"""Reconstruct archive metadata and labels with bounded ZIP64 range requests."""

from __future__ import annotations

import csv
import io
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, final

import typer

from retina.download import URL, create_client

EOCD, ZIP64_EOCD, ZIP64_LOCATOR = b"PK\x05\x06", b"PK\x06\x06", b"PK\x06\x07"
CENTRAL, LOCAL = b"PK\x01\x02", b"PK\x03\x04"
TAIL_BYTES, MAX_RANGE_BYTES = 131_072, 32 * 1024 * 1024
UINT16_MAX, UINT32_MAX = 0xFFFF, 0xFFFFFFFF
LABEL_SUFFIX: Final = "/trainLabels.csv"
INVENTORY_FIELDS: Final = ("Name", "Size", "Compressed", "Offset", "Method")
PARTIAL_CONTENT, EOCD_BYTES, LOCAL_HEADER_BYTES, STORE_METHOD, DEFLATE_METHOD = 206, 22, 30, 0, 8

if TYPE_CHECKING:
    import httpx2


@final
class BootstrapError(RuntimeError):
    """A remote archive boundary or ZIP structure was invalid."""

    def __init__(self, detail: str) -> None:
        """Create a typed archive-boundary failure."""
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Paths required by the analysis and selective image downloader."""

    directory: Path
    inventory: Path
    labels: Path


@dataclass(frozen=True, slots=True)
class _CentralEntry:
    name: str
    size: int
    compressed: int
    offset: int
    method: int
    checksum: int


def _content_range(value: str) -> tuple[int, int, int]:
    try:
        unit, positions = value.split(" ", maxsplit=1)
        interval, total_text = positions.split("/", maxsplit=1)
        start_text, stop_text = interval.split("-", maxsplit=1)
        parsed = (int(start_text), int(stop_text), int(total_text))
    except (ValueError, TypeError) as error:
        raise BootstrapError(detail="invalid content-range response") from error
    if unit != "bytes" or parsed[0] > parsed[1] or parsed[1] >= parsed[2]:
        raise BootstrapError(detail="invalid content-range response")
    return parsed


def _range(client: httpx2.Client, url: str, header: str) -> tuple[bytes, int, int]:
    with client.stream("GET", url, headers={"Range": header}) as response:
        if response.status_code != PARTIAL_CONTENT:
            raise BootstrapError(detail="server ignored the byte range request")
        start, stop, total = _content_range(response.headers.get("content-range", ""))
        expected = stop - start + 1
        if expected > MAX_RANGE_BYTES:
            raise BootstrapError(detail="server proposed an unexpectedly large range")
        payload = response.read()
    if len(payload) != expected:
        raise BootstrapError(detail="range response length does not match its header")
    return payload, start, total


def _absolute_range(
    client: httpx2.Client, url: str, offset: int, size: int, *, exact: bool = True
) -> bytes:
    if size <= 0 or size > MAX_RANGE_BYTES:
        raise BootstrapError(detail="requested ZIP range is outside the safe bound")
    payload, start, _ = _range(client, url, f"bytes={offset}-{offset + size - 1}")
    if start != offset or (exact and len(payload) != size):
        raise BootstrapError(detail="server returned a different ZIP range")
    return payload


def _location(client: httpx2.Client, url: str) -> tuple[int, int, int]:
    tail, tail_offset, _ = _range(client, url, f"bytes=-{TAIL_BYTES}")
    eocd = tail.rfind(EOCD)
    if eocd < 0 or len(tail) - eocd < EOCD_BYTES:
        raise BootstrapError(detail="ZIP end record is missing")
    entries = _integer(tail, eocd + 10, 2)
    size = _integer(tail, eocd + 12, 4)
    offset = _integer(tail, eocd + 16, 4)
    if entries != UINT16_MAX and UINT32_MAX not in (size, offset):
        return offset, size, entries
    locator = eocd - 20
    if locator < 0 or tail[locator : locator + 4] != ZIP64_LOCATOR:
        raise BootstrapError(detail="ZIP64 locator is missing")
    zip64_offset = _integer(tail, locator + 8, 8)
    relative = zip64_offset - tail_offset
    record = (
        tail[relative : relative + 56]
        if relative >= 0 and relative + 56 <= len(tail)
        else _absolute_range(client, url, zip64_offset, 56)
    )
    if record[:4] != ZIP64_EOCD:
        raise BootstrapError(detail="ZIP64 end record is missing")
    return _integer(record, 48, 8), _integer(record, 40, 8), _integer(record, 32, 8)


def _integer(payload: bytes, offset: int, size: int) -> int:
    return int.from_bytes(payload[offset : offset + size], "little")


def _zip64_values(extra: bytes, needs: tuple[bool, bool, bool]) -> tuple[int, ...]:
    position = 0
    while position + 4 <= len(extra):
        field_id = _integer(extra, position, 2)
        length = _integer(extra, position + 2, 2)
        value = extra[position + 4 : position + 4 + length]
        if field_id == 1:
            count = sum(needs)
            if len(value) < count * 8:
                raise BootstrapError(detail="ZIP64 entry metadata is truncated")
            return tuple(_integer(value, index * 8, 8) for index in range(count))
        position += 4 + length
    raise BootstrapError(detail="ZIP64 entry metadata is missing")


def _entries(directory: bytes, expected: int | None = None) -> list[_CentralEntry]:
    result: list[_CentralEntry] = []
    position = 0
    while position < len(directory):
        if directory[position : position + 4] != CENTRAL or position + 46 > len(directory):
            raise BootstrapError(detail="central directory is malformed")
        method = _integer(directory, position + 10, 2)
        checksum = _integer(directory, position + 16, 4)
        compressed = _integer(directory, position + 20, 4)
        size = _integer(directory, position + 24, 4)
        name_len = _integer(directory, position + 28, 2)
        extra_len = _integer(directory, position + 30, 2)
        comment_len = _integer(directory, position + 32, 2)
        offset = _integer(directory, position + 42, 4)
        end = position + 46 + name_len + extra_len + comment_len
        if end > len(directory):
            raise BootstrapError(detail="central directory entry is truncated")
        name_bytes = directory[position + 46 : position + 46 + name_len]
        extra = directory[position + 46 + name_len : position + 46 + name_len + extra_len]
        needs = (size == UINT32_MAX, compressed == UINT32_MAX, offset == UINT32_MAX)
        if any(needs):
            values = iter(_zip64_values(extra, needs))
            size = next(values) if needs[0] else size
            compressed = next(values) if needs[1] else compressed
            offset = next(values) if needs[2] else offset
        result.append(
            _CentralEntry(name_bytes.decode("utf-8"), size, compressed, offset, method, checksum)
        )
        position = end
    if expected is not None and len(result) != expected:
        raise BootstrapError(detail="central directory entry count does not match ZIP metadata")
    return result


def _decode_label(payload: bytes, entry: _CentralEntry) -> bytes:
    if payload[:4] != LOCAL or len(payload) < LOCAL_HEADER_BYTES:
        raise BootstrapError(detail="label local header is missing")
    name_len = _integer(payload, 26, 2)
    extra_len = _integer(payload, 28, 2)
    start = LOCAL_HEADER_BYTES + name_len + extra_len
    compressed = payload[start : start + entry.compressed]
    if entry.method == STORE_METHOD:
        raw = compressed
    else:
        if entry.method != DEFLATE_METHOD:
            raise BootstrapError(detail=f"unsupported label compression method: {entry.method}")
        raw = zlib.decompress(compressed, -15)
    if len(raw) != entry.size or zlib.crc32(raw) != entry.checksum:
        raise BootstrapError(detail="label CRC or size does not match the central directory")
    return raw


def _inventory_matches(path: Path, entries: list[_CentralEntry]) -> bool:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(INVENTORY_FIELDS):
            return False
        return all(
            tuple(row[field] for field in INVENTORY_FIELDS)
            == (
                entry.name,
                str(entry.size),
                str(entry.compressed),
                str(entry.offset),
                str(entry.method),
            )
            for row, entry in zip(reader, entries, strict=True)
        )


def _existing(result: BootstrapResult) -> bool:
    if not all(path.is_file() for path in _paths(result)):
        return False
    try:
        entries = _entries(result.directory.read_bytes())
        label = next(entry for entry in entries if entry.name.endswith(LABEL_SUFFIX))
        labels = result.labels.read_bytes()
        return (
            _inventory_matches(result.inventory, entries)
            and len(labels) == label.size
            and zlib.crc32(labels) == label.checksum
        )
    except (BootstrapError, StopIteration, UnicodeDecodeError, csv.Error, OSError, ValueError):
        return False


def _write(result: BootstrapResult, directory: bytes, inventory: str, labels: bytes) -> None:
    temporary = BootstrapResult(
        *(path.with_suffix(path.suffix + ".bootstrap.tmp") for path in _paths(result))
    )
    try:
        _ = temporary.directory.write_bytes(directory)
        _ = temporary.inventory.write_text(inventory, encoding="utf-8-sig", newline="")
        _ = temporary.labels.write_bytes(labels)
        if not _existing(temporary):
            raise BootstrapError(detail="reconstructed bootstrap artifacts failed validation")
        for source, destination in zip(_paths(temporary), _paths(result), strict=True):
            _ = source.replace(destination)
    finally:
        for path in _paths(temporary):
            path.unlink(missing_ok=True)


def _paths(result: BootstrapResult) -> tuple[Path, Path, Path]:
    return result.directory, result.inventory, result.labels


def bootstrap(
    destination: Path | None = None,
    *,
    client: httpx2.Client | None = None,
    url: str = URL,
    force: bool = False,
) -> BootstrapResult:
    """Fetch only archive metadata and labels needed for later selective downloads."""
    root = destination or Path()
    result = BootstrapResult(
        directory=root / "zip-directory.bin",
        inventory=root / "data-inventory.csv",
        labels=root / "trainLabels.csv",
    )
    if not force and _existing(result):
        return result
    owned = client is None
    active = client or create_client()
    try:
        offset, size, entry_count = _location(active, url)
        directory = _absolute_range(active, url, offset, size)
        entries = _entries(directory, entry_count)
        label = next((entry for entry in entries if entry.name.endswith(LABEL_SUFFIX)), None)
        if label is None:
            raise BootstrapError(detail="trainLabels.csv is absent from the archive")
        member = _absolute_range(active, url, label.offset, label.compressed + 65_536, exact=False)
        raw_labels = _decode_label(member, label)
    finally:
        if owned:
            active.close()
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(INVENTORY_FIELDS)
    writer.writerows(
        (entry.name, entry.size, entry.compressed, entry.offset, entry.method) for entry in entries
    )
    root.mkdir(parents=True, exist_ok=True)
    _write(result, directory, buffer.getvalue(), raw_labels)
    return result


def main(destination: Path | None = None, force: bool = False) -> None:
    """CLI entry point for source-only checkouts."""
    result = bootstrap(destination, force=force)
    typer.echo(f"Archive metadata ready: {result.inventory}\nLabels ready: {result.labels}")


if __name__ == "__main__":
    typer.run(main)

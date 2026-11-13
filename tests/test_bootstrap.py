from __future__ import annotations

import csv
import io
import struct
import zlib
from typing import TYPE_CHECKING, assert_never
from zipfile import ZIP_DEFLATED, ZipFile

import httpx2
import pytest

from retina.bootstrap import BootstrapError, bootstrap

if TYPE_CHECKING:
    from pathlib import Path


def _zip64_fixture() -> bytes:
    name = b"diabetic-retinopathy/trainLabels.csv"
    raw = b"image,level\n1_left,0\n1_right,1\n"
    compressor = zlib.compressobj(level=6, wbits=-15)
    compressed = compressor.compress(raw) + compressor.flush()
    checksum = zlib.crc32(raw)
    local = (
        struct.pack(
            "<IHHHHHIIIHH",
            0x04034B50,
            45,
            0,
            8,
            0,
            0,
            checksum,
            len(compressed),
            len(raw),
            len(name),
            0,
        )
        + name
        + compressed
    )
    zip64_extra = struct.pack("<HHQQQ", 1, 24, len(raw), len(compressed), 0)
    central = (
        struct.pack(
            "<IHHHHHHIIIHHHHHII",
            0x02014B50,
            45,
            45,
            0,
            8,
            0,
            0,
            checksum,
            0xFFFFFFFF,
            0xFFFFFFFF,
            len(name),
            len(zip64_extra),
            0,
            0,
            0,
            0,
            0xFFFFFFFF,
        )
        + name
        + zip64_extra
    )
    central_offset = len(local)
    zip64_offset = central_offset + len(central)
    zip64_eocd = struct.pack(
        "<IQHHIIQQQQ",
        0x06064B50,
        44,
        45,
        45,
        0,
        0,
        1,
        1,
        len(central),
        central_offset,
    )
    locator = struct.pack("<IIQI", 0x07064B50, 0, zip64_offset, 1)
    eocd = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        0xFFFF,
        0xFFFF,
        0xFFFFFFFF,
        0xFFFFFFFF,
        0,
    )
    return local + central + zip64_eocd + locator + eocd


def _range_client(blob: bytes, requested: list[str]) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        range_value = request.headers["range"]
        requested.append(range_value)
        if range_value.startswith("bytes=-"):
            count = min(int(range_value.removeprefix("bytes=-")), len(blob))
            start = len(blob) - count
            stop = len(blob) - 1
        else:
            start_text, stop_text = range_value.removeprefix("bytes=").split("-", 1)
            start = int(start_text)
            stop = min(int(stop_text), len(blob) - 1)
        return httpx2.Response(
            206,
            headers={"content-range": f"bytes {start}-{stop}/{len(blob)}"},
            content=blob[start : stop + 1],
        )

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def _standard_zip_fixture() -> bytes:
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("dataset/trainLabels.csv", "image,level\n7_left,2\n")
        archive.writestr("dataset/train/7_left.jpeg", b"jpeg")
    return stream.getvalue()


def test_bootstrap_reconstructs_zip64_inventory_and_labels(tmp_path: Path) -> None:
    # Given a ZIP64 archive available only through byte ranges.
    archive = _zip64_fixture()
    requested: list[str] = []
    with _range_client(archive, requested) as client:
        # When bootstrapping source metadata.
        result = bootstrap(tmp_path, client=client, url="https://example.test/archive.zip")

    # Then all three prerequisite files are reconstructed without a whole-file request.
    assert result.labels.read_bytes() == b"image,level\n1_left,0\n1_right,1\n"
    assert result.directory.read_bytes().startswith(b"PK\x01\x02")
    with result.inventory.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]["Name"] == "diabetic-retinopathy/trainLabels.csv"
    assert rows[0]["Size"] == "31"
    assert rows[0]["Offset"] == "0"
    assert rows[0]["Method"] == "8"
    assert all(value != "bytes=0-" for value in requested)
    assert len(requested) <= 4


def test_bootstrap_supports_standard_zip_end_record(tmp_path: Path) -> None:
    # Given a small ordinary ZIP archive served through ranges.
    archive = _standard_zip_fixture()
    requested: list[str] = []
    with _range_client(archive, requested) as client:
        # When bootstrapping the same public contract.
        result = bootstrap(tmp_path, client=client, url="https://example.test/archive.zip")

    # Then the labels and all central entries are recovered.
    assert result.labels.read_text(encoding="utf-8") == "image,level\n7_left,2\n"
    with result.inventory.open(encoding="utf-8-sig", newline="") as stream:
        names = [row["Name"] for row in csv.DictReader(stream)]
    assert names == ["dataset/trainLabels.csv", "dataset/train/7_left.jpeg"]


def test_bootstrap_rejects_server_that_ignores_range(tmp_path: Path) -> None:
    # Given a server that answers a byte-range request with a full 200 response.
    def handler(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"full archive must not be accepted")

    with (
        httpx2.Client(transport=httpx2.MockTransport(handler)) as client,
        pytest.raises(BootstrapError, match="range"),
    ):
        # When bootstrapping, then it fails instead of treating the body as a ZIP tail.
        bootstrap(tmp_path, client=client, url="https://example.test/archive.zip")


def test_bootstrap_skips_network_when_existing_files_are_complete(tmp_path: Path) -> None:
    # Given a complete cache created from one verified archive.
    archive = _standard_zip_fixture()
    requested: list[str] = []
    with _range_client(archive, requested) as client:
        expected = bootstrap(tmp_path, client=client, url="https://example.test/archive.zip")

    def fail_if_called(_: httpx2.Request) -> httpx2.Response:
        raise AssertionError

    with httpx2.Client(transport=httpx2.MockTransport(fail_if_called)) as client:
        # When bootstrapping without force.
        result = bootstrap(tmp_path, client=client, url="https://example.test/archive.zip")

    # Then the validated local files are reused.
    assert result == expected


@pytest.mark.parametrize("corruption", ["directory", "inventory", "labels"])
def test_bootstrap_refetches_when_cached_artifacts_do_not_match(
    tmp_path: Path,
    corruption: str,
) -> None:
    # Given a valid cache with one truncated or tampered artifact.
    archive = _standard_zip_fixture()
    initial_requests: list[str] = []
    with _range_client(archive, initial_requests) as client:
        result = bootstrap(tmp_path, client=client, url="https://example.test/archive.zip")
    match corruption:
        case "directory":
            result.directory.write_bytes(b"PK\x01\x02entry")
        case "inventory":
            result.inventory.write_text(
                '"Name","Size","Compressed","Offset","Method"\n',
                encoding="utf-8",
            )
        case "labels":
            result.labels.write_text("image,level\n7_left,4\n", encoding="utf-8")
        case unreachable:
            assert_never(unreachable)

    # When bootstrapping again from the same source archive.
    recovery_requests: list[str] = []
    with _range_client(archive, recovery_requests) as client:
        recovered = bootstrap(tmp_path, client=client, url="https://example.test/archive.zip")

    # Then the invalid cache is fetched and rebuilt as one matching set.
    assert recovery_requests
    assert recovered.labels.read_text(encoding="utf-8") == "image,level\n7_left,2\n"
    assert recovered.directory.read_bytes().startswith(b"PK\x01\x02")
    assert not list(tmp_path.glob("*.bootstrap.tmp"))

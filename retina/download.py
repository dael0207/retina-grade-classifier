"""Fetch selected ZIP members, validate CRC, and preserve original JPEG bytes."""

import csv
import hashlib
import io
import logging
import socket
import time
import zlib
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar, Final

import httpx2
from PIL import Image
from pydantic import BaseModel, ConfigDict

ROOT: Final = Path(__file__).resolve().parents[1]
URL: Final = (
    "https://drive.usercontent.google.com/download"
    "?id=1bqh0eEzBGFOit9_BJ7bwuoSG25LZXVHg&export=download&confirm=t"
)
LOGGER: Final = logging.getLogger(__name__)
CENTRAL_SIGNATURE: Final = 0x02014B50
LOCAL_SIGNATURE: Final = 0x04034B50
DEFLATE_METHOD: Final = 8
PARTIAL_CONTENT: Final = 206
MAX_ATTEMPTS: Final = 4
RETRY_DELAYS: Final = (1.0, 2.0, 4.0, 8.0)


@dataclass(frozen=True, slots=True)
class Entry:
    """ZIP central-directory facts for an image."""

    image: str
    offset: int
    compressed: int
    size: int
    checksum: int


@dataclass(frozen=True, slots=True)
class Audit:
    """Provenance and integrity evidence from an original JPEG."""

    image: str
    sha256: str
    original_width: int
    original_height: int
    original_bytes: int
    crc_verified: bool


class ArchiveError(RuntimeError):
    """Archive integrity validation failed."""


class ExamplePair(BaseModel):
    """Only the image fields are needed from the analysis examples."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    left_image: str
    right_image: str


class Examples(BaseModel):
    """Typed boundary for the analysis example selection."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    pairs: list[ExamplePair]


def create_client() -> httpx2.Client:
    """Use pooled bounded HTTP requests with transport retries."""
    limits = httpx2.Limits(max_connections=200, max_keepalive_connections=40, keepalive_expiry=30)
    transport = httpx2.HTTPTransport(
        # Drive repeatedly disconnects concurrent HTTP/2 range streams; HTTP/1.1 isolates them.
        http2=False,
        retries=3,
        limits=limits,
        socket_options=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)],
    )
    return httpx2.Client(
        transport=transport,
        timeout=httpx2.Timeout(connect=5, read=30, write=10, pool=10),
        follow_redirects=True,
    )


def entries() -> list[Entry]:
    """Resolve selected image names against the inspected central directory."""
    with (ROOT / "data/manifest.csv").open(encoding="utf-8", newline="") as source:
        wanted = {row["image"] for row in csv.DictReader(source)}
    examples = ROOT / "outputs/assignment1/examples.json"
    if examples.exists():
        selected = Examples.model_validate_json(examples.read_text(encoding="utf-8"))
        for pair in selected.pairs:
            wanted.update((pair.left_image, pair.right_image))
    checksums = central_checksums()
    result: list[Entry] = []
    with (ROOT / "data-inventory.csv").open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            image = Path(row["Name"]).stem
            if "/train/" in row["Name"] and image in wanted:
                result.append(
                    Entry(
                        image,
                        int(row["Offset"]),
                        int(row["Compressed"]),
                        int(row["Size"]),
                        checksums[row["Name"]],
                    )
                )
    if len(result) != len(wanted):
        message = "Manifest contains names absent from the ZIP inventory"
        raise ArchiveError(message)
    return result


def central_checksums() -> Mapping[str, int]:
    """Read authoritative CRCs, including members with deferred local descriptors."""
    directory = (ROOT / "zip-directory.bin").read_bytes()
    position = 0
    checksums: dict[str, int] = {}
    while position + 46 <= len(directory):
        if int.from_bytes(directory[position : position + 4], "little") != CENTRAL_SIGNATURE:
            message = "Invalid central-directory signature"
            raise ArchiveError(message)
        checksum = int.from_bytes(directory[position + 16 : position + 20], "little")
        name_len = int.from_bytes(directory[position + 28 : position + 30], "little")
        extra_len = int.from_bytes(directory[position + 30 : position + 32], "little")
        comment_len = int.from_bytes(directory[position + 32 : position + 34], "little")
        name = directory[position + 46 : position + 46 + name_len].decode("utf-8")
        checksums[name] = checksum
        position += 46 + name_len + extra_len + comment_len
    return checksums


def decode_member(payload: bytes, entry: Entry) -> bytes:
    """Validate compressed bytes using the central-directory CRC, not a deferred zero."""
    signature = int.from_bytes(payload[:4], "little")
    method = int.from_bytes(payload[8:10], "little")
    name_len = int.from_bytes(payload[26:28], "little")
    extra_len = int.from_bytes(payload[28:30], "little")
    if signature != LOCAL_SIGNATURE or method != DEFLATE_METHOD:
        message = f"Unexpected ZIP member for {entry.image}"
        raise ArchiveError(message)
    start = 30 + name_len + extra_len
    raw = zlib.decompress(payload[start : start + entry.compressed], -15)
    if len(raw) != entry.size or zlib.crc32(raw) != entry.checksum:
        message = f"CRC or size mismatch for {entry.image}"
        raise ArchiveError(message)
    return raw


def fetch_entry(client: httpx2.Client, entry: Entry) -> Audit:
    """Read a range, validate the local header and checksum, and retain original pixels."""
    stop = entry.offset + entry.compressed + 1023
    with client.stream("GET", URL, headers={"Range": f"bytes={entry.offset}-{stop}"}) as response:
        _ = response.raise_for_status()
        expected = f"bytes {entry.offset}-"
        if response.status_code != PARTIAL_CONTENT or not response.headers.get(
            "content-range", ""
        ).startswith(expected):
            message = f"Server ignored byte range for {entry.image}"
            raise ArchiveError(message)
        payload = response.read()
    raw = decode_member(payload, entry)
    with Image.open(io.BytesIO(raw)) as original:
        _ = original.load()
        width, height = original.size
    _ = (ROOT / "data/images" / f"{entry.image}.jpg").write_bytes(raw)
    return Audit(
        entry.image, hashlib.sha256(raw).hexdigest(), width, height, len(raw), crc_verified=True
    )


def fetch_with_retry(client: httpx2.Client, entry: Entry) -> Audit:
    """Retry recoverable HTTP transfer failures while keeping integrity failures explicit."""
    for attempt in range(MAX_ATTEMPTS):
        try:
            return fetch_entry(client, entry)
        except (httpx2.HTTPError, ArchiveError) as error:
            if attempt == MAX_ATTEMPTS - 1:
                raise
            LOGGER.warning("Retry %s (%s): %s", entry.image, attempt + 1, error)
            time.sleep(RETRY_DELAYS[attempt])
    message = "Retry loop exhausted"
    raise ArchiveError(message)


def main() -> None:
    """Download a resumable cohort, keeping successful provenance rows on disk."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    (ROOT / "data/images").mkdir(parents=True, exist_ok=True)
    audit_path = ROOT / "data/image_audit.csv"
    completed: set[str] = set()
    if audit_path.exists():
        with audit_path.open(encoding="utf-8", newline="") as source:
            completed = {row["image"] for row in csv.DictReader(source)}
    pending = [entry for entry in entries() if entry.image not in completed]
    LOGGER.info("Pending %s; already verified %s", len(pending), len(completed))
    with (
        create_client() as client,
        ThreadPoolExecutor(max_workers=12) as pool,
        audit_path.open("a", encoding="utf-8", newline="") as target,
    ):
        writer = csv.DictWriter(target, fieldnames=list(Audit.__dataclass_fields__))
        if target.tell() == 0:
            writer.writeheader()
        futures = {pool.submit(fetch_with_retry, client, entry): entry for entry in pending}
        for count, future in enumerate(as_completed(futures), 1):
            writer.writerow(asdict(future.result()))
            target.flush()
            if count % 25 == 0 or count == len(pending):
                LOGGER.info("Verified %s / %s", count, len(pending))


if __name__ == "__main__":
    main()

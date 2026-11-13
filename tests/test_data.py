"""Data integrity and image transformation contracts."""

import hashlib
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image

from retina.download import ArchiveError, Entry, decode_member
from retina.imaging import prepare_image
from retina.integrity import AuditRecord, verify_image


def test_preparation_preserves_aspect_and_produces_rgb() -> None:
    # Given a non-square, non-RGB image.
    source = Image.new("L", (200, 100), color=100)

    # When preparing the source for the model.
    result = prepare_image(source)
    # Then it is padded, not geometrically stretched.
    assert result.size == (320, 320)
    assert result.mode == "RGB"
    assert result.getpixel((160, 0)) == (0, 0, 0)
    assert result.getpixel((160, 160)) == (100, 100, 100)


def test_black_image_is_handled_without_empty_crop() -> None:
    # Given an all-black image.
    source = Image.new("RGB", (75, 100))

    # When transforming it.
    result = prepare_image(source)
    # Then the output is valid and unchanged in information content.
    assert result.size == (320, 320)
    assert result.getbbox() is None


def test_zip_descriptor_uses_central_crc() -> None:
    # Given a ZIP member whose flag 8 defers the local checksum.
    raw = b"original-image-bytes"
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(raw) + compressor.flush()
    header = bytearray(30)
    struct.pack_into("<I", header, 0, 0x04034B50)
    struct.pack_into("<HH", header, 6, 8, 8)
    entry = Entry("example", 0, len(compressed), len(raw), zlib.crc32(raw))
    # When decoded using central directory metadata.
    decoded = decode_member(bytes(header) + compressed, entry)
    # Then a deferred zero CRC is not mistaken for corruption.
    assert decoded == raw


def test_zip_corruption_is_rejected() -> None:
    # Given valid deflate bytes with an incorrect central checksum.
    raw = b"source"
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(raw) + compressor.flush()
    header = bytearray(30)
    struct.pack_into("<I", header, 0, 0x04034B50)
    struct.pack_into("<H", header, 8, 8)
    entry = Entry("example", 0, len(compressed), len(raw), 1)
    # When validating the member, then corruption is explicit.
    with pytest.raises(ArchiveError, match="CRC"):
        decode_member(bytes(header) + compressed, entry)


def test_processed_cache_is_rejected_as_an_original(tmp_path: Path) -> None:
    # Given an audit for original bytes and a resized substitute.
    path = tmp_path / "eye.jpg"
    Image.new("RGB", (640, 480), color="red").save(path)
    raw = path.read_bytes()
    record = AuditRecord(
        image="eye",
        sha256=hashlib.sha256(raw).hexdigest(),
        original_width=640,
        original_height=480,
        original_bytes=len(raw),
        crc_verified=True,
    )
    Image.new("RGB", (320, 320), color="red").save(path)
    # When checking source identity, then transformed substitutes are rejected.
    with pytest.raises(ValueError, match="Source byte mismatch"):
        verify_image(path, record)

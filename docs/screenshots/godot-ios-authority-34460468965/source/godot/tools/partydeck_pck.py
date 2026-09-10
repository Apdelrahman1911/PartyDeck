"""Inspect standalone, unencrypted Godot 4.7.2 PCK files without an engine.

The v4 layout is taken from the pinned engine's file_access_pack.cpp and
editor_export_platform.cpp; see README.md. Unsupported pack modes fail closed.
"""

from hashlib import md5, sha256
from pathlib import Path, PurePosixPath
import struct


class PackError(ValueError):
    pass


def normalized_path(value: str) -> str:
    value = value.removeprefix("res://")
    path = PurePosixPath(value)
    if not value or "\x00" in value or "\\" in value or path.is_absolute():
        raise PackError("PCK contains an invalid resource path")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise PackError("PCK contains a non-canonical resource path")
    return value


def read_pack(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 108:
        raise PackError("PCK header is truncated")
    magic, version, major, minor, patch, flags = struct.unpack_from("<6I", data)
    if magic != 0x43504447 or version != 4 or (major, minor, patch) != (4, 7, 2):
        raise PackError("Expected a standalone Godot 4.7.2 PCK format v4")
    if flags != 2:
        raise PackError("Only plain, relative-filebase PCK exports are supported")
    file_base, directory = struct.unpack_from("<2Q", data, 24)
    if not 104 <= file_base <= directory <= len(data) - 4:
        raise PackError("PCK directory or data base is outside the file")
    count = struct.unpack_from("<I", data, directory)[0]
    if not 1 <= count <= 100_000:
        raise PackError("PCK file count is outside the supported bound")
    cursor = directory + 4
    entries = []
    seen = set()
    for _ in range(count):
        if cursor + 4 > len(data):
            raise PackError("PCK directory is truncated")
        length = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4
        if not 1 <= length <= 4096 or cursor + length + 36 > len(data):
            raise PackError("PCK directory entry is truncated or oversized")
        try:
            name = normalized_path(data[cursor:cursor + length].rstrip(b"\0").decode("utf-8"))
        except UnicodeDecodeError as error:
            raise PackError("PCK resource path is not UTF-8") from error
        cursor += length
        offset, size = struct.unpack_from("<2Q", data, cursor)
        digest = data[cursor + 16:cursor + 32]
        file_flags = struct.unpack_from("<I", data, cursor + 32)[0]
        cursor += 36
        start = file_base + offset
        if name in seen or file_flags != 0 or start + size > directory:
            raise PackError("PCK contains duplicate paths, unsupported file flags, or invalid offsets")
        seen.add(name)
        content = data[start:start + size]
        # MD5 is part of Godot's file format, not the artifact trust mechanism.
        if md5(content, usedforsecurity=False).digest() != digest:
            raise PackError("PCK entry checksum differs: " + name)
        entries.append({"path": name, "bytes": size, "sha256": sha256(content).hexdigest()})
    return {
        "format_version": version,
        "engine_version": f"{major}.{minor}.{patch}",
        "bytes": len(data),
        "sha256": sha256(data).hexdigest(),
        "entries": sorted(entries, key=lambda entry: entry["path"]),
    }

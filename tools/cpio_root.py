#!/usr/bin/env python3
"""Pack a directory into a deterministic gzipped SVR4 newc cpio archive (uid=0, gid=0, mtime=0)."""
import gzip
import os
import stat
import sys


def pack_cpio_gz(root_dir: str, out_gz_path: str) -> None:
    entries = []
    for dirpath, dirnames, filenames in os.walk(root_dir, followlinks=False):
        dirnames.sort()
        filenames.sort()
        rel_dir = os.path.relpath(dirpath, root_dir)
        if rel_dir != ".":
            entries.append(rel_dir)
        for fn in dirnames + filenames:
            p = os.path.join(dirpath, fn)
            if os.path.islink(p) or os.path.isfile(p):
                entries.append(os.path.relpath(p, root_dir))

    seen = set()
    ordered = []
    for e in sorted(entries):
        if e not in seen:
            seen.add(e)
            ordered.append(e)

    ino = 300000
    buf = bytearray()

    def write_entry(name: str, mode: int, data: bytes, nlink: int = 1) -> None:
        nonlocal ino
        ino += 1
        name_bytes = name.encode("utf-8") + b"\x00"
        header = (
            "070701"
            f"{ino:08x}"
            f"{mode:08x}"
            f"{0:08x}"
            f"{0:08x}"
            f"{nlink:08x}"
            f"{0:08x}"
            f"{len(data):08x}"
            f"{0:08x}{0:08x}{0:08x}{0:08x}"
            f"{len(name_bytes):08x}"
            f"{0:08x}"
        ).encode("ascii")
        buf.extend(header)
        buf.extend(name_bytes)
        while len(buf) % 4 != 0:
            buf.append(0)
        buf.extend(data)
        while len(buf) % 4 != 0:
            buf.append(0)

    for rel in ordered:
        full = os.path.join(root_dir, rel)
        st = os.lstat(full)
        mode = st.st_mode
        if stat.S_ISLNK(mode):
            target = os.readlink(full).encode("utf-8")
            write_entry(rel, mode, target, 1)
        elif stat.S_ISDIR(mode):
            write_entry(rel, mode, b"", 2)
        elif stat.S_ISREG(mode):
            with open(full, "rb") as f:
                data = f.read()
            write_entry(rel, mode, data, 1)

    write_entry("TRAILER!!!", 0, b"", 1)
    while len(buf) % 512 != 0:
        buf.append(0)

    os.makedirs(os.path.dirname(os.path.abspath(out_gz_path)), exist_ok=True)
    with open(out_gz_path, "wb") as raw_f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_f, compresslevel=9, mtime=0) as gz:
            gz.write(buf)


if __name__ == "__main__":
    pack_cpio_gz(sys.argv[1], sys.argv[2])
    print(f"Packed {sys.argv[1]} -> {sys.argv[2]} ({os.path.getsize(sys.argv[2])} bytes)")

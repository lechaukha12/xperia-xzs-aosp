#!/usr/bin/env python3
"""Replace only the kernel in a v0 boot image, retaining its ramdisk/header.

Produces a separate test artifact; never flashes a device or edits the input.
"""
import argparse
import shlex
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("boot", type=Path)
parser.add_argument("kernel", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
assert args.output.resolve() != args.boot.resolve(), "Use a separate output"
source = args.boot.read_bytes()
assert source[:8] == b"ANDROID!" and struct.unpack_from("<I", source, 40)[0] == 0
root = Path(__file__).resolve().parent / "mkbootimg"
with tempfile.TemporaryDirectory(prefix="keyaki-boot-") as tmp:
    cmdline = subprocess.check_output([
        sys.executable, str(root / "unpack_bootimg.py"),
        "--boot_img", str(args.boot.resolve()), "--out", tmp,
        "--format", "mkbootimg"], text=True)
    options = shlex.split(cmdline)
    options[options.index("--kernel") + 1] = str(args.kernel.resolve())
    subprocess.run([sys.executable, str(root / "mkbootimg.py"), *options,
                    "--output", str(args.output.resolve())], check=True)
result = args.output.read_bytes()
assert len(result) <= 64 * 1024 * 1024
assert source[12:576] == result[12:576], "Header fields changed"
assert source[608:1632] == result[608:1632], "Extra command line changed"

def ramdisk(image):
    kernel_size, = struct.unpack_from("<I", image, 8)
    ramdisk_size, = struct.unpack_from("<I", image, 16)
    page, = struct.unpack_from("<I", image, 36)
    offset = page + (kernel_size + page - 1) // page * page
    return image[offset:offset + ramdisk_size]

assert ramdisk(source) == ramdisk(result), "Ramdisk changed"
print(f"Created {args.output}; original ramdisk and load parameters preserved")

#!/usr/bin/env python3
"""Write reviewed keyaki boot/OEM images from root recovery and verify read-back.

Targets are fixed to SO-03J boot and optional OEM. Does not reboot automatically.
Full existing partition backups are mandatory. Never writes FOTAKernel or data.
"""
import argparse
import hashlib
import struct
import shlex
import subprocess
from pathlib import Path

PARTITION = "/dev/block/mmcblk0p30"
SIZE = 64 * 1024 * 1024
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("image", type=Path)
parser.add_argument("--backup", type=Path, required=True)
parser.add_argument("--oem", type=Path)
parser.add_argument("--oem-backup", type=Path)
args = parser.parse_args()
assert args.backup.stat().st_size == SIZE, "A full baseline boot backup is required"
data = args.image.read_bytes()
assert data[:8] == b"ANDROID!" and struct.unpack_from("<I", data, 40)[0] == 0
assert 0 < len(data) <= SIZE and len(data) % 4096 == 0
assert bool(args.oem) == bool(args.oem_backup), "OEM image and backup are a pair"
images = [(args.image, "boot", PARTITION, SIZE)]
if args.oem:
    assert args.oem.stat().st_size == 400 * 1024 * 1024
    assert args.oem_backup.stat().st_size == 400 * 1024 * 1024
    with args.oem.open("rb") as stream:
        stream.seek(1080)
        assert stream.read(2) == b"\x53\xef", "Raw ext4 OEM image required"
    images.append((args.oem, "oem", "/dev/block/mmcblk0p53", 400 * 1024 * 1024))

def adb(*argv):
    return subprocess.check_output(["adb", *argv], stderr=subprocess.PIPE)

assert adb("get-state").strip() == b"recovery", "Root recovery required"
assert adb("shell", "id -u").strip() == b"0", "Root recovery required"
for image, name, partition, capacity in images:
    assert int(adb("shell", f"blockdev --getsize64 {partition}")) == capacity
    label = adb("shell", f"readlink -f /dev/block/bootdevice/by-name/{name}").strip()
    assert label.decode() == partition, f"Unexpected partition mapping: {label!r}"
targets = {entry[2] for entry in images}
for line in adb("shell", "cat /proc/mounts").decode().splitlines():
    source = line.split()[0]
    if source.startswith("/dev/block/"):
        resolved = adb("shell", f"readlink -f {shlex.quote(source)}").strip().decode()
        assert resolved not in targets, f"Unmount {source} before flashing"

for image, name, partition, capacity in images:
    hasher = hashlib.sha256()
    with image.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    digest = hasher.hexdigest()
    remote = f"/tmp/codex-release-{name}.img"
    subprocess.run(["adb", "push", str(image), remote], check=True)
    assert adb("shell", f"sha256sum {remote}").decode().split()[0] == digest
    # Older TWRP dd lacks conv=fsync; run sync separately and verify block data.
    adb("shell", f"dd if={remote} of={partition} bs=4096 && sync")
    if image.stat().st_size == capacity:
        result = adb("shell", f"sha256sum {partition}")
    else:
        count = image.stat().st_size // 4096
        result = adb("shell", f"dd if={partition} bs=4096 count={count} 2>/dev/null | sha256sum")
    assert result.decode().split()[0] == digest, f"{name} read-back mismatch; do not reboot"
    print(f"{name} write and read-back verified: {digest}", flush=True)

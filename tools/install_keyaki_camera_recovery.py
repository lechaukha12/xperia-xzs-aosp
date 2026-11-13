#!/usr/bin/env python3
"""Install only the three keyaki camera XMLs in root TWRP; verify read-back.

Does not reboot or replace the vendor image. Keeps all Bluetooth/audio files.
"""
import argparse
import hashlib
import shlex
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = ("camera_config.xml", "imx258_chromatix.xml", "imx400_chromatix.xml")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--backup-dir", type=Path, required=True)
args = parser.parse_args()
source = ROOT / "base_rom/device-keyaki/rootdir/vendor/etc/camera"
sensors = [node.text for node in ET.parse(source / NAMES[0]).iter("SensorName")]
assert sensors == ["imx400", "imx258"], sensors
for name in NAMES:
    ET.parse(source / name)

def adb(*argv):
    return subprocess.check_output(["adb", *argv], stderr=subprocess.PIPE)

assert adb("get-state").strip() == b"recovery", "Root TWRP required"
assert adb("shell", "id -u").strip() == b"0"
partition = "/dev/block/mmcblk0p53"
assert adb("shell", "readlink -f /dev/block/bootdevice/by-name/oem").strip().decode() == partition
assert int(adb("shell", f"blockdev --getsize64 {partition}")) == 400 * 1024 * 1024
args.backup_dir.mkdir(parents=True, exist_ok=True)
mount = "/tmp/codex-camera-vendor"
adb("shell", f"mkdir -p {mount} && mount -t ext4 {partition} {mount}")
try:
    for name in NAMES:
        destination = f"{mount}/etc/camera/{name}"
        if adb("shell", f"if [ -f {destination} ]; then echo yes; fi").strip() == b"yes":
            backup = args.backup_dir / name
            assert not backup.exists(), "Use a fresh backup directory"
            subprocess.run(["adb", "pull", destination, str(backup)], check=True)
        remote = f"/tmp/codex-{name}"
        subprocess.run(["adb", "push", str(source / name), remote], check=True)
        adb("shell", f"cat {remote} > {destination} && chown 0:0 {destination} && "
            f"chmod 0644 {destination} && chcon u:object_r:vendor_configs_file:s0 {destination} && sync")
        expected = hashlib.sha256((source / name).read_bytes()).hexdigest()
        actual = adb("shell", f"sha256sum {shlex.quote(destination)}").decode().split()[0]
        assert actual == expected, f"Read-back mismatch: {name}; do not reboot"
        print(f"Verified keyaki camera configuration: {name}")
finally:
    adb("shell", f"sync && umount {mount}")
print("All three XMLs installed and verified; reboot separately when ready")

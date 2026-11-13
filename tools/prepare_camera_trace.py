#!/usr/bin/env python3
"""Install an opt-in camera provider trace in a mounted vendor image.

Use a disposable image copy. Restore the original provider rc and remove the
two diagnostic files after collecting the trace; production builds omit them.
"""
import argparse
import os
import shutil
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("vendor", type=Path)
parser.add_argument("strace", type=Path)
parser.add_argument("--probe32", type=Path)
parser.add_argument("--probe64", type=Path)
args = parser.parse_args()
assert bool(args.probe32) == bool(args.probe64), "Provide both ABI probes"
rc = args.vendor / "etc/init/android.hardware.camera.provider@2.4-service.rc"
text = rc.read_text()
original = "/vendor/bin/hw/android.hardware.camera.provider@2.4-service"
assert "strace-camera" not in text, "Already instrumented"
assert f"service vendor.camera-provider-2-4 {original}\n" in text
rc.write_text(text.replace(
    f"service vendor.camera-provider-2-4 {original}\n",
    "service vendor.camera-provider-2-4 /vendor/bin/strace-camera -f -A -tt -s 160 "
    f"-o /data/local/tmp/codex-camera/provider.trace {original}\n"
    "    seclabel u:r:hal_camera_default:s0\n", 1))

binary = args.vendor / "bin/strace-camera"
shutil.copyfile(args.strace, binary)
os.chown(binary, 0, 2000)
os.chmod(binary, 0o755)
os.setxattr(binary, b"security.selinux", b"u:object_r:vendor_file:s0\0")
extra = args.vendor / "etc/init/codex-camera-trace.rc"
extra.write_text("""# Temporary diagnostic only; remove after collecting camera traces.
on post-fs-data
    mkdir /data/local/tmp/codex-camera 0755 cameraserver camera
    write /data/local/tmp/codex-camera/provider.trace "Camera provider diagnostic"
    chown cameraserver camera /data/local/tmp/codex-camera/provider.trace
    chmod 0644 /data/local/tmp/codex-camera/provider.trace
    setprop persist.vendor.camera.global.debug 5
    setprop persist.vendor.camera.hal.debug 5
    setprop persist.vendor.camera.mci.debug 5

# Bounded live retry for camera diagnostics; production builds omit this rc.
on property:debug.xzs.camera_restart=1
    restart vendor.camera-provider-2-4
    setprop debug.xzs.camera_restart 0
""")
if args.probe32:
    for bits, source in [(32, args.probe32), (64, args.probe64)]:
        target = args.vendor / f"bin/camera-media-probe{bits}"
        shutil.copyfile(source, target)
        os.chown(target, 0, 2000)
        os.chmod(target, 0o755)
        os.setxattr(target, b"security.selinux", b"u:object_r:vendor_file:s0\0")
    with extra.open("a") as stream:
        stream.write("""
on post-fs-data
    write /data/local/tmp/codex-camera/probe32.txt "pending"
    chown cameraserver camera /data/local/tmp/codex-camera/probe32.txt
    chmod 0644 /data/local/tmp/codex-camera/probe32.txt
    write /data/local/tmp/codex-camera/probe64.txt "pending"
    chown cameraserver camera /data/local/tmp/codex-camera/probe64.txt
    chmod 0644 /data/local/tmp/codex-camera/probe64.txt

service codex-camera-probe /vendor/bin/camera-media-probe64 /vendor/bin/camera-media-probe32
    user cameraserver
    group camera
    seclabel u:r:hal_camera_default:s0
    disabled
    oneshot

on property:sys.boot_completed=1
    start codex-camera-probe

on property:debug.xzs.camera_probe=1
    start codex-camera-probe
""")
os.chown(extra, 0, 0)
os.chmod(extra, 0o644)
os.setxattr(extra, b"security.selinux", os.getxattr(rc, b"security.selinux"))
print("Camera trace installed in disposable vendor image")

#!/usr/bin/env python3
"""
Helper to repack a TWRP ramdisk with the S1_Boot-verified Linux 5.4.302 keyaki kernel
and ConfigFS USB gadget initialization (/sbin/usb_54_init.sh).
"""
import os
import subprocess
import sys
from pathlib import Path

import cpio_root

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
RD = WORK / "twrp_rd"
KERNEL = ROOT / "prebuilt" / "Image.gz-dtb"
MKBOOTIMG = ROOT / "tools" / "mkbootimg" / "mkbootimg.py"
OUT_RD = ROOT / "out" / "components" / "twrp-keyaki-5.4-ramdisk.cpio.gz"
OUT_IMG = ROOT / "out" / "twrp-keyaki-5.4.img"

if not RD.is_dir():
    print(f"Unpack base TWRP ramdisk into {RD} before running this script.")
    sys.exit(1)

os.makedirs(RD / "config", exist_ok=True)

# 1. Patch init.rc: disable panic_on_oops, defer functionfs mount until after configfs ffs.adb exists
init_rc_path = RD / "init.rc"
init_rc = init_rc_path.read_text()
init_rc = init_rc.replace("write /proc/sys/kernel/panic_on_oops 1", "write /proc/sys/kernel/panic_on_oops 0")
init_rc = init_rc.replace(
    "mount functionfs adb /dev/usb-ffs/adb uid=2000,gid=2000",
    "# mounted after configfs in init.recovery.usb.rc",
)
if "service usb_54_init" not in init_rc:
    init_rc += """
service usb_54_init /sbin/usb_54_init.sh
    user root
    group root
    seclabel u:r:recovery:s0
    oneshot

on boot
    start usb_54_init
"""
init_rc_path.write_text(init_rc)

# 2. Ensure init.recovery.keyaki.rc exists alongside init.recovery.qcom.rc
qcom_rc_path = RD / "init.recovery.qcom.rc"
keyaki_rc_path = RD / "init.recovery.keyaki.rc"
qcom_rc = qcom_rc_path.read_text()
if "mmcblk0rpmb" not in qcom_rc:
    qcom_rc += """
on early-fs
    symlink /dev/mmcblk0rpmb /dev/block/mmcblk0rpmb
"""
keyaki_rc_path.write_text(qcom_rc)
os.chmod(keyaki_rc_path, 0o750)

# 3. Write clean ConfigFS init.recovery.usb.rc for Linux 5.4
usb_rc = """on fs
    mkdir /config 0775 root root
    mount configfs none /config
    mkdir /config/usb_gadget/g1 0770 shell shell
    mkdir /config/usb_gadget/g1/strings/0x409 0770 shell shell
    write /config/usb_gadget/g1/idVendor 0x0fce
    write /config/usb_gadget/g1/idProduct 0x51e7
    write /config/usb_gadget/g1/bcdDevice 0x0223
    write /config/usb_gadget/g1/bcdUSB 0x0200
    write /config/usb_gadget/g1/os_desc/use 1
    write /config/usb_gadget/g1/strings/0x409/serialnumber ${ro.serialno}
    write /config/usb_gadget/g1/strings/0x409/manufacturer "Sony"
    write /config/usb_gadget/g1/strings/0x409/product "Xperia XZs"
    mkdir /config/usb_gadget/g1/functions/mtp.gs0
    mkdir /config/usb_gadget/g1/functions/ffs.adb
    mkdir /config/usb_gadget/g1/configs/b.1 0770 shell shell
    mkdir /config/usb_gadget/g1/configs/b.1/strings/0x409 0770 shell shell
    write /config/usb_gadget/g1/os_desc/b_vendor_code 0x1
    write /config/usb_gadget/g1/os_desc/qw_sign "MSFT100"
    write /config/usb_gadget/g1/configs/b.1/MaxPower 500
    symlink /config/usb_gadget/g1/configs/b.1 /config/usb_gadget/g1/os_desc/b.1
    mkdir /dev/usb-ffs 0770 shell shell
    mkdir /dev/usb-ffs/adb 0770 shell shell
    mount functionfs adb /dev/usb-ffs/adb uid=2000,gid=2000
    setprop sys.usb.configfs 1
    setprop sys.usb.controller 6a00000.dwc3

on boot
    write /sys/devices/platform/soc/6a00000.ssusb/mode peripheral

on property:sys.usb.config=none
    write /config/usb_gadget/g1/UDC "none"
    setprop sys.usb.state ${sys.usb.config}

on property:sys.usb.config=adb
    start adbd

on property:sys.usb.ffs.ready=1 && property:sys.usb.config=adb
    write /config/usb_gadget/g1/configs/b.1/strings/0x409/configuration "adb"
    rm /config/usb_gadget/g1/configs/b.1/f1
    rm /config/usb_gadget/g1/configs/b.1/f2
    write /config/usb_gadget/g1/idVendor 0x0fce
    write /config/usb_gadget/g1/idProduct 0x51e7
    symlink /config/usb_gadget/g1/functions/ffs.adb /config/usb_gadget/g1/configs/b.1/f1
    write /config/usb_gadget/g1/UDC 6a00000.dwc3
    write /sys/devices/platform/soc/6a00000.ssusb/mode peripheral
    setprop sys.usb.state ${sys.usb.config}

on property:sys.usb.config=mtp,adb
    start adbd

on property:sys.usb.ffs.ready=1 && property:sys.usb.config=mtp,adb
    write /config/usb_gadget/g1/configs/b.1/strings/0x409/configuration "mtp_adb"
    rm /config/usb_gadget/g1/configs/b.1/f1
    rm /config/usb_gadget/g1/configs/b.1/f2
    write /config/usb_gadget/g1/idVendor 0x0fce
    write /config/usb_gadget/g1/idProduct 0x51e7
    symlink /config/usb_gadget/g1/functions/mtp.gs0 /config/usb_gadget/g1/configs/b.1/f1
    symlink /config/usb_gadget/g1/functions/ffs.adb /config/usb_gadget/g1/configs/b.1/f2
    write /config/usb_gadget/g1/UDC 6a00000.dwc3
    write /sys/devices/platform/soc/6a00000.ssusb/mode peripheral
    setprop sys.usb.state ${sys.usb.config}
"""
(RD / "init.recovery.usb.rc").write_text(usb_rc)

# 4. Write fallback /sbin/usb_54_init.sh reading runtime serial number via getprop
usb_sh = """#!/sbin/sh
echo peripheral > /sys/devices/platform/soc/6a00000.ssusb/mode
ln -sf /dev/block/platform/soc/7464900.sdhci /dev/block/bootdevice
mkdir -p /config
mount -t configfs none /config 2>/dev/null
mkdir -p /config/usb_gadget/g1/strings/0x409
mkdir -p /config/usb_gadget/g1/functions/ffs.adb
mkdir -p /config/usb_gadget/g1/functions/mtp.gs0
mkdir -p /config/usb_gadget/g1/configs/b.1/strings/0x409
echo 0x0fce > /config/usb_gadget/g1/idVendor
echo 0x51e7 > /config/usb_gadget/g1/idProduct
echo 0x0200 > /config/usb_gadget/g1/bcdUSB
SER=$(getprop ro.serialno)
[ -z "$SER" ] && SER="keyaki-recovery"
echo "$SER" > /config/usb_gadget/g1/strings/0x409/serialnumber
echo "Sony" > /config/usb_gadget/g1/strings/0x409/manufacturer
echo "Xperia XZs" > /config/usb_gadget/g1/strings/0x409/product
echo "adb" > /config/usb_gadget/g1/configs/b.1/strings/0x409/configuration
mkdir -p /dev/usb-ffs/adb
mount -t functionfs adb /dev/usb-ffs/adb -o uid=2000,gid=2000 2>/dev/null
start adbd
sleep 2
ln -sf /config/usb_gadget/g1/functions/ffs.adb /config/usb_gadget/g1/configs/b.1/f1
UDC_VAL=$(cat /config/usb_gadget/g1/UDC 2>/dev/null)
if [ -z "$UDC_VAL" ] || [ "$UDC_VAL" = "none" ]; then
    echo 6a00000.dwc3 > /config/usb_gadget/g1/UDC
fi
echo peripheral > /sys/devices/platform/soc/6a00000.ssusb/mode
"""
usb_sh_path = RD / "sbin" / "usb_54_init.sh"
usb_sh_path.write_text(usb_sh)
os.chmod(usb_sh_path, 0o750)

# 5. Update default.prop to ensure insecure root adb in recovery
prop_path = RD / "default.prop"
prop = prop_path.read_text()
prop = prop.replace("ro.adb.secure=1", "ro.adb.secure=0").replace("ro.secure=1", "ro.secure=0")
if "sys.usb.configfs=1" not in prop:
    prop += "\nsys.usb.configfs=1\nsys.usb.controller=6a00000.dwc3\nro.adb.secure=0\nro.secure=0\n"
prop_path.write_text(prop)

# 6. Repack ramdisk using cpio_root.py
cpio_root.pack_cpio_gz(str(RD), str(OUT_RD))

# 7. Pack boot image with keyaki 5.4 kernel + exact keyaki offsets
cmdline = (
    "androidboot.bootdevice=7464900.sdhci androidboot.selinux=permissive enforcing=0 "
    "msm_rtb.filter=0x3F ehci-hcd.park=3 coherent_pool=8M "
    "sched_enable_power_aware=1 user_debug=31 cgroup.memory=nokmem "
    "printk.devkmsg=on kpti=0 androidboot.hardware=keyaki "
    "buildvariant=userdebug log_buf_len=4M firmware_class.path=/vendor/firmware"
)
subprocess.run(
    [
        "python3",
        str(MKBOOTIMG),
        "--kernel",
        str(KERNEL),
        "--ramdisk",
        str(OUT_RD),
        "--header_version",
        "0",
        "--base",
        "0x80000000",
        "--kernel_offset",
        "0x8000",
        "--ramdisk_offset",
        "0x2000000",
        "--tags_offset",
        "0x1e00000",
        "--pagesize",
        "4096",
        "--os_version",
        "10.0.0",
        "--os_patch_level",
        "2020-03",
        "--cmdline",
        cmdline,
        "-o",
        str(OUT_IMG),
    ],
    check=True,
)
print("Built:", OUT_IMG, os.path.getsize(OUT_IMG))

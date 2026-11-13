#!/bin/bash
set -euo pipefail

OUT_OEM="/work/out/oem-a17-keyaki.img"
OUT_OEM_SPARSE="/work/out/oem-a17-keyaki.sparse.img"
mkdir -p /work/out
cp /work/backup/oem.img "$OUT_OEM"
e2fsck -fy "$OUT_OEM" >/dev/null 2>&1 || true

MNT="/tmp/mnt_oem_edit"
rm -rf "$MNT"
mkdir -p "$MNT"
mount -o loop,rw "$OUT_OEM" "$MNT"
trap 'umount "$MNT" 2>/dev/null || true' EXIT

set_ctx() {
    local path="$1" ctx="$2"
    python3 -c 'import os,sys; os.setxattr(sys.argv[1], b"security.selinux", sys.argv[2].rstrip("\x00\n").encode()+b"\x00", follow_symlinks=False)' "$path" "$ctx"
}

get_ctx() {
    python3 -c 'import os,sys; print(os.getxattr(sys.argv[1], b"security.selinux", follow_symlinks=False).rstrip(b"\x00\n").decode())' "$1" 2>/dev/null || echo "$2"
}

install_vfile() {
    local src="$1" dst="$2" mode="$3" ctx="$4"
    mkdir -p "$(dirname "$dst")"
    cp -f "$src" "$dst"
    chown 0:0 "$dst"
    chmod "$mode" "$dst"
    set_ctx "$dst" "$ctx"
}

echo "1. Installing Linux 5.4.302 audio DLKM modules (17 modules incl. wcd_cpe_dlkm)..."
rm -rf "$MNT/lib/modules"
mkdir -p "$MNT/lib/modules"
chown 0:0 "$MNT/lib/modules"
chmod 0755 "$MNT/lib/modules"
set_ctx "$MNT/lib/modules" "u:object_r:vendor_file:s0"
for ko in /work/out/kernel_a17/modules/*.ko; do
    install_vfile "$ko" "$MNT/lib/modules/$(basename "$ko")" 0644 "u:object_r:vendor_file:s0"
done

echo "2. Installing BCM4359 PCIe Wi-Fi firmware + board-specific NVRAM for brcmfmac..."
FW_CTX=$(get_ctx "$MNT/firmware/BCM4359C0.hcd" "u:object_r:vendor_firmware_file:s0")
mkdir -p "$MNT/firmware/brcm"
chown 0:0 "$MNT/firmware/brcm"
chmod 0755 "$MNT/firmware/brcm"
set_ctx "$MNT/firmware/brcm" "$FW_CTX"
install_vfile /work/base_rom/brcmfmac4359-pcie.bin "$MNT/firmware/brcm/brcmfmac4359-pcie.bin" 0644 "$FW_CTX"
install_vfile /work/base_rom/brcmfmac4359-pcie.txt "$MNT/firmware/brcm/brcmfmac4359-pcie.txt" 0644 "$FW_CTX"
for compat in "somc,keyaki-row" "somc,keyaki" "qcom,msm8996"; do
    install_vfile /work/base_rom/brcmfmac4359-pcie.txt "$MNT/firmware/brcm/brcmfmac4359-pcie.${compat}.txt" 0644 "$FW_CTX"
done

echo "2b. Patching Wi-Fi HAL bcmdhd firmware_path write -> /dev/null for brcmfmac..."
python3 - "$MNT" << 'PY'
import glob, os, sys
mnt = sys.argv[1]
needle = b"/sys/module/bcmdhd/parameters/firmware_path\x00"
repl = b"/dev/null\x00" + b"\x00" * (len(needle) - 10)
assert len(needle) == len(repl)
targets = glob.glob(f"{mnt}/bin/hw/*wifi*") + glob.glob(f"{mnt}/lib*/*wifi*")
for p in targets:
    if not os.path.isfile(p) or os.path.islink(p):
        continue
    data = open(p, "rb").read()
    if needle in data:
        ctx = os.getxattr(p, b"security.selinux", follow_symlinks=False)
        st = os.stat(p)
        data = data.replace(needle, repl)
        open(p, "wb").write(data)
        os.chown(p, st.st_uid, st.st_gid)
        os.chmod(p, st.st_mode & 0o7777)
        os.setxattr(p, b"security.selinux", ctx, follow_symlinks=False)
        print("  Patched bcmdhd firmware_path -> /dev/null in:", p)
PY

echo "2c. Patching libbt-vendor.so (BCM4359C0 UART LPM Sleep_Mode=0 & UPIO_BT_WAKE no-op for 5.4 kernel without msm_bt_sleep)..."
python3 - "$MNT/lib64/libbt-vendor.so" << 'PY'
import os, sys
p = sys.argv[1]
ctx = os.getxattr(p, b"security.selinux", follow_symlinks=False)
st = os.stat(p)
b = bytearray(open(p, "rb").read())
assert bytes(b[0x64d8:0x64e4]) == bytes([1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0]), "Unexpected LPM param table at 0x64d8"
assert bytes(b[0x5488:0x548c]) == bytes.fromhex("080000d0"), "Unexpected upio_set instruction at 0x5488"
b[0x64d8:0x64e4] = bytes([0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
b[0x5488:0x548c] = bytes.fromhex("c0035fd6")
open(p, "wb").write(b)
os.chown(p, st.st_uid, st.st_gid)
os.chmod(p, st.st_mode & 0o7777)
os.setxattr(p, b"security.selinux", ctx, follow_symlinks=False)
print("  Patched BCM4359C0 UART LPM in:", p)
PY

echo "3. Installing keyaki + 5.4 init, USB ConfigFS, ueventd, fstab, audio & input configs..."
RC_CTX=$(get_ctx "$MNT/etc/init/hw/init.qcom.rc" "u:object_r:vendor_configs_file:s0")
ETC_CTX=$(get_ctx "$MNT/etc/fstab.qcom" "u:object_r:vendor_configs_file:s0")

install_vfile /work/base_rom/device-tone-common/rootdir/etc/init.qcom.rc "$MNT/etc/init/hw/init.qcom.rc" 0644 "$RC_CTX"
install_vfile /work/base_rom/device-tone-common/rootdir/etc/init.qcom.usb.rc "$MNT/etc/init/hw/init.qcom.usb.rc" 0644 "$RC_CTX"
install_vfile /work/base_rom/device-tone-common/rootdir/etc/init.qcom.power.rc "$MNT/etc/init/hw/init.qcom.power.rc" 0644 "$RC_CTX"
install_vfile /work/base_rom/device-keyaki/rootdir/etc/init.target.rc "$MNT/etc/init/hw/init.target.rc" 0644 "$RC_CTX"
install_vfile /work/base_rom/device-tone-common/rootdir/etc/ueventd.qcom.rc "$MNT/ueventd.rc" 0644 "$ETC_CTX"
install_vfile /work/base_rom/device-tone-common/rootdir/etc/ueventd.qcom.rc "$MNT/etc/ueventd.rc" 0644 "$ETC_CTX"

# Patch init.qcom.rc so RPMB block symlink exists BEFORE vendor.qseecomd starts in 'on init'
python3 - "$MNT/etc/init/hw/init.qcom.rc" << 'PY'
import sys
p = sys.argv[1]
s = open(p).read()
s = s.replace(
    "    start vendor.qseecomd",
    "    chown root system /dev/mmcblk0rpmb\n    chmod 0660 /dev/mmcblk0rpmb\n    symlink /dev/mmcblk0rpmb /dev/block/mmcblk0rpmb\n    start vendor.qseecomd"
)
open(p, "w").write(s)
PY
set_ctx "$MNT/etc/init/hw/init.qcom.rc" "$RC_CTX"

# Patch init.qcom.usb.rc: early ConfigFS gadget g1 in 'on post-fs' + Google ADB PID 0x4EE7 + forced dwc3 peripheral
python3 - "$MNT/etc/init/hw/init.qcom.usb.rc" << 'PY'
import sys, re
p = sys.argv[1]
s = open(p).read()
s = s.replace("on boot\n", "on post-fs\n", 1)
s = s.replace(
    '    setprop sys.usb.rmnet.func.name "rmnet_bam"\n',
    '    setprop sys.usb.rmnet.func.name "rmnet_bam"\n    write /sys/devices/platform/soc/6a00000.ssusb/mode peripheral\n    setprop sys.usb.config adb\n',
    1
)
s = re.sub(
    r"# Completely redeclare ADB for safety purposes.*?setprop sys\.usb\.state \$\{sys\.usb\.config\}",
    "# Set Google ADB PID 0x4EE7 before init.usb.configfs.rc binds UDC on ffs.ready=1\n"
    "on property:sys.usb.config=adb && property:sys.usb.configfs=1\n"
    "    write /config/usb_gadget/g1/idProduct 0x4EE7\n"
    "    write /sys/devices/platform/soc/6a00000.ssusb/mode peripheral",
    s,
    flags=re.DOTALL,
)
open(p, "w").write(s)
PY
set_ctx "$MNT/etc/init/hw/init.qcom.usb.rc" "$RC_CTX"

install_vfile /work/configs/init/init.keyaki.rc "$MNT/etc/init/hw/init.keyaki.rc" 0644 "$RC_CTX"
install_vfile /work/configs/fstab/fstab.keyaki "$MNT/etc/fstab.keyaki" 0644 "$ETC_CTX"
install_vfile /work/configs/fstab/fstab.keyaki "$MNT/etc/fstab.qcom" 0644 "$ETC_CTX"

install_vfile /work/base_rom/device-keyaki/audio/audio_platform_info.xml "$MNT/etc/audio_platform_info.xml" 0644 "$ETC_CTX"
install_vfile /work/base_rom/device-keyaki/audio/mixer_paths_tasha.xml "$MNT/etc/mixer_paths_tasha.xml" 0644 "$ETC_CTX"
install_vfile /work/base_rom/device-keyaki/idc/clearpad.idc "$MNT/usr/idc/clearpad.idc" 0644 "u:object_r:vendor_file:s0"

# The donor vendor contains kagura IMX300/IMX214 settings. SO-03J keyaki
# reports IMX400/IMX258 IDs; install the matching device camera XMLs.
for camera_xml in /work/base_rom/device-keyaki/rootdir/vendor/etc/camera/*.xml; do
    install_vfile "$camera_xml" "$MNT/etc/camera/$(basename "$camera_xml")" 0644 "$ETC_CTX"
done
install_vfile /work/configs/init/init.keyaki.camera.rc "$MNT/etc/init/init.keyaki.camera.rc" 0644 "$RC_CTX"

echo "3b. Removing broken services (thermanager GPU throttle bug, configstore@1.1, stale precompiled_sepolicy)..."
rm -f "$MNT/etc/init/thermanager.rc" "$MNT/bin/thermanager"
rm -f "$MNT/etc/init/android.hardware.configstore@1.1-service.rc" "$MNT/bin/hw/android.hardware.configstore@1.1-service"
rm -f "$MNT/etc/selinux/precompiled_sepolicy"*

echo "4. Updating /vendor/etc/vintf/manifest.xml (target-level=5, mapper@2.0 only, display.config@1.9, no configstore)..."
MANIFEST_CTX=$(get_ctx "$MNT/etc/vintf/manifest.xml" "$ETC_CTX")
python3 - "$MNT/etc/vintf/manifest.xml" << 'PY'
import re, sys
p = sys.argv[1]
s = open(p).read()
s = s.replace('target-level="legacy"', 'target-level="5"')
s = re.sub(r"\s*<hal format=\"hidl\">\s*<name>android\.hardware\.configstore</name>.*?</hal>", "", s, flags=re.DOTALL)
s = re.sub(r"\s*<fqname>@[34]\.0::IMapper/default</fqname>", "", s)
s = re.sub(
    r"(<name>vendor\.display\.config</name>.*?<version>)1\.1(</version>.*?<fqname>@)1\.1(::IDisplayConfig/default</fqname>)",
    r"\g<1>1.9\g<2>1.9\g<3>",
    s,
    flags=re.DOTALL,
)
open(p, "w").write(s)
PY
chown 0:0 "$MNT/etc/vintf/manifest.xml"
chmod 0644 "$MNT/etc/vintf/manifest.xml"
set_ctx "$MNT/etc/vintf/manifest.xml" "$MANIFEST_CTX"

echo "5. Updating vendor build.prop & default.prop (preserving SELinux xattrs)..."
BP_CTX=$(get_ctx "$MNT/build.prop" "u:object_r:vendor_file:s0")
python3 - "$MNT/build.prop" /work/configs/props/vendor_keyaki.prop << 'PY'
import sys
p, extra_p = sys.argv[1], sys.argv[2]
with open(p, "r") as f:
    s = f.read()
s = s.replace("ro.product.vendor.device=kagura", "ro.product.vendor.device=keyaki")
s = s.replace("ro.product.vendor.model=Xperia XZ", "ro.product.vendor.model=Xperia XZs (SO-03J)")
s = s.replace("ro.product.vendor.name=lineage_kagura", "ro.product.vendor.name=aosp_keyaki")
s = s.replace("ro.hwui.use_vulkan=", "ro.hwui.use_vulkan=false")
s = s.replace("persist.hwc.enable_vds=1", "#persist.hwc.enable_vds=1")
extra = "\n" + open(extra_p, "r").read().strip() + "\n"
if "sys.usb.controller=6a00000.dwc3" not in s:
    s += extra
with open(p, "w") as f:
    f.write(s)
PY
chown 0:0 "$MNT/build.prop"
chmod 0600 "$MNT/build.prop"
set_ctx "$MNT/build.prop" "$BP_CTX"

if [ -f "$MNT/default.prop" ]; then
    DP_CTX=$(get_ctx "$MNT/default.prop" "u:object_r:vendor_file:s0")
    grep -q "ro.vndk.version=30" "$MNT/default.prop" || echo "ro.vndk.version=30" >> "$MNT/default.prop"
    set_ctx "$MNT/default.prop" "$DP_CTX"
fi

echo "6. Auditing SELinux xattrs across entire /vendor image..."
python3 - "$MNT" << 'PY'
import os, sys
mnt = sys.argv[1]
missing = []
for root, dirs, files in os.walk(mnt, followlinks=False):
    for name in dirs + files:
        if name == "lost+found":
            continue
        p = os.path.join(root, name)
        try:
            os.getxattr(p, b"security.selinux", follow_symlinks=False)
        except OSError:
            missing.append(p)
if missing:
    print("ERROR: Unlabeled files in /vendor:", missing[:20])
    sys.exit(1)
print("SELinux xattr audit PASSED: 0 unlabeled entries in /vendor!")
PY

df -h "$MNT"
umount "$MNT"
trap - EXIT
e2fsck -fy "$OUT_OEM" >/dev/null 2>&1 || true
rm -f "$OUT_OEM_SPARSE"
img2simg "$OUT_OEM" "$OUT_OEM_SPARSE"
echo "SUCCESS: Built $OUT_OEM and $OUT_OEM_SPARSE"
ls -lh "$OUT_OEM" "$OUT_OEM_SPARSE"

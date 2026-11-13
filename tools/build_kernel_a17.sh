#!/bin/bash
set -euo pipefail

DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git rsync >/dev/null

rm -rf /root/sov35-kernel /root/kout
git clone /work/kernel/sov35-kernel /root/sov35-kernel
cd /root/sov35-kernel
git reset --hard HEAD

# 1. Patch Device Tree fstab flags to include first_stage_mount for Android 17 2SI
python3 - <<'PY'
p = "arch/arm64/boot/dts/qcom/msm8996-tone-common.dtsi"
with open(p, "r") as f:
    s = f.read()
target = 'fsmgr_flags = "wait";'
assert target in s, "fsmgr_flags not found"
s = s.replace(target, 'fsmgr_flags = "wait,first_stage_mount";')
with open(p, "w") as f:
    f.write(s)
print("Patched DT first_stage_mount successfully")
PY

# 2. Append Android 17 kernel config requirements from configs/kernel/android17_54.fragment
cat /work/configs/kernel/android17_54.fragment >> arch/arm64/configs/aosp_tone_keyaki_defconfig

export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
JOBS=$(nproc)

make -C /root/sov35-kernel O=/root/kout aosp_tone_keyaki_defconfig
make -C /root/sov35-kernel O=/root/kout olddefconfig

echo "=== VERIFYING EFFECTIVE .config FLAGS ==="
grep -E "CONFIG_(BPF_EVENTS|NET_ACT_BPF|DEBUG_INFO_BTF|UPROBE_EVENTS|IKCONFIG_PROC|EROFS_FS|OVERLAY_FS|CGROUP_BPF|ANDROID_BINDERFS)=" /root/kout/.config

make -C /root/sov35-kernel O=/root/kout -j"$JOBS" Image.gz-dtb modules

mkdir -p /work/out/kernel_a17/modules
cp /root/kout/arch/arm64/boot/Image.gz-dtb /work/out/kernel_a17/Image.gz-dtb
find /root/kout/techpack -name '*_dlkm.ko' | while read -r m; do
    aarch64-linux-gnu-strip --strip-debug -o "/work/out/kernel_a17/modules/$(basename "$m")" "$m"
done

echo "=== KERNEL BUILD COMPLETE ==="
ls -lh /work/out/kernel_a17/Image.gz-dtb /work/out/kernel_a17/modules/

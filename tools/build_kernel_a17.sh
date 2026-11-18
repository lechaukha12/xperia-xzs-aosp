#!/bin/bash
set -euo pipefail

DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git rsync >/dev/null

rm -rf /root/sov35-kernel /root/kout
git clone /work/kernel/sov35-kernel /root/sov35-kernel
cd /root/sov35-kernel
git reset --hard HEAD

# 1. Patch Device Tree fstab flags and RGB LED names + V4L2/Media Controller compatibility for Camera
python3 - <<'PY'
# 1a. Patch first_stage_mount in msm8996-tone-common.dtsi
p = "arch/arm64/boot/dts/qcom/msm8996-tone-common.dtsi"
with open(p, "r") as f:
    s = f.read()
target = 'fsmgr_flags = "wait";'
assert target in s, "fsmgr_flags not found"
s = s.replace(target, 'fsmgr_flags = "wait,first_stage_mount";')
with open(p, "w") as f:
    f.write(s)
print("Patched DT first_stage_mount successfully")

# 1b. Patch RGB LED sysfs names in msm8996-tone-keyaki-common.dtsi for Lights HAL
p_led = "arch/arm64/boot/dts/qcom/msm8996-tone-keyaki-common.dtsi"
with open(p_led, "r") as f:
    s = f.read()
for old, new in [
    ('linux,name = "led:rgb_red";', 'linux,name = "red";'),
    ('linux,name = "led:rgb_green";', 'linux,name = "green";'),
    ('linux,name = "led:rgb_blue";', 'linux,name = "blue";'),
]:
    assert old in s, f"{old} not found in {p_led}"
    s = s.replace(old, new, 1)
with open(p_led, "w") as f:
    f.write(s)
print("Patched DT RGB LED names (red/green/blue) successfully")

# 1c. Preserve legacy camera_v2 entity.function (QCAMERA_VNODE_GROUP_ID) in v4l2-dev.c
p_v4l2 = "drivers/media/v4l2-core/v4l2-dev.c"
with open(p_v4l2, "r") as f:
    s = f.read()
old_v4l2 = """\tvdev->entity.obj_type = MEDIA_ENTITY_TYPE_VIDEO_DEVICE;
\tvdev->entity.function = MEDIA_ENT_F_UNKNOWN;

\tswitch (vdev->vfl_type) {
\tcase VFL_TYPE_VIDEO:
\t\tintf_type = MEDIA_INTF_T_V4L_VIDEO;
\t\tvdev->entity.function = MEDIA_ENT_F_IO_V4L;
\t\tbreak;"""
new_v4l2 = """\tvdev->entity.obj_type = MEDIA_ENTITY_TYPE_VIDEO_DEVICE;
\tif (vdev->entity.function == 0)
\t\tvdev->entity.function = MEDIA_ENT_F_UNKNOWN;

\tswitch (vdev->vfl_type) {
\tcase VFL_TYPE_VIDEO:
\t\tintf_type = MEDIA_INTF_T_V4L_VIDEO;
\t\tif (vdev->entity.function == MEDIA_ENT_F_UNKNOWN)
\t\t\tvdev->entity.function = MEDIA_ENT_F_IO_V4L;
\t\tbreak;"""
assert old_v4l2 in s, "v4l2-dev.c target not found"
s = s.replace(old_v4l2, new_v4l2, 1)
with open(p_v4l2, "w") as f:
    f.write(s)
print("Patched v4l2-dev.c entity.function preservation successfully")

# 1d. Map legacy camera_v2 entity ID (media_id), group_id & entity type in mc-device.c (MEDIA_IOC_ENUM_ENTITIES)
p_mc = "drivers/media/mc/mc-device.c"
with open(p_mc, "r") as f:
    s = f.read()
old_mc = """static struct media_entity *find_entity(struct media_device *mdev, u32 id)
{
\tstruct media_entity *entity;
\tint next = id & MEDIA_ENT_ID_FLAG_NEXT;

\tid &= ~MEDIA_ENT_ID_FLAG_NEXT;

\tmedia_device_for_each_entity(entity, mdev) {
\t\tif (((media_entity_id(entity) == id) && !next) ||
\t\t    ((media_entity_id(entity) > id) && next)) {
\t\t\treturn entity;
\t\t}
\t}

\treturn NULL;
}

static long media_device_enum_entities(struct media_device *mdev, void *arg)
{
\tstruct media_entity_desc *entd = arg;
\tstruct media_entity *ent;

\tent = find_entity(mdev, entd->id);
\tif (ent == NULL)
\t\treturn -EINVAL;

\tmemset(entd, 0, sizeof(*entd));

\tentd->id = media_entity_id(ent);
\tif (ent->name)
\t\tstrscpy(entd->name, ent->name, sizeof(entd->name));
\tentd->type = ent->function;
\tentd->revision = 0;\t\t/* Unused */
\tentd->flags = ent->flags;
\tentd->group_id = 0;\t\t/* Unused */
\tentd->pads = ent->num_pads;
\tentd->links = ent->num_links - ent->num_backlinks;

\t/*
\t * Workaround for a bug at media-ctl <= v1.10 that makes it to
\t * do the wrong thing if the entity function doesn't belong to
\t * either MEDIA_ENT_F_OLD_BASE or MEDIA_ENT_F_OLD_SUBDEV_BASE
\t * Ranges.
\t *
\t * Non-subdevices are expected to be at the MEDIA_ENT_F_OLD_BASE,
\t * or, otherwise, will be silently ignored by media-ctl when
\t * printing the graphviz diagram. So, map them into the devnode
\t * old range.
\t */
\tif (ent->function < MEDIA_ENT_F_OLD_BASE ||
\t    ent->function > MEDIA_ENT_F_TUNER) {
\t\tif (is_media_entity_v4l2_subdev(ent))
\t\t\tentd->type = MEDIA_ENT_F_V4L2_SUBDEV_UNKNOWN;
\t\telse if (ent->function != MEDIA_ENT_F_IO_V4L)
\t\t\tentd->type = MEDIA_ENT_T_DEVNODE_UNKNOWN;
\t}"""
new_mc = """static struct media_entity *find_entity(struct media_device *mdev, u32 id)
{
\tstruct media_entity *entity;
\tint next = id & MEDIA_ENT_ID_FLAG_NEXT;

\tid &= ~MEDIA_ENT_ID_FLAG_NEXT;

\tmedia_device_for_each_entity(entity, mdev) {
\t\tu32 eid = media_id(&entity->graph_obj);
\t\tif (((eid == id) && !next) ||
\t\t    ((eid > id) && next)) {
\t\t\treturn entity;
\t\t}
\t}

\treturn NULL;
}

static long media_device_enum_entities(struct media_device *mdev, void *arg)
{
\tstruct media_entity_desc *entd = arg;
\tstruct media_entity *ent;

\tent = find_entity(mdev, entd->id);
\tif (ent == NULL)
\t\treturn -EINVAL;

\tmemset(entd, 0, sizeof(*entd));

\tentd->id = media_id(&ent->graph_obj);
\tif (ent->name)
\t\tstrscpy(entd->name, ent->name, sizeof(entd->name));
\tentd->type = ent->function;
\tentd->revision = 0;\t\t/* Unused */
\tentd->flags = ent->flags;
\tentd->group_id = 0;\t\t/* Unused */
\tentd->pads = ent->num_pads;
\tentd->links = ent->num_links - ent->num_backlinks;

\tif (ent->function > 0 && ent->function < MEDIA_ENT_F_OLD_BASE) {
\t\tentd->group_id = ent->function;
\t\tif (is_media_entity_v4l2_subdev(ent))
\t\t\tentd->type = MEDIA_ENT_F_V4L2_SUBDEV_UNKNOWN;
\t\telse
\t\t\tentd->type = MEDIA_ENT_F_IO_V4L;
\t} else if (ent->function < MEDIA_ENT_F_OLD_BASE ||
\t    ent->function > MEDIA_ENT_F_TUNER) {
\t\tif (is_media_entity_v4l2_subdev(ent))
\t\t\tentd->type = MEDIA_ENT_F_V4L2_SUBDEV_UNKNOWN;
\t\telse if (ent->function != MEDIA_ENT_F_IO_V4L)
\t\t\tentd->type = MEDIA_ENT_T_DEVNODE_UNKNOWN;
\t}"""
assert old_mc in s, "mc-device.c target not found"
s = s.replace(old_mc, new_mc, 1)
with open(p_mc, "w") as f:
    f.write(s)
print("Patched mc-device.c legacy camera_v2 media_id, group_id & type mapping successfully")
PY

# The tree's real camera subdevice functions use 0x10f00, not small integers.
python3 /work/tools/patch_camera_media_legacy.py /root/sov35-kernel

# 2. Append Android 17 kernel config requirements from configs/kernel/android17_54.fragment
cat /work/configs/kernel/android17_54.fragment >> arch/arm64/configs/aosp_tone_keyaki_defconfig

export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
JOBS=$(nproc)

make -C /root/sov35-kernel O=/root/kout aosp_tone_keyaki_defconfig
make -C /root/sov35-kernel O=/root/kout olddefconfig

echo "=== VERIFYING EFFECTIVE .config FLAGS ==="
grep -E "CONFIG_(BPF_EVENTS|NET_ACT_BPF|DEBUG_INFO_BTF|UPROBE_EVENTS|IKCONFIG_PROC|CC_OPTIMIZE_FOR_SIZE|CGROUP_BPF|ANDROID_BINDERFS)=" /root/kout/.config

make -C /root/sov35-kernel O=/root/kout -j"$JOBS" Image.gz-dtb modules

mkdir -p /work/out/kernel_a17/modules
cp /root/kout/arch/arm64/boot/Image.gz-dtb /work/out/kernel_a17/Image.gz-dtb
find /root/kout/techpack -name '*_dlkm.ko' | while read -r m; do
    aarch64-linux-gnu-strip --strip-debug -o "/work/out/kernel_a17/modules/$(basename "$m")" "$m"
done

echo "=== KERNEL BUILD COMPLETE ==="
ls -lh /work/out/kernel_a17/Image.gz-dtb /work/out/kernel_a17/modules/

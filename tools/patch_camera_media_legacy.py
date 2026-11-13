#!/usr/bin/env python3
"""Expose the tone camera_v2 legacy entity groups through ENUM_ENTITIES.

The 5.4 driver encodes private subdevice kinds in entity.function at 0x10f00.
The shipped 32-bit HAL searches for type 0x20000 plus the old numeric group_id.
Keep modern topology functions unchanged. Translate the msm_config subdevices
and the msm_config/msm_camera video nodes only.
"""
import argparse
from pathlib import Path

MARKER = "/* keyaki: camera_v2 legacy ENUM_ENTITIES ABI */"
OLD = "\tif (ent->function > 0 && ent->function < MEDIA_ENT_F_OLD_BASE) {"
NEW = """\t/* keyaki: camera_v2 legacy ENUM_ENTITIES ABI */
\tif (!strcmp(mdev->model, "msm_config") &&
\t    ent->function >= MEDIA_ENT_F_OLD_BASE + 0xf00 &&
\t    ent->function <= MEDIA_ENT_F_OLD_BASE + 0xf15) {
\t\tu32 group = ent->function - (MEDIA_ENT_F_OLD_BASE + 0xf00);

\t\t/* This tree swapped CSID and BUF_MNGR when encoding function. */
\t\tif (group == 13)
\t\t\tgroup = 1;
\t\telse if (group == 1)
\t\t\tgroup = 13;
\t\tentd->group_id = group;
\t\tentd->type = MEDIA_ENT_F_V4L2_SUBDEV_UNKNOWN;
\t} else if ((!strcmp(mdev->model, "msm_config") ||
\t\t    !strcmp(mdev->model, "msm_camera")) &&
\t\t   ent->function == MEDIA_ENT_F_IO_V4L) {
\t\tentd->group_id = 2; /* legacy QCAMERA_VNODE_GROUP_ID */
\t} else if (ent->function > 0 && ent->function < MEDIA_ENT_F_OLD_BASE) {"""


def patch(root: Path) -> bool:
    path = root / "drivers/media/mc/mc-device.c"
    text = path.read_text()
    if MARKER in text:
        old_video = '\t} else if (!strcmp(mdev->model, "msm_config") &&\n'
        new_video = ('\t} else if ((!strcmp(mdev->model, "msm_config") ||\n'
                     '\t\t    !strcmp(mdev->model, "msm_camera")) &&\n')
        if old_video not in text:
            assert new_video in text, "Unknown version of the camera mapping patch"
            return False
        path.write_text(text.replace(old_video, new_video, 1))
        return True
    assert text.count(OLD) == 1, "Apply the existing media compatibility patch first"
    path.write_text(text.replace(OLD, NEW, 1))
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path)
    args = parser.parse_args()
    print("patched" if patch(args.kernel) else "already patched")

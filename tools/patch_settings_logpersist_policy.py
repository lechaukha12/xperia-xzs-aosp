#!/usr/bin/env python3
"""Restore the logpersist property permission required by Settings on this debuggable port.

The user GSI policy omits the userdebug system_app permission, while this port
sets ro.debuggable=1 and exposes the corresponding Developer options controller.
Keep the change limited to the logpersist property; do not relax property_service
checks globally. Preserve the source file's owner, mode and SELinux xattr.
"""
import argparse
import os
from pathlib import Path

MARKER = "; keyaki: Settings logpersist controller on the debuggable user GSI"
RULES = """(allow system_app logpersistd_logging_prop (property_service (set)))
(allow system_app logpersistd_logging_prop (file (getattr open read map)))
"""


def patch(path: Path) -> bool:
    text = path.read_text()
    if MARKER in text:
        return False
    for symbol in ["system_app", "logpersistd_logging_prop"]:
        if f"(type {symbol})" not in text:
            raise ValueError(f"Missing policy type: {symbol}")
    st = path.stat()
    ctx = os.getxattr(path, b"security.selinux", follow_symlinks=False)
    path.write_text(text.rstrip() + "\n\n" + MARKER + "\n" + RULES)
    os.chown(path, st.st_uid, st.st_gid)
    os.chmod(path, st.st_mode & 0o7777)
    os.setxattr(path, b"security.selinux", ctx, follow_symlinks=False)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path)
    args = parser.parse_args()
    print("patched" if patch(args.policy) else "already patched")

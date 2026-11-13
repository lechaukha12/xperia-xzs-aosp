#!/usr/bin/env python3
"""
Extract and patch Android 17 com.android.tethering BPF loader and BPF ELF objects
for Linux 5.4.302 compatibility on Sony Xperia XZs (keyaki):

1. /work/out/components/netbpfload_54:
   Relaxes NetBpfLoad minimum kernel version gate so Linux 5.4.302 proceeds cleanly:
   - 0x98c4: 41 21 00 54 (b.ne) -> 1f 20 03 d5 (nop)
   - 0xa598: 28 01 00 54 (b.eq) -> 16 00 00 14 (b +0x58)

2. /work/out/components/bpf_mainline_54/{netd.o, offload.o, ...}:
   Android 17 ships both legacy non-BTF BPF programs (min_kver=4.19, max_kver=5.4.0)
   and newer BTF/ringbuf BPF programs (min_kver=5.4.0) in .android_progs.
   On Linux 5.4.302 (0x0504012e > 0x05040000), NetBpfLoad normally skips the 4.19
   programs and attempts to load the 5.4+ ringbuf/CO-RE variants, failing on 5.4.
   This patch disables the incompatible 5.4+ descriptors (0xffffffff) and raises
   max_kver of the verified non-BTF 4.19 descriptors from 5.4.0 to 5.10.0.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NETBPFLOAD_PATCHES = [
    (0x98C4, bytes.fromhex("41210054"), bytes.fromhex("1f2003d5")),
    (0xA598, bytes.fromhex("28010054"), bytes.fromhex("16000014")),
]

NETD_O_PATCHES = [
    (0x1E488, bytes.fromhex("0000040500000a05"), bytes.fromhex("ffffffffffffffff")),
    (0x1E542, bytes.fromhex("04"), bytes.fromhex("0a")),
    (0x1E54C, bytes.fromhex("100e00"), bytes.fromhex("000001")),
    (0x1EA28, bytes.fromhex("0000040500000a05"), bytes.fromhex("ffffffffffffffff")),
    (0x1EAE2, bytes.fromhex("04"), bytes.fromhex("0a")),
    (0x1EAEC, bytes.fromhex("100e00"), bytes.fromhex("000001")),
]

OFFLOAD_O_PATCHES = [
    (0x1D798, bytes.fromhex("00000405"), bytes.fromhex("ffffffff")),
    (0x1D84C, bytes.fromhex("00000405"), bytes.fromhex("ffffffff")),
    (0x1D906, bytes.fromhex("04"), bytes.fromhex("0a")),
    (0x1D9BA, bytes.fromhex("04"), bytes.fromhex("0a")),
    (0x1DA68, bytes.fromhex("00000405"), bytes.fromhex("ffffffff")),
    (0x1DB1C, bytes.fromhex("00000405"), bytes.fromhex("ffffffff")),
    (0x1DBD6, bytes.fromhex("04"), bytes.fromhex("0a")),
    (0x1DC8A, bytes.fromhex("04"), bytes.fromhex("0a")),
    (0x1E170, bytes.fromhex("0000040500000a05"), bytes.fromhex("ffffffffffffffff")),
    (0x1E224, bytes.fromhex("0000040500000a05"), bytes.fromhex("ffffffffffffffff")),
    (0x1E2D8, bytes.fromhex("0000040500000a05"), bytes.fromhex("ffffffffffffffff")),
    (0x1E38C, bytes.fromhex("0000040500000a05"), bytes.fromhex("ffffffffffffffff")),
    (0x1E710, bytes.fromhex("0000040500000a05"), bytes.fromhex("ffffffffffffffff")),
    (0x1E7C4, bytes.fromhex("0000040500000a05"), bytes.fromhex("ffffffffffffffff")),
    (0x1E87E, bytes.fromhex("04"), bytes.fromhex("0a")),
    (0x1E932, bytes.fromhex("04"), bytes.fromhex("0a")),
    (0x1E9E0, bytes.fromhex("0000040500000a05"), bytes.fromhex("ffffffffffffffff")),
    (0x1EA94, bytes.fromhex("0000040500000a05"), bytes.fromhex("ffffffffffffffff")),
    (0x1EB4E, bytes.fromhex("04"), bytes.fromhex("0a")),
    (0x1EC02, bytes.fromhex("04"), bytes.fromhex("0a")),
]


def apply_verified_patches(src: Path, dst: Path, patches: list[tuple[int, bytes, bytes]], mode: int) -> None:
    buf = bytearray(src.read_bytes())
    for off, exp, repl in patches:
        assert len(exp) == len(repl)
        got = bytes(buf[off : off + len(exp)])
        if got != exp:
            raise RuntimeError(
                f"{src.name}@0x{off:x}: expected {exp.hex()}, got {got.hex()}"
            )
        buf[off : off + len(repl)] = repl
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(buf)
    os.chmod(dst, mode)
    print(f"[OK] Patched {src.name} -> {dst} ({len(patches)} sites, {len(buf)} bytes)")


def patch_from_tethering_capex(capex_path: Path, out_components: Path) -> None:
    out_bpf_dir = out_components / "bpf_mainline_54"
    out_bpf_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="tethering_bpf_") as td:
        subprocess.run(f"unzip -q {capex_path} original_apex -d {td}", shell=True, check=True)
        subprocess.run(f"unzip -q {td}/original_apex apex_payload.img -d {td}", shell=True, check=True)
        mnt_pay = f"{td}/pay"
        os.makedirs(mnt_pay, exist_ok=True)
        subprocess.run(f"mount -o loop,ro {td}/apex_payload.img {mnt_pay}", shell=True, check=True)
        try:
            apply_verified_patches(
                Path(f"{mnt_pay}/bin/netbpfload"),
                out_components / "netbpfload_54",
                NETBPFLOAD_PATCHES,
                0o750,
            )
            src_mainline = Path(f"{mnt_pay}/etc/bpf/mainline")
            for p in sorted(src_mainline.iterdir()):
                if not p.is_file():
                    continue
                dst = out_bpf_dir / p.name
                if p.name == "netd.o":
                    apply_verified_patches(p, dst, NETD_O_PATCHES, 0o644)
                elif p.name == "offload.o":
                    apply_verified_patches(p, dst, OFFLOAD_O_PATCHES, 0o644)
                else:
                    shutil.copyfile(p, dst)
                    os.chmod(dst, 0o644)
        finally:
            subprocess.run(f"umount {mnt_pay}", shell=True, check=True)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    sys_img = root / "port_rom" / "extracted" / "system.img"
    out_components = root / "out" / "components"

    if len(sys.argv) > 1 and sys.argv[1].endswith(".capex"):
        patch_from_tethering_capex(Path(sys.argv[1]), out_components)
        return 0

    with tempfile.TemporaryDirectory(prefix="sys_teth_") as td:
        mnt_sys = f"{td}/sys"
        os.makedirs(mnt_sys, exist_ok=True)
        subprocess.run(f"mount -o loop,ro {sys_img} {mnt_sys}", shell=True, check=True)
        try:
            patch_from_tethering_capex(
                Path(f"{mnt_sys}/system/apex/com.android.tethering.capex"),
                out_components,
            )
        finally:
            subprocess.run(f"umount {mnt_sys}", shell=True, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Patches Android 17 libui.so (32-bit & 64-bit, system & media.swcodec APEX)
to re-enable Gralloc 2.0 / 3.0 passthrough IMapper fallback on legacy Treble
devices where ro.build.version.sdk (37) > 35 (__ANDROID_API_V__).
"""
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def vaddr_to_offset(data: bytes, vaddr: int) -> int:
    assert data[:4] == b"\x7fELF", "Not an ELF binary"
    ei_class = data[4]
    if ei_class == 2:  # ELF64
        e_phoff = struct.unpack_from("<Q", data, 32)[0]
        e_phentsize, e_phnum = struct.unpack_from("<HH", data, 54)
        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            p_type, p_flags, p_offset, p_vaddr, _, p_filesz, _ = struct.unpack_from(
                "<IIQQQQQ", data, off
            )
            if p_type == 1 and p_vaddr <= vaddr < p_vaddr + p_filesz:
                return p_offset + (vaddr - p_vaddr)
    elif ei_class == 1:  # ELF32
        e_phoff = struct.unpack_from("<I", data, 28)[0]
        e_phentsize, e_phnum = struct.unpack_from("<HH", data, 42)
        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            p_type, p_offset, p_vaddr, _, p_filesz, _, _, _ = struct.unpack_from(
                "<IIIIIIII", data, off
            )
            if p_type == 1 and p_vaddr <= vaddr < p_vaddr + p_filesz:
                return p_offset + (vaddr - p_vaddr)
    raise ValueError(f"vaddr {hex(vaddr)} not found in any PT_LOAD segment")


def patch_elf64(src: Path, dst: Path, sites: list[tuple[int, bytes]]) -> None:
    buf = bytearray(src.read_bytes())
    cmp_insn = b"\x1f\x8c\x00\x71"  # cmp w0, #0x23
    nop_insn = b"\x1f\x20\x03\xd5"  # nop
    for vaddr, expected_bgt in sites:
        foff = vaddr_to_offset(buf, vaddr)
        prev = bytes(buf[foff - 4 : foff])
        cur = bytes(buf[foff : foff + 4])
        assert prev == cmp_insn, f"{src.name}@{hex(vaddr)}-4: got {prev.hex()}"
        assert cur == expected_bgt, f"{src.name}@{hex(vaddr)}: got {cur.hex()} != {expected_bgt.hex()}"
        buf[foff : foff + 4] = nop_insn
        print(f"[OK] {src.name}: vaddr {hex(vaddr)} (file {hex(foff)}) {cur.hex()} -> {nop_insn.hex()}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(buf)


def patch_elf32(src: Path, dst: Path, sites: list[tuple[int, bytes]]) -> None:
    buf = bytearray(src.read_bytes())
    cmp_insn = b"\x23\x28"  # cmp r0, #0x23
    nop_insn = b"\x00\xbf"  # nop (Thumb)
    for vaddr, expected_bgt in sites:
        foff = vaddr_to_offset(buf, vaddr)
        prev = bytes(buf[foff - 2 : foff])
        cur = bytes(buf[foff : foff + 2])
        assert prev == cmp_insn, f"{src.name}@{hex(vaddr)}-2: got {prev.hex()}"
        assert cur == expected_bgt, f"{src.name}@{hex(vaddr)}: got {cur.hex()} != {expected_bgt.hex()}"
        buf[foff : foff + 2] = nop_insn
        print(f"[OK] {src.name}: vaddr {hex(vaddr)} (file {hex(foff)}) {cur.hex()} -> {nop_insn.hex()}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(buf)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    sys_img = root / "port_rom" / "extracted" / "system.img"
    out = root / "out" / "components"
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="libui_src_") as td:
        mnt = f"{td}/sys"
        os.makedirs(mnt, exist_ok=True)
        subprocess.run(f"mount -o loop,ro {sys_img} {mnt}", shell=True, check=True)
        try:
            patch_elf64(
                Path(f"{mnt}/system/lib64/libui.so"),
                out / "libui64.patched.so",
                [(0x34D98, b"\xac\x03\x00\x54"), (0x5A1F4, b"\x6c\x00\x00\x54")],
            )
            patch_elf32(
                Path(f"{mnt}/system/lib/libui.so"),
                out / "libui32.patched.so",
                [(0x2184A, b"\x1b\xdc"), (0x3E670, b"\x03\xdc")],
            )

            subprocess.run(
                f"unzip -q {mnt}/system/apex/com.android.media.swcodec.capex original_apex -d {td}",
                shell=True,
                check=True,
            )
            subprocess.run(f"unzip -q {td}/original_apex apex_payload.img -d {td}", shell=True, check=True)
            os.makedirs(f"{td}/pay", exist_ok=True)
            subprocess.run(f"mount -o loop,ro {td}/apex_payload.img {td}/pay", shell=True, check=True)
            try:
                patch_elf64(
                    Path(f"{td}/pay/lib64/libui.so"),
                    out / "swcodec_libui64.patched.so",
                    [(0x351A8, b"\xac\x03\x00\x54"), (0x5C368, b"\x6c\x00\x00\x54")],
                )
                patch_elf32(
                    Path(f"{td}/pay/lib/libui.so"),
                    out / "swcodec_libui32.patched.so",
                    [(0x2186A, b"\x1b\xdc"), (0x3E690, b"\x03\xdc")],
                )
            finally:
                subprocess.run(f"umount {td}/pay", shell=True, check=True)
        finally:
            subprocess.run(f"umount {mnt}", shell=True, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

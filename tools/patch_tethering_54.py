#!/usr/bin/env python3
"""
Patch Android 17 com.android.tethering's libservice-connectivity.so for Linux 5.4 kernels
that lack BPF_MAP_TYPE_RINGBUF (introduced in Linux 5.8).

Root causes addressed:
1. LocalNetEventHandler::GetRingbuf() (0xf30c) opens
   /sys/fs/bpf/netd_shared/map_netd_local_net_note_op_ringbuf (BPF_MAP_TYPE_RINGBUF)
   and calls abort() at 0xf3ec on failure, crashing system_server in ConnectivityService.<init>.
   Furthermore, LocalNetEventListener.start() passes mRingbufFd directly to
   MessageQueue.addOnFileDescriptorEventListener(), which requires a non-null pollable fd.
   -> Patch nativeGetLocalNetAccessRingbufFd (0xdf18..0xdf28) to allocate an idle
      eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK) via eventfd@plt (0x15130), patch
      nativeConsumeAllLocalNetAccessEvents (0xe2b0) to return an empty int[0],
      and NOP the abort branch in LocalNetEventHandler::GetRingbuf() (0xf380).

2. LoopbackEventHandler::GetPoller() lambda (0x11f0c) opens
   /sys/fs/bpf/netd_shared/map_netd_loopback_access_ringbuf (BPF_MAP_TYPE_RINGBUF)
   and calls abort() at 0x12108 when BpfEventPoller.nativeInitLoopbackEventConsumer()
   runs in ConnectivityService.systemReady().
   LoopbackEventHandler::Start() and Stop() already handle GetPoller() == nullptr gracefully.
   -> Patch 0x11f10..0x11f18 (after paciasp at 0x11f0c) to `mov x0, xzr; autiasp; ret`.
"""

import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def u32(val: int) -> bytes:
    return struct.pack("<I", val)


def r32(buf: bytearray, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def patch_libservice_connectivity(src: Path, dst: Path) -> None:
    data = bytearray(src.read_bytes())

    expected = {
        0xDF18: 0x94001BF2,  # bl LocalNetEventHandler::GetRingbuf()@plt
        0xDF1C: 0xB9401800,  # ldr w0, [x0, #24]
        0xDF20: 0x528080C1,  # mov w1, #0x406
        0xDF24: 0x2A1F03E2,  # mov w2, wzr
        0xDF28: 0x94001BF2,  # bl fcntl@plt
        0xE2B0: 0x94001B28,  # bl LocalNetEventHandler::ConsumeAll()@plt
        0xF380: 0x350001E8,  # cbnz w8, 0xf3bc
        0x11F0C: 0xD503233F,  # paciasp
        0x11F10: 0xD10383FF,  # sub sp, sp, #0xe0
        0x11F14: 0xA90A7BFD,  # stp x29, x30, [sp, #160]
        0x11F18: 0xF9005BF7,  # str x23, [sp, #176]
        0x15130: 0xF0000010,  # adrp x16, 0x18000 (eventfd@plt)
    }

    for off, exp in expected.items():
        got = r32(data, off)
        if got != exp:
            raise RuntimeError(
                f"Unexpected instruction at 0x{off:x}: got 0x{got:08x}, expected 0x{exp:08x}"
            )

    bl_eventfd = 0x94000000 | (((0x15130 - 0xDF24) // 4) & 0x03FFFFFF)
    assert bl_eventfd == 0x94001C83

    patches = {
        0xDF18: 0x2A1F03E0,  # mov w0, wzr
        0xDF1C: 0x52810001,  # mov w1, #0x800 (EFD_NONBLOCK)
        0xDF20: 0x72A00101,  # movk w1, #0x8, lsl #16 (EFD_CLOEXEC)
        0xDF24: bl_eventfd,  # bl 0x15130 <eventfd@plt>
        0xDF28: 0xD503201F,  # nop
        0xE2B0: 0xD503201F,  # nop
        0xF380: 0xD503201F,  # nop
        0x11F10: 0xAA1F03E0,  # mov x0, xzr
        0x11F14: 0xD50323BF,  # autiasp
        0x11F18: 0xD65F03C0,  # ret
    }

    for off, insn in patches.items():
        data[off : off + 4] = u32(insn)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    print(f"[OK] Patched {src.name} -> {dst} ({len(data)} bytes, {len(patches)} instructions updated)")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    dst_path = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "out" / "components" / "libservice-connectivity_54.so"
    if len(sys.argv) > 1:
        patch_libservice_connectivity(Path(sys.argv[1]), dst_path)
        return 0

    sys_img = root / "port_rom" / "extracted" / "system.img"
    with tempfile.TemporaryDirectory(prefix="teth_src_") as td:
        mnt = f"{td}/sys"
        os.makedirs(mnt, exist_ok=True)
        subprocess.run(f"mount -o loop,ro {sys_img} {mnt}", shell=True, check=True)
        try:
            subprocess.run(
                f"unzip -q {mnt}/system/apex/com.android.tethering.capex original_apex -d {td}",
                shell=True,
                check=True,
            )
            subprocess.run(f"unzip -q {td}/original_apex apex_payload.img -d {td}", shell=True, check=True)
            os.makedirs(f"{td}/pay", exist_ok=True)
            subprocess.run(f"mount -o loop,ro {td}/apex_payload.img {td}/pay", shell=True, check=True)
            try:
                patch_libservice_connectivity(
                    Path(f"{td}/pay/lib64/libservice-connectivity.so"),
                    dst_path,
                )
            finally:
                subprocess.run(f"umount {td}/pay", shell=True, check=True)
        finally:
            subprocess.run(f"umount {mnt}", shell=True, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

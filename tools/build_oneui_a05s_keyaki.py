#!/usr/bin/env python3
"""
Build and offline-verify a MysticGSI One UI 6.1 (Oneui-a05s-14) system image
adapted for Sony Xperia XZs (keyaki / SO-03J, MSM8996, VNDK 30, Linux 5.4.302):
  Input : /work/oneui_work/system.img
          /work/out/oem-a17-keyaki.img
  Output: /work/out/system-oneui61-keyaki.sparse.img
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from repack_virt_apex_ext4 import ensure_container_keys


MMCBLK0P55_LIMIT = 7_707_033_600
TARGET_RAW_MB = "5200M"


def run(cmd: str) -> None:
    print(">>", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def get_meta(path: Path) -> tuple[int, int, int, bytes]:
    st = os.lstat(path)
    ctx = os.getxattr(path, b"security.selinux", follow_symlinks=False)
    return st.st_uid, st.st_gid, st.st_mode & 0o7777, ctx


def apply_meta(path: Path, uid: int, gid: int, mode: int, ctx: bytes) -> None:
    os.chown(path, uid, gid)
    os.chmod(path, mode)
    os.setxattr(path, b"security.selinux", ctx, follow_symlinks=False)


def write_preserving_meta(path: Path, content: str, default_mode: int = 0o644) -> None:
    uid, gid, mode, ctx = get_meta(path)
    path.write_text(content)
    apply_meta(path, uid, gid, mode or default_mode, ctx)


def install_preserving_target_meta(src: Path, dst: Path) -> None:
    uid, gid, mode, ctx = get_meta(dst)
    shutil.copyfile(src, dst)
    apply_meta(dst, uid, gid, mode, ctx)


def repack_erofs_apex_to_ext4(
    src_apex: Path,
    out_apex: Path,
    avbtool: Path,
    pk8: Path,
    cert: Path,
    apex_key_prop: str,
) -> None:
    """Repack an EROFS-backed APEX into an ext4-backed, AVB+APK v2/v3 signed APEX."""
    with tempfile.TemporaryDirectory(prefix="repack_shell_apex_") as td:
        run(f"unzip -q {src_apex} -d {td}/orig")
        erofs_img = f"{td}/orig/apex_payload.img"
        mnt_erofs = f"{td}/mnt_erofs"
        os.makedirs(mnt_erofs, exist_ok=True)
        run(f"mount -t erofs -o loop,ro {erofs_img} {mnt_erofs}")
        try:
            du_kb = int(
                subprocess.check_output(
                    f"du --apparent-size -sk {mnt_erofs}", shell=True
                ).split()[0]
            )
            img_mb = (du_kb // 1024) + 32
            ext4_img = f"{td}/apex_payload_ext4.img"
            run(f"dd if=/dev/zero of={ext4_img} bs=1M count={img_mb} status=none")
            run(f"mkfs.ext4 -F -b 4096 -L '' -O ^has_journal {ext4_img} >/dev/null 2>&1")

            mnt_ext4 = f"{td}/mnt_ext4"
            os.makedirs(mnt_ext4, exist_ok=True)
            run(f"mount -o loop {ext4_img} {mnt_ext4}")
            try:
                run(f"cp -a {mnt_erofs}/. {mnt_ext4}/")
                root_ctx = os.getxattr(
                    mnt_erofs, b"security.selinux", follow_symlinks=False
                )
                os.setxattr(mnt_ext4, b"security.selinux", root_ctx, follow_symlinks=False)
            finally:
                run(f"umount {mnt_ext4}")
        finally:
            run(f"umount {mnt_erofs}")

        run(f"e2fsck -fy {ext4_img} >/dev/null 2>&1 || true")
        run(f"resize2fs -M {ext4_img} >/dev/null 2>&1")
        cur_size = os.path.getsize(ext4_img)
        new_size = ((cur_size + 4095) // 4096) * 4096 + (2 * 1024 * 1024)
        with open(ext4_img, "ab") as f:
            f.truncate(new_size)

        key_pem = f"{td}/apex_avb.pem"
        pubkey_bin = f"{td}/apex_pubkey"
        run(f"openssl genrsa -out {key_pem} 4096 2>/dev/null")
        run(f"python3 {avbtool} extract_public_key --key {key_pem} --output {pubkey_bin}")
        run(
            f"python3 {avbtool} add_hashtree_footer "
            f"--do_not_generate_fec "
            f"--algorithm SHA256_RSA4096 "
            f"--hash_algorithm sha256 "
            f"--key {key_pem} "
            f"--prop apex.key:{apex_key_prop} "
            f"--image {ext4_img}"
        )
        run(f"python3 {avbtool} verify_image --image {ext4_img} --key {key_pem}")

        if out_apex.exists():
            out_apex.unlink()

        entries = [("apex_payload.img", Path(ext4_img).read_bytes(), 4096)]
        for rel in [
            "assets/NOTICE.html.gz",
            "resources.arsc",
            "AndroidManifest.xml",
            "apex_build_info.pb",
            "apex_manifest.pb",
        ]:
            p = Path(f"{td}/orig/{rel}")
            if p.exists():
                entries.append((rel, p.read_bytes(), 4))
        entries.append(("apex_pubkey", Path(pubkey_bin).read_bytes(), 4))

        with zipfile.ZipFile(out_apex, "w", compression=zipfile.ZIP_STORED) as zf:
            for name, data, align in entries:
                zi = zipfile.ZipInfo(name, date_time=(2009, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_STORED
                zi.external_attr = 0o644 << 16
                cur_offset = zf.fp.tell()
                header_end = cur_offset + 30 + len(name.encode("utf-8"))
                pad = (align - (header_end % align)) % align
                zi.extra = b"\x00" * pad
                zf.writestr(zi, data)

        run(
            f"apksigner sign --key {pk8} --cert {cert} "
            f"--v1-signing-enabled false --v2-signing-enabled true --v3-signing-enabled true "
            f"--min-sdk-version 24 {out_apex}"
        )
        idsig = Path(f"{out_apex}.idsig")
        if idsig.exists():
            idsig.unlink()

        raw = out_apex.read_bytes()
        head2k = Path(ext4_img).read_bytes()[:2048]
        off = raw.find(head2k)
        assert off > 0 and off % 4096 == 0, f"Misaligned apex_payload.img offset: {off}"
        print(
            f"[OK] Repacked {src_apex.name} -> ext4 ({out_apex.stat().st_size} bytes, "
            f"payload offset={off}, mod 4096 == 0)"
        )


def patch_compatibility_matrix(path: Path) -> None:
    xml = path.read_text()
    xml_new = re.sub(r"<kernel\b[^>]*>.*?</kernel>", "", xml, flags=re.DOTALL)
    xml_new = re.sub(
        r"(<name>android\.hardware\.graphics\.mapper</name>\s*<version>)2\.1(</version>)",
        r"\g<1>2.0-1\g<2>",
        xml_new,
    )
    ET.fromstring(xml_new)
    write_preserving_meta(path, xml_new)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    src_img = root / "oneui_work" / "system.img"
    raw_img = root / "oneui_work" / "system-oneui61-keyaki.raw.img"
    out_sparse = root / "out" / "system-oneui61-keyaki.sparse.img"
    oem_img = root / "out" / "oem-a17-keyaki.img"
    avbtool = root / "tools" / "avb" / "avbtool.py"
    cfg_cgroups = root / "configs" / "cgroups" / "cgroups.json"
    cfg_sys_prop = root / "configs" / "props" / "system_keyaki.prop"

    assert src_img.exists(), f"Missing extracted GSI image: {src_img}"
    assert oem_img.exists(), f"Missing OEM image: {oem_img}"
    assert cfg_cgroups.exists(), f"Missing cgroups config: {cfg_cgroups}"
    assert cfg_sys_prop.exists(), f"Missing system_keyaki.prop: {cfg_sys_prop}"

    print(f"Copying {src_img} -> {raw_img}...")
    shutil.copyfile(src_img, raw_img)
    run(f"e2fsck -fy {raw_img} >/dev/null 2>&1 || true")
    run(f"resize2fs {raw_img} {TARGET_RAW_MB}")
    run(f"e2fsck -E unshare_blocks -fy {raw_img} >/dev/null 2>&1 || true")
    assert raw_img.stat().st_size < MMCBLK0P55_LIMIT, "Raw image exceeds mmcblk0p55 limit"

    mnt = Path("/tmp/mnt_oneui_rw")
    mnt_ven = Path("/tmp/mnt_ven_ro")
    shutil.rmtree(mnt, ignore_errors=True)
    shutil.rmtree(mnt_ven, ignore_errors=True)
    mnt.mkdir(parents=True, exist_ok=True)
    mnt_ven.mkdir(parents=True, exist_ok=True)

    run(f"mount -o loop,rw {raw_img} {mnt}")
    run(f"mount -o loop,ro {oem_img} {mnt_ven}")
    try:
        # 2a. Remove broken 133-byte Git LFS stubs for VNDK 31/32
        for stub_name in ["com.android.vndk.v31.apex", "com.android.vndk.v32.apex"]:
            stub = mnt / "system" / "apex" / stub_name
            if stub.exists():
                assert stub.stat().st_size < 1024 and b"git-lfs" in stub.read_bytes(), (
                    f"Unexpected size/content in {stub}"
                )
                stub.unlink()
                print(f"[OK] Removed corrupt Git LFS pointer stub: {stub_name}")

        # 2b. Repack EROFS com.samsung.android.shell.apex -> ext4
        shell_apex = mnt / "system" / "apex" / "com.samsung.android.shell.apex"
        assert shell_apex.exists(), f"Missing {shell_apex}"
        s_uid, s_gid, s_mode, s_ctx = get_meta(shell_apex)
        pk8, cert = ensure_container_keys(root)
        with tempfile.TemporaryDirectory(prefix="shell_apex_out_") as td:
            repacked_shell = Path(td) / "com.samsung.android.shell.apex"
            repack_erofs_apex_to_ext4(
                shell_apex,
                repacked_shell,
                avbtool,
                pk8,
                cert,
                "com.samsung.android.apex",
            )
            shutil.copyfile(repacked_shell, shell_apex)
            apply_meta(shell_apex, s_uid, s_gid, s_mode, s_ctx)

        # 3a. Patch /system/bin/vndk-detect so it detects vendor_sepolicy.cil too
        vndk_detect = mnt / "system" / "bin" / "vndk-detect"
        vd_text = vndk_detect.read_text()
        old_line = "grep -oE 'init_[0-9_]+' /vendor/etc/selinux/nonplat_sepolicy.cil | \\"
        new_line = "grep -hoE 'init_[0-9_]+' /vendor/etc/selinux/nonplat_sepolicy.cil /vendor/etc/selinux/vendor_sepolicy.cil 2>/dev/null | \\"
        assert old_line in vd_text, "Expected pattern not found in /system/bin/vndk-detect"
        write_preserving_meta(vndk_detect, vd_text.replace(old_line, new_line, 1), 0o755)
        print("[OK] Patched /system/bin/vndk-detect for vendor_sepolicy.cil")

        # 3a2. Patch /system/bin/bpfloader so /system/etc/bpf allows BPF_PROG_TYPE_SCHED_CLS (3)
        bpfloader = mnt / "system" / "bin" / "bpfloader"
        b_uid, b_gid, b_mode, b_ctx = get_meta(bpfloader)
        b_buf = bytearray(bpfloader.read_bytes())
        exp_types = bytes.fromhex("0200000007000000010000000500000000000000")
        new_types = bytes.fromhex("0200000007000000010000000500000003000000")
        assert bytes(b_buf[0x1978:0x198C]) == exp_types, (
            f"Unexpected bpfloader prog_type array at 0x1978: {bytes(b_buf[0x1978:0x198C]).hex()}"
        )
        b_buf[0x1978:0x198C] = new_types
        bpfloader.write_bytes(b_buf)
        apply_meta(bpfloader, b_uid, b_gid, b_mode or 0o755, b_ctx)
        print("[OK] Patched /system/bin/bpfloader (allowed schedcls=3 in /system/etc/bpf/)")

        # 3b. VINTF compatibility_matrix.5.xml / 4.xml & system_ext/etc/vintf/manifest.xml
        for cm_name in ["compatibility_matrix.5.xml", "compatibility_matrix.4.xml"]:
            cm_path = mnt / "system" / "etc" / "vintf" / cm_name
            if cm_path.exists():
                patch_compatibility_matrix(cm_path)
                print(f"[OK] Patched {cm_name} (mapper 2.0-1, stripped <kernel> blocks)")

        se_manifest = mnt / "system" / "system_ext" / "etc" / "vintf" / "manifest.xml"
        mf_text = se_manifest.read_text()
        if "<version>30</version>" not in mf_text:
            target_tag = "    <vendor-ndk>\n        <version>33</version>\n    </vendor-ndk>"
            assert target_tag in mf_text, f"Unexpected structure in {se_manifest}"
            add_tag = (
                target_tag
                + "\n    <vendor-ndk>\n        <version>30</version>\n    </vendor-ndk>"
            )
            mf_new = mf_text.replace(target_tag, add_tag, 1)
            ET.fromstring(mf_new)
            write_preserving_meta(se_manifest, mf_new)
            print("[OK] Added <vendor-ndk><version>30</version></vendor-ndk> to system_ext vintf manifest")

        # 3c. SELinux mapping empty stubs + secilc verification
        _, _, _, map_ctx = get_meta(mnt / "system" / "etc" / "selinux" / "mapping" / "30.0.cil")
        for sub in ["system_ext", "product"]:
            for fn in ["30.0.cil", "30.0.compat.cil"]:
                sp = mnt / "system" / sub / "etc" / "selinux" / "mapping" / fn
                sp.parent.mkdir(parents=True, exist_ok=True)
                sp.write_text("")
                apply_meta(sp, 0, 0, 0o644, map_ctx)

        se_tmp = Path("/tmp/oneui_secilc_verify")
        shutil.rmtree(se_tmp, ignore_errors=True)
        se_tmp.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(mnt_ven / "etc" / "selinux" / "plat_pub_versioned.cil", se_tmp / "plat_pub_versioned.cil")
        shutil.copyfile(mnt_ven / "etc" / "selinux" / "vendor_sepolicy.cil", se_tmp / "vendor_sepolicy.cil")
        run(f"mount --bind {se_tmp} {mnt / 'data'}")
        try:
            secilc_cmd = [
                "chroot",
                str(mnt),
                "/system/bin/secilc",
                "-m", "-M", "true", "-G", "-N", "-c", "31",
                "-o", "/data/sepolicy.bin",
                "-f", "/data/file_contexts_out",
                "/system/etc/selinux/plat_sepolicy.cil",
                "/system/etc/selinux/mapping/30.0.cil",
                "/system/etc/selinux/mapping/30.0.compat.cil",
                "/system/system_ext/etc/selinux/system_ext_sepolicy.cil",
                "/system/system_ext/etc/selinux/mapping/30.0.cil",
                "/system/system_ext/etc/selinux/mapping/30.0.compat.cil",
                "/system/product/etc/selinux/product_sepolicy.cil",
                "/system/product/etc/selinux/mapping/30.0.cil",
                "/system/product/etc/selinux/mapping/30.0.compat.cil",
                "/data/plat_pub_versioned.cil",
                "/data/vendor_sepolicy.cil",
            ]
            res = subprocess.run(secilc_cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print("FATAL: Offline secilc verification FAILED!", res.stdout, res.stderr)
                sys.exit(1)
            pol_sz = (se_tmp / "sepolicy.bin").stat().st_size
            print(f"[OK] Offline secilc PASSED (exit=0, sepolicy.bin={pol_sz} bytes)")
        finally:
            run(f"umount {mnt / 'data'}")
            shutil.rmtree(se_tmp, ignore_errors=True)

        # 4a. Install Linux 5.4 cgroups.json
        install_preserving_target_meta(cfg_cgroups, mnt / "system" / "etc" / "cgroups.json")
        print("[OK] Installed Linux 5.4 cgroups.json")

        # 4b. Audio configs (audio_effects_sec.xml + strip STAGE_EFFECT_DOLBY from stage_policy.conf)
        ae_src = mnt / "system" / "etc" / "audio_effects.xml"
        ae_dst = mnt / "system" / "etc" / "audio_effects_sec.xml"
        _, _, _, ae_ctx = get_meta(ae_src)
        shutil.copyfile(ae_src, ae_dst)
        apply_meta(ae_dst, 0, 0, 0o644, ae_ctx)
        print("[OK] Created /system/etc/audio_effects_sec.xml from audio_effects.xml")

        stage_conf = mnt / "system" / "etc" / "stage_policy.conf"
        sc_lines = stage_conf.read_text().splitlines(keepends=True)
        sc_filtered = [ln for ln in sc_lines if "STAGE_EFFECT_DOLBY" not in ln]
        sc_new = "".join(sc_filtered)
        assert sc_new.count("{") == sc_new.count("}"), "Brace mismatch after stripping STAGE_EFFECT_DOLBY"
        write_preserving_meta(stage_conf, sc_new)
        print(f"[OK] Stripped {len(sc_lines) - len(sc_filtered)} STAGE_EFFECT_DOLBY lines from stage_policy.conf")

        # 4c. Remove incompatible Samsung priv-apps/overlays:
        #     - SamsungDeviceHealthManagerService: repeated vendor crashes
        #     - KnoxGuard: code 3010 remote lock on non-Samsung devices
        #     - WifiRROverlayApp/H2E/Jdm: force connected MAC randomization, breaking BCM4359 brcmfmac 4-way handshake
        for rel_dir in (
            "priv-app/SamsungDeviceHealthManagerService",
            "priv-app/KnoxGuard",
            "app/WifiRROverlayApp",
            "app/WifiRROverlayAppH2E",
            "app/WifiRROverlayJdm",
        ):
            app_dir = mnt / "system" / rel_dir
            if app_dir.exists():
                shutil.rmtree(app_dir)
                print(f"[OK] Removed {rel_dir}")

        # 4d. Restore standard AOSP ConfigFS USB triggers & update /system/product/etc/build.prop + /system/build.prop
        usb_cfg = mnt / "system" / "etc" / "init" / "hw" / "init.usb.configfs.rc"
        usb_uncommented = re.sub(r"^#", "", usb_cfg.read_text(), flags=re.MULTILINE)
        assert "on property:sys.usb.config=adb && property:sys.usb.configfs=1" in usb_uncommented
        write_preserving_meta(usb_cfg, usb_uncommented, 0o644)
        print("[OK] Uncommented AOSP USB ConfigFS triggers in /system/etc/init/hw/init.usb.configfs.rc")

        prod_prop = mnt / "system" / "product" / "etc" / "build.prop"
        pp_text = prod_prop.read_text()
        assert "persist.sys.usb.config=mtp" in pp_text, f"Expected persist.sys.usb.config=mtp in {prod_prop}"
        pp_new = pp_text.replace("persist.sys.usb.config=mtp", "persist.sys.usb.config=adb")
        write_preserving_meta(prod_prop, pp_new)
        print("[OK] Updated persist.sys.usb.config=adb in /system/product/etc/build.prop")

        sys_prop = mnt / "system" / "build.prop"
        sp_text = sys_prop.read_text().replace("persist.sys.usb.config=adb,mtp", "persist.sys.usb.config=adb")
        extra_lines = [
            ln for ln in cfg_sys_prop.read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("persist.sys.usb.config=")
        ]
        extra_block = "\n" + "\n".join(extra_lines) + "\nro.opengles.version=196610\n"
        write_preserving_meta(sys_prop, sp_text.rstrip() + "\n" + extra_block, 0o600)
        print("[OK] Updated persist.sys.usb.config=adb and appended keyaki props + ro.opengles.version=196610 to /system/build.prop")

        rw_sys = mnt / "system" / "bin" / "rw-system.sh"
        rw_text = rw_sys.read_text()
        assert "resetprop_phh ro.adb.secure 1" in rw_text, f"Expected resetprop_phh ro.adb.secure 1 in {rw_sys}"
        write_preserving_meta(rw_sys, rw_text.replace("resetprop_phh ro.adb.secure 1", "resetprop_phh ro.adb.secure 0"), 0o755)
        print("[OK] Updated resetprop_phh ro.adb.secure 0 in /system/bin/rw-system.sh")

        # 4e. Audit SELinux xattrs across the entire mounted image
        print("Auditing SELinux xattrs across mounted root...")
        unlabeled = []
        for root_dir, dirs, files in os.walk(mnt, followlinks=False):
            for name in dirs + files:
                if name == "lost+found":
                    continue
                p = os.path.join(root_dir, name)
                try:
                    os.getxattr(p, b"security.selinux", follow_symlinks=False)
                except OSError:
                    unlabeled.append(p)
        if unlabeled:
            print("FATAL: Unlabeled entries in system:", unlabeled[:20])
            sys.exit(1)
        print("[OK] SELinux xattr audit PASSED: 0 unlabeled entries!")

        run(f"df -h {mnt}")
    finally:
        subprocess.run(f"umount {mnt_ven}", shell=True)
        run(f"umount {mnt}")
        shutil.rmtree(mnt_ven, ignore_errors=True)
        shutil.rmtree(mnt, ignore_errors=True)

    run(f"e2fsck -fy {raw_img} >/dev/null 2>&1 || true")
    if out_sparse.exists():
        out_sparse.unlink()
    run(f"img2simg {raw_img} {out_sparse}")
    raw_img.unlink()

    print(f"ALL DONE: {out_sparse} ({out_sparse.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

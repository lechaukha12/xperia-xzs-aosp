#!/usr/bin/env python3
"""
Convert Android 17 com.android.virt.apex from an EROFS payload to an ext4 payload
for Linux 5.4 kernels without CONFIG_EROFS_FS, sign its AVB hashtree, pack a
4096-byte-aligned uncompressed .apex, and sign the outer container with
APK Signature Scheme v2+v3 (required by Android 17 PackageManagerService).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def run(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=True)


def ensure_container_keys(root: Path) -> tuple[Path, Path]:
    for key_dir in [root / "backup" / "keys", root / "work" / "keys"]:
        pk8 = key_dir / "virt_container.pk8"
        cert = key_dir / "virt_container.x509.pem"
        if pk8.exists() and cert.exists():
            return pk8, cert

    gen_dir = root / "work" / "keys"
    gen_dir.mkdir(parents=True, exist_ok=True)
    priv_pem = gen_dir / "virt_container_priv.pem"
    pk8 = gen_dir / "virt_container.pk8"
    cert = gen_dir / "virt_container.x509.pem"
    run(
        f"openssl req -new -x509 -newkey rsa:4096 -nodes -days 10000 "
        f"-subj '/CN=Android17-Keyaki-APEX/' -keyout {priv_pem} -out {cert} 2>/dev/null"
    )
    run(
        f"openssl pkcs8 -topk8 -inform PEM -outform DER -nocrypt "
        f"-in {priv_pem} -out {pk8}"
    )
    return pk8, cert


def repack_virt_apex(src_apex: Path, out_apex: Path, avbtool: Path, pk8: Path, cert: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="repack_virt_") as td:
        run(f"unzip -q {src_apex} -d {td}/orig")
        erofs_img = f"{td}/orig/apex_payload.img"
        mnt_erofs = f"{td}/mnt_erofs"
        os.makedirs(mnt_erofs, exist_ok=True)
        run(f"mount -t erofs -o loop,ro {erofs_img} {mnt_erofs}")
        try:
            du_kb = int(
                subprocess.check_output(f"du --apparent-size -sk {mnt_erofs}", shell=True).split()[0]
            )
            img_mb = (du_kb // 1024) + 48
            ext4_img = f"{td}/apex_payload_ext4.img"
            run(f"dd if=/dev/zero of={ext4_img} bs=1M count={img_mb} status=none")
            run(f"mkfs.ext4 -F -b 4096 -L '' -O ^has_journal {ext4_img} >/dev/null 2>&1")

            mnt_ext4 = f"{td}/mnt_ext4"
            os.makedirs(mnt_ext4, exist_ok=True)
            run(f"mount -o loop {ext4_img} {mnt_ext4}")
            try:
                run(f"cp -a {mnt_erofs}/. {mnt_ext4}/")
                root_ctx = os.getxattr(mnt_erofs, b"security.selinux", follow_symlinks=False)
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

        key_pem = f"{td}/virt_avb.pem"
        pubkey_bin = f"{td}/apex_pubkey"
        run(f"openssl genrsa -out {key_pem} 4096 2>/dev/null")
        run(f"python3 {avbtool} extract_public_key --key {key_pem} --output {pubkey_bin}")
        run(
            f"python3 {avbtool} add_hashtree_footer "
            f"--do_not_generate_fec "
            f"--algorithm SHA256_RSA4096 "
            f"--hash_algorithm sha256 "
            f"--key {key_pem} "
            f"--prop apex.key:com.android.virt "
            f"--image {ext4_img}"
        )
        run(f"python3 {avbtool} verify_image --image {ext4_img} --key {key_pem}")

        out_apex.parent.mkdir(parents=True, exist_ok=True)
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
            f"[OK] Built & signed {out_apex} ({out_apex.stat().st_size} bytes, "
            f"payload offset={off}, mod 4096 == 0)"
        )


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    avbtool = root / "tools" / "avb" / "avbtool.py"
    out_apex = root / "out" / "components" / "com.android.virt.signed.apex"
    pk8, cert = ensure_container_keys(root)

    if len(sys.argv) > 1 and sys.argv[1].endswith(".apex"):
        repack_virt_apex(Path(sys.argv[1]), out_apex, avbtool, pk8, cert)
        return 0

    sys_img = root / "port_rom" / "extracted" / "system.img"
    with tempfile.TemporaryDirectory(prefix="sys_virt_") as td:
        mnt_sys = f"{td}/sys"
        os.makedirs(mnt_sys, exist_ok=True)
        run(f"mount -o loop,ro {sys_img} {mnt_sys}")
        try:
            repack_virt_apex(
                Path(f"{mnt_sys}/system/apex/com.android.virt.apex"),
                out_apex,
                avbtool,
                pk8,
                cert,
            )
        finally:
            run(f"umount {mnt_sys}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

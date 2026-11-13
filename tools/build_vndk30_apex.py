#!/usr/bin/env python3
"""
Build an AVB-signed, APK Signature Scheme v2+v3 signed, 4096-byte-aligned
com.android.vndk.v30.apex for Android 17 using com.android.vndk.v31.apex as
structure template and extracted LineageOS 18.1 com.android.vndk.current payload.
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from repack_virt_apex_ext4 import ensure_container_keys


def run(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=True)


def build_vndk30_apex(root: Path) -> Path:
    avbtool = root / "tools" / "avb" / "avbtool.py"
    sys17_img = root / "port_rom" / "extracted" / "system.img"
    vndk30_tar = root / "base_rom" / "los18_system_extract" / "vndk30_and_vintf.tar"
    out_apex = root / "out" / "components" / "com.android.vndk.v30.signed.apex"

    tmp = "/tmp/build_vndk30"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)

    try:
        # 1. Extract v31 template from Android 17 system.img
        os.makedirs(f"{tmp}/mnt_sys17", exist_ok=True)
        run(f"mount -o loop,ro {sys17_img} {tmp}/mnt_sys17")
        try:
            run(f"unzip -q {tmp}/mnt_sys17/system/system_ext/apex/com.android.vndk.v31.apex -d {tmp}/v31")
        finally:
            run(f"umount {tmp}/mnt_sys17")

        # 2. Extract LineageOS 18.1 VNDK v30 files
        os.makedirs(f"{tmp}/v30_src", exist_ok=True)
        run(f"tar -xf {vndk30_tar} -C {tmp}/v30_src")
        v30_root = f"{tmp}/v30_src/apex/com.android.vndk.current"

        # 3. Patch apex_manifest.pb & AndroidManifest.xml (v31 -> v30, exact same byte length)
        manifest_pb = Path(f"{tmp}/v31/apex_manifest.pb").read_bytes()
        assert b"com.android.vndk.v31" in manifest_pb
        manifest_pb_v30 = manifest_pb.replace(b"com.android.vndk.v31", b"com.android.vndk.v30")

        axml = Path(f"{tmp}/v31/AndroidManifest.xml").read_bytes()
        axml_v30 = axml.replace(b"com.android.vndk.v31", b"com.android.vndk.v30")
        axml_v30 = axml_v30.replace(
            "com.android.vndk.v31".encode("utf-16le"),
            "com.android.vndk.v30".encode("utf-16le"),
        )

        # 4. Create ext4 apex_payload.img
        du_kb = int(subprocess.check_output(f"du -sk {v30_root}", shell=True).split()[0])
        img_mb = (du_kb // 1024) + 24
        payload_img = f"{tmp}/apex_payload.img"
        run(f"dd if=/dev/zero of={payload_img} bs=1M count={img_mb} status=none")
        run(f"mkfs.ext4 -F -b 4096 -L '' -O ^has_journal {payload_img} >/dev/null 2>&1")

        os.makedirs(f"{tmp}/mnt_payload", exist_ok=True)
        run(f"mount -o loop {payload_img} {tmp}/mnt_payload")
        try:
            run(f"cp -a {v30_root}/lib {v30_root}/lib64 {v30_root}/etc {tmp}/mnt_payload/")
            Path(f"{tmp}/mnt_payload/apex_manifest.pb").write_bytes(manifest_pb_v30)
            run(f"chown -R 0:0 {tmp}/mnt_payload")
            run(f"setfattr -n security.selinux -v 'u:object_r:system_file:s0' {tmp}/mnt_payload")
            run(f"find {tmp}/mnt_payload -exec setfattr -h -n security.selinux -v 'u:object_r:system_file:s0' {{}} +")
            run(f"find {tmp}/mnt_payload/lib {tmp}/mnt_payload/lib64 -exec setfattr -h -n security.selinux -v 'u:object_r:system_lib_file:s0' {{}} +")
        finally:
            run(f"umount {tmp}/mnt_payload")

        run(f"e2fsck -fy {payload_img} >/dev/null 2>&1 || true")
        run(f"resize2fs -M {payload_img} >/dev/null 2>&1")
        cur_size = os.path.getsize(payload_img)
        new_size = ((cur_size + 4095) // 4096) * 4096 + (2 * 1024 * 1024)
        with open(payload_img, "ab") as f:
            f.truncate(new_size)

        # 5. Sign apex_payload.img with RSA-4096 AVB hashtree footer
        key_pem = f"{tmp}/vndk30.pem"
        pubkey_bin = f"{tmp}/apex_pubkey"
        run(f"openssl genrsa -out {key_pem} 4096 2>/dev/null")
        run(f"python3 {avbtool} extract_public_key --key {key_pem} --output {pubkey_bin}")
        run(
            f"python3 {avbtool} add_hashtree_footer "
            f"--do_not_generate_fec "
            f"--algorithm SHA256_RSA4096 "
            f"--hash_algorithm sha256 "
            f"--key {key_pem} "
            f"--prop apex.key:com.android.vndk "
            f"--image {payload_img}"
        )
        run(f"python3 {avbtool} verify_image --image {payload_img} --key {key_pem}")

        # 6. Write 4096-byte aligned uncompressed .apex ZIP
        out_apex.parent.mkdir(parents=True, exist_ok=True)
        if out_apex.exists():
            out_apex.unlink()

        files_to_pack = [
            ("apex_manifest.pb", manifest_pb_v30, 4),
            ("AndroidManifest.xml", axml_v30, 4),
            ("apex_pubkey", Path(pubkey_bin).read_bytes(), 4),
            ("apex_payload.img", Path(payload_img).read_bytes(), 4096),
        ]
        if os.path.exists(f"{tmp}/v31/resources.arsc"):
            files_to_pack.insert(2, ("resources.arsc", Path(f"{tmp}/v31/resources.arsc").read_bytes(), 4))

        with zipfile.ZipFile(out_apex, "w", compression=zipfile.ZIP_STORED) as zf:
            for name, data, align in files_to_pack:
                zi = zipfile.ZipInfo(name, date_time=(2009, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_STORED
                zi.external_attr = 0o644 << 16
                cur_offset = zf.fp.tell()
                header_end = cur_offset + 30 + len(name.encode("utf-8"))
                pad = (align - (header_end % align)) % align
                zi.extra = b"\x00" * pad
                zf.writestr(zi, data)

        # 7. Sign outer APEX container with APK Signature Scheme v2+v3
        pk8, cert = ensure_container_keys(root)
        run(
            f"apksigner sign --key {pk8} --cert {cert} "
            f"--v1-signing-enabled false --v2-signing-enabled true --v3-signing-enabled true "
            f"--min-sdk-version 24 {out_apex}"
        )
        idsig = Path(f"{out_apex}.idsig")
        if idsig.exists():
            idsig.unlink()

        raw = out_apex.read_bytes()
        head2k = Path(payload_img).read_bytes()[:2048]
        off = raw.find(head2k)
        assert off > 0 and off % 4096 == 0, f"Misaligned apex_payload.img offset: {off}"
        print(
            f"[OK] Built & signed {out_apex} ({out_apex.stat().st_size} bytes, "
            f"payload offset={off}, mod 4096 == 0)"
        )
        return out_apex
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    build_vndk30_apex(Path(__file__).resolve().parent.parent)
    sys.exit(0)

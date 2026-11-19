# Samsung One UI 6.1 (Android 14) GSI Port Guide for Sony Xperia XZs (`keyaki` / `SO-03J`)

**Language**: [English](#english) | [Tieng Viet](#tieng-viet)

---

<a id="english"></a>
## English

### 1. System Architecture
This branch (`oneui`) adapts a prebuilt **MysticGSI Samsung One UI 6.1** system image ported from **Galaxy A05s (`SM-A057F`, Qualcomm Snapdragon 680 `SM6225` — `ARMv8.0-A`, matching Snapdragon 820 `MSM8996` ISA)** onto the existing Xperia XZs Linux `5.4.302` + `VNDK 30` foundation built on the `android-17` branch:

- **System (`/` / `/system`)**: `Oneui-a05s-14-A057FXXU8CYC6-AB-20250330-MysticGSI.zip` (Android 14, `UP1A.231005.007`, SDK 34), adapted by `tools/build_oneui_a05s_keyaki.py` into `out/system-oneui61-keyaki.sparse.img`.
- **Vendor (`/vendor` on `oem` `mmcblk0p53`)**: Existing `out/oem-a17-keyaki.img` (LineageOS 18.1 Treble Vendor, VNDK 30).
- **Boot / Kernel (`boot` `mmcblk0p30`)**: Existing `out/boot-a17-keyaki.img` (Linux `5.4.302-g32a306e084db-dirty #7` + `keyaki_first_stage_init`).
- **Recovery (`FOTAKernel` `mmcblk0p48`)**: Preserved TWRP recovery (temporarily booted via `fastboot boot work/twrp-kagura.img` for flashing).

---

### 2. Root Causes & Automated Fixes in `tools/build_oneui_a05s_keyaki.py`

1. **Corrupt VNDK Git LFS Pointer Stubs (`v31`, `v32`)**:
   - `/system/apex/com.android.vndk.v31.apex` and `v32.apex` in the upstream archive were 133-byte Git LFS text stubs (`git-lfs`), while `com.android.vndk.v30.apex` (`ext4`) was valid. Removed `v31`/`v32` stubs and preserved `v30`.
2. **EROFS APEX Unsupported by Kernel**:
   - `/system/apex/com.samsung.android.shell.apex` shipped with an `EROFS` payload (`EROFS` is disabled in the `keyaki` Linux 5.4 kernel). Repacked payload into `ext4`, re-signed with AVB (`SHA256_RSA4096` + `--prop apex.key:com.samsung.android.apex`) and outer APK Signature Scheme v2/v3 with 4096-byte payload alignment.
3. **`vndk-detect` Missing `vendor_sepolicy.cil`**:
   - Patched `/system/bin/vndk-detect` to inspect `/vendor/etc/selinux/vendor_sepolicy.cil` alongside `nonplat_sepolicy.cil` so `persist.sys.vndk=30` resolves cleanly on `oem`.
4. **`/system/bin/bpfloader` Rejecting `schedcls/` BPF Programs (`reboot,bpfloader-failed`)**:
   - `semUidBPF.o`, `semSmartHS.o`, and `mnxbNetd.o` in `/system/etc/bpf/` contain `BPF_PROG_TYPE_SCHED_CLS` (`3`) sections, which `bpfloader` rejected (`exit=2`) because its `/system/etc/bpf/` `allowedProgTypes` table at file offset `0x1978..0x198c` was `(2, 7, 1, 5, 0)`. Patched `0x1988` from `00000000` to `03000000` while preserving `0:2000`, `0755`, and `u:object_r:bpfloader_exec:s0`.
5. **VINTF & SELinux VNDK 30 Compatibility**:
   - Patched `compatibility_matrix.5.xml` / `4.xml` (`android.hardware.graphics.mapper` `2.1` -> `2.0-1`, stripped `<kernel>` elements), added `<vendor-ndk><version>30</version></vendor-ndk>` to `/system/system_ext/etc/vintf/manifest.xml`, generated empty `30.0.cil` / `30.0.compat.cil` stubs for `system_ext` and `product`, and verified offline `secilc` compilation against `oem-a17-keyaki.img`.
6. **Linux 5.4 Cgroups & Audio Configs**:
   - Installed `configs/cgroups/cgroups.json` to `/system/etc/cgroups.json`. Copied `/system/etc/audio_effects.xml` to `/system/etc/audio_effects_sec.xml` and stripped `STAGE_EFFECT_DOLBY` lines from `/system/etc/stage_policy.conf`.
7. **Samsung Services Incompatible with Non-Samsung Hardware (`KnoxGuard` Code `3010`)**:
   - Removed `/system/priv-app/SamsungDeviceHealthManagerService` (repeated vendor crashes) and `/system/priv-app/KnoxGuard`.
   - *Root cause of `code 3010`*: On `keyaki` (`ro.product.first_api_level=25 < 30`), `SystemServer` registers `KnoxGuardService`, which accepts a missing `com.samsung.android.kgclient` when RLC state is `null`. However, `KnoxGuard.apk` checks `ro.product.first_api_level < 30` upon `BOOT_COMPLETED`/`SETUPWIZARD_COMPLETE` and invokes `IKnoxGuardManager.setRemoteLockToLockscreen(...)` with error `"3010"`, writing `3locked=true` into `locksettings.db`.
8. **Wi-Fi 4-Way Handshake `WRONG_KEY` Timeouts (`brcmfmac` BCM4359 + Connected MAC Randomization)**:
   - Samsung static RROs `WifiRROverlayApp`, `WifiRROverlayAppH2E`, and `WifiRROverlayJdm` force `config_wifi_connected_mac_randomization_supported=true` and `config_wifiSaveFactoryMacToConfigStoreEnabled=false`. On `brcmfmac`, changing `wlan0` `cur_etheraddr` while active caused `wlan0` address, `mRandomizedMacAddress`, and `mWifiInfo` MAC to diverge, causing WPA2 `EAPOL-Key 2/4` 4-way handshake timeouts (`WRONG_KEY`).
   - Removed `app/WifiRROverlayApp`, `app/WifiRROverlayAppH2E`, and `app/WifiRROverlayJdm` so AOSP `ServiceWifiResources.apk` defaults apply (`first_byte_locally_admin=0` factory MAC restored after reboot).
9. **ConfigFS USB Gadget & Direct ADB**:
   - Uncommented AOSP USB ConfigFS triggers in `/system/etc/init/hw/init.usb.configfs.rc`, set `persist.sys.usb.config=adb` in `/system/product/etc/build.prop` and `/system/build.prop`, appended `configs/props/system_keyaki.prop` + `ro.opengles.version=196610`, and changed `resetprop_phh ro.adb.secure 1` to `resetprop_phh ro.adb.secure 0` in `/system/bin/rw-system.sh`.

---

### 3. Reproducible Build & Flash Instructions

#### Build `out/system-oneui61-keyaki.sparse.img`
1. Place the base One UI 6.1 zip (`SHA-256: 04f01b0b8de62a4a5cce33ec97052b1403140ea3d6173037cbeb2461f0928e4e`) in `oneui_work/` and extract `system.img` there.
2. Ensure `out/oem-a17-keyaki.img` and `out/boot-a17-keyaki.img` exist (from the `android-17` build pipeline).
3. Inside the Ubuntu 22.04 `aarch64` privileged container (`xzs17-box`):
   ```bash
   docker exec xzs17-box python3 /work/tools/build_oneui_a05s_keyaki.py
   ```
   Output: `out/system-oneui61-keyaki.sparse.img` (sized `5200M` raw ext4 -> ~`4.02 GiB` sparse, under the `7,707,033,600`-byte `mmcblk0p55` limit).

#### Flash via TWRP Staging on `/data`
Because the `4.02 GiB` sparse image exceeds TWRP's `/tmp` tmpfs (`~1.8 GiB` on `3.68 GiB` total RAM), stage the sparse image on `userdata` (`/dev/block/mmcblk0p54`) before writing to `system` (`/dev/block/mmcblk0p55`):

1. Boot TWRP via Fastboot (assuming `boot` `mmcblk0p30` and `oem` `mmcblk0p53` already hold `boot-a17-keyaki.img` and `oem-a17-keyaki.img`):
   ```bash
   fastboot boot work/twrp-kagura.img
   adb wait-for-recovery
   ```
2. Format `userdata` cleanly and mount `/data` as staging, push `out/system-oneui61-keyaki.sparse.img`, and flash `/dev/block/mmcblk0p55`:
   ```bash
   adb shell "umount /data /system /system_root /cache 2>/dev/null || true; /sbin/mke2fs -F -t ext4 -b 4096 /dev/block/mmcblk0p54; mkdir -p /data; mount -o rw /dev/block/mmcblk0p54 /data"
   adb push out/system-oneui61-keyaki.sparse.img /data/sys.sparse.img
   adb shell "/sbin/simg2img /data/sys.sparse.img /dev/block/mmcblk0p55 && sync && /sbin/e2fsck -fn /dev/block/mmcblk0p55"
   ```
3. Cleanly reformat `userdata` (`mmcblk0p54`) and `cache` (`mmcblk0p43`) and reboot:
   ```bash
   adb shell "rm -f /data/sys.sparse.img; umount /data; /sbin/mke2fs -F -t ext4 -b 4096 /dev/block/mmcblk0p54; /sbin/mke2fs -F -t ext4 -b 4096 /dev/block/mmcblk0p43; sync"
   adb reboot
   ```
4. Allow ~3–5 minutes on first boot for `odsign` and `ArtService` first-boot `dexopt`.

---

<a id="tieng-viet"></a>
## Tieng Viet

### 1. Kien Truc He Thong
Nhanh `oneui` nay chay phien ban **MysticGSI Samsung One UI 6.1** port tu **Galaxy A05s (`SM-A057F`, Snapdragon 680 `SM6225` — tap lenh thuan `ARMv8.0-A` tuong thich Snapdragon 820 `MSM8996`)** tren nen kernel Linux `5.4.302` va vendor `VNDK 30` da xay dung tu nhanh `android-17`:

- **System (`/` / `/system`)**: `Oneui-a05s-14-A057FXXU8CYC6-AB-20250330-MysticGSI.zip` (Android 14, `UP1A.231005.007`, SDK 34), duoc script `tools/build_oneui_a05s_keyaki.py` dong goi thanh `out/system-oneui61-keyaki.sparse.img`.
- **Vendor (`/vendor` tren `oem` `mmcblk0p53`)**: Dung lai `out/oem-a17-keyaki.img` (LineageOS 18.1 Treble Vendor, VNDK 30).
- **Boot / Kernel (`boot` `mmcblk0p30`)**: Dung lai `out/boot-a17-keyaki.img` (Linux `5.4.302-g32a306e084db-dirty #7` + `keyaki_first_stage_init`).
- **Recovery (`FOTAKernel` `mmcblk0p48`)**: Giu nguyen phan vung TWRP (chi `fastboot boot work/twrp-kagura.img` khi can flash).

### 2. Nguyen Nhan Goc Va Ban Va Tu Dong Trong `tools/build_oneui_a05s_keyaki.py`

1. **Xoa stub Git LFS loi (`v31`, `v32`)**: Go `/system/apex/com.android.vndk.v31.apex` va `v32.apex` (chi la file pointer 133 byte `git-lfs`), giu lai `com.android.vndk.v30.apex` (`ext4`).
2. **Chuyen `com.samsung.android.shell.apex` tu EROFS sang `ext4`**: Kernel 5.4 cho `keyaki` khong bat EROFS nen can dong goi lai payload sang `ext4`, ky lai AVB (`SHA256_RSA4096`) + APK v2/v3 can le 4096 byte.
3. **Va `/system/bin/vndk-detect`**: Bo sung doc `/vendor/etc/selinux/vendor_sepolicy.cil` de nhan dung `persist.sys.vndk=30`.
4. **Va `/system/bin/bpfloader` (`reboot,bpfloader-failed`)**: Cap nhat 4 byte tai offset `0x1988` (`00000000` -> `03000000`) cho phep `BPF_PROG_TYPE_SCHED_CLS` (`3`) trong `/system/etc/bpf/` cho `semUidBPF.o`, `semSmartHS.o` va `mnxbNetd.o`.
5. **Tuong thich VINTF & SELinux VNDK 30**: Sua `compatibility_matrix.5.xml` / `4.xml` (`graphics.mapper` `2.0-1`), them `<vendor-ndk><version>30</version></vendor-ndk>` vao manifest `system_ext`, tao `30.0.cil` / `30.0.compat.cil` va kiem tra `secilc` offline voi `oem-a17-keyaki.img`.
6. **Cgroups & Audio**: Cai dat `configs/cgroups/cgroups.json`, sao chep `audio_effects.xml` thanh `audio_effects_sec.xml` va loai bo cac dong `STAGE_EFFECT_DOLBY` trong `stage_policy.conf`.
7. **Go `SamsungDeviceHealthManagerService` va `KnoxGuard` (loi khoa `code 3010`)**:
   - Tren may co `ro.product.first_api_level=25 < 30`, `SystemServer` khoi tao `KnoxGuardService` (khong bat buoc co `KnoxGuard.apk`), nhung chinh `KnoxGuard.apk` (`com.samsung.android.kgclient`) lai kiem tra `first_api_level < 30` khi Setup Wizard xong va goi `setRemoteLockToLockscreen` kem ma `"3010"`. Go `/system/priv-app/KnoxGuard` triet tieu hoan toan khoa `3010`.
8. **Go 3 overlay Wi-Fi RRO gay loi sai mat khau (`WRONG_KEY`)**:
   - Cac RRO tinh `WifiRROverlayApp`, `WifiRROverlayAppH2E`, `WifiRROverlayJdm` ep bat `Connected MAC Randomization` khien dia chi MAC giao dien `wlan0` (`brcmfmac`) lech voi `mRandomizedMacAddress` / `mWifiInfo`, dan toi timeout khung `EAPOL-Key 2/4` (`WRONG_KEY`). Go 3 thu muc RRO nay khoi phuc hanh vi mac dinh cua `ServiceWifiResources.apk` va tra `wlan0` ve MAC goc phan cung (`first_byte_locally_admin=0` sau khi reboot).
9. **Bat USB ConfigFS ADB**: Bo comment cac trigger ConfigFS trong `/system/etc/init/hw/init.usb.configfs.rc`, dat `persist.sys.usb.config=adb`, them `ro.opengles.version=196610`, va doi `resetprop_phh ro.adb.secure 1` thanh `resetprop_phh ro.adb.secure 0` trong `/system/bin/rw-system.sh`.

### 3. Huong Dan Build Lai Va Flash
- Build trong container `xzs17-box`: `docker exec xzs17-box python3 /work/tools/build_oneui_a05s_keyaki.py`
- Flash qua TWRP bang cach stage tam anh sparse (`4.02 GiB`, lon hon RAM `3.68 GiB`) tren `/data` (`mmcblk0p54`), dung `/sbin/simg2img /data/sys.sparse.img /dev/block/mmcblk0p55`, kiem tra `e2fsck -fn /dev/block/mmcblk0p55`, sau do format sach lai `userdata` (`mmcblk0p54`) va `cache` (`mmcblk0p43`) truoc khi reboot.

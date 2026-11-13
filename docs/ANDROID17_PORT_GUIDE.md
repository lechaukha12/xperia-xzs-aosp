# Technical Porting Guide: Android 17 AOSP on Sony Xperia XZs (`keyaki` / `SO-03J`)

**Language**: **English (Default)** | [Tiếng Việt (ANDROID17_PORT_GUIDE.vi.md)](ANDROID17_PORT_GUIDE.vi.md)

**2026-11-13 update:** build-7 kernel, both cameras and Bluetooth working; Developer options crash fixed. Current verification and artifact manifest: [release notes](SETTINGS_CAMERA_BRINGUP.md).

## 1. Overview and Architectural Scope

This document details the end-to-end engineering analysis, architectural barriers spanning **seven Android generations** (from legacy non-A/B Android 8.0 / Android 11 Project Treble VNDK 30 up to **Android 17 "Cinnamon Bun" — `CP3A.260905.010`, SDK 37 / API 37.1**), and the deterministic solutions verified on live **Sony Xperia XZs (`SO-03J` / `keyaki`, Qualcomm Snapdragon 820 `MSM8996`, Sony `tone` platform)** hardware.

### Port Component Matrix
| Component | Version / Source | Target Partition | Engineering Role |
| :--- | :--- | :--- | :--- |
| **System (OS)** | Google Android 17 AOSP ARM64 GSI (`CP3A.260905.010`, SDK `37`) | `system` (`mmcblk0p55`, `7.18 GiB`) | Expanded `2.6 GiB` ext4, unshared blocks, custom signed `vndk.v30` + ext4 `virt` APEXes, generated SELinux `30.0.cil` |
| **Vendor (HAL)** | LineageOS 18.1 Treble Vendor (`tone` / `keyaki`, VNDK `30`) | `oem` (`mmcblk0p53`, `400 MiB`) | Mounted directly at `/vendor` during First-Stage Init |
| **Kernel** | Linux `5.4.302-g32a306e084db-dirty (#7)` (`nec093/sov35-kernel`) | `boot` (`mmcblk0p30`, `64 MiB`) | eBPF, cgroup v2, 17 `msm8996-tasha` audio DLKM modules, `brcmfmac` PCIe Wi-Fi |
| **First-Stage Init** | Custom static C (`tools/keyaki_first_stage_init.c`) | `boot` ramdisk (`/init`) | Creates eMMC + RPMB device nodes, mounts `/system` & `/vendor`, executes `SwitchRoot`, maintains permissive shadow |
| **Fallback Recovery** | TWRP `3.7.0_9-0` (Linux `3.18.71`) (`FOTAKernel`) | `FOTAKernel` (`mmcblk0p48`, `64 MiB`) | Untouched standalone recovery (`adb reboot recovery` or `Power + Volume Down`) |

> [!CAUTION]
> Never write to sensitive Sony or Qualcomm partitions: `TA` (`mmcblk0p1` — DRM keys and calibration), `aboot` (`mmcblk0p13` — `S1_Boot`), `FOTAKernel` (`mmcblk0p48`), `modemst1`, `modemst2`, `persist`, and `fsg`.

---

## 2. Core Bring-Up Root Causes and Deterministic Solutions

### 2.1. Sony `S1_Boot` Boot Image Header Rejection (Black Screen + Solid Green LED)
- **Root Cause**: Sony's `S1_Boot` bootloader on `MSM8996` strictly validates the appended `msm8996-tone-keyaki` DTB format in `Image.gz-dtb` and the `os_version` field in Android Boot Image Header v0. Setting `--os_version 17.0.0` causes `S1_Boot` to stall early with a solid green LED before kernel decompression.
- **Solution**: Package the verified `prebuilt/Image.gz-dtb` (`5.4.302-xzs54`) with exact `keyaki` offsets (`base=0x80000000`, `kernel_offset=0x8000`, `ramdisk_offset=0x2000000`, `tags_offset=0x1e00000`, `pagesize=4096`) and `--os_version 10.0.0 --os_patch_level 2020-03`.

### 2.2. Legacy Non-2SI First-Stage Init, `/metadata`, and SELinux Shadow on `user` GSI
- **Root Cause**:
  1. Xperia XZs uses a legacy non-A/B, non-dynamic partition table with no dedicated `/metadata` partition and `/vendor` stored on `oem` (`mmcblk0p53`).
  2. Official Google Android 17 GSIs (`CP3A.260905.010`) are `user` builds (`ALLOW_PERMISSIVE_SELINUX=0`), where `init` unconditionally writes `'1'` to `/sys/fs/selinux/enforce` regardless of `androidboot.selinux=permissive` on the kernel command line.
- **Solution (`tools/keyaki_first_stage_init.c`)**:
  - Built a lightweight static C binary running as PID 1 in the boot ramdisk. It scans `/sys/block/mmcblk0` and `/sys/bus/mmc/devices/mmc0:0001/mmcblk0rpmb` to create `/dev/block/.../by-name/*` and `/dev/mmcblk0rpmb` nodes early.
  - Mounts `tmpfs` at `/metadata` and `/second_stage_resources` (`ro.boot.dynamic_partitions=false`).
  - Mounts `/dev/block/mmcblk0p55` at `/system_root` and `/dev/block/mmcblk0p53` at `/system_root/vendor`, moves early virtual mounts (`MS_MOVE`), and performs `SwitchRoot` (`chroot`) into `/system/bin/init selinux_setup`.
  - Bind-mounts `/dev/.selinux_enforce_shadow` over `/sys/fs/selinux/enforce` during early bring-up so the kernel remains permissive for legacy MSM8996 HAL daemons while userspace `init` completes `selinux_setup` cleanly.

### 2.3. Missing SELinux `30.0.cil`, VINTF Matrix 5, and VNDK v30 APEX in Android 17
- **Root Cause**: Android 17 drops `com.android.vndk.v30.apex`, `/system/etc/selinux/mapping/30.0.cil`, and `compatibility_matrix.5.xml`, all of which are required by an Android 11 (`VNDK 30`, VINTF target-level `5`) vendor partition.
- **Solution (`tools/build_vndk30_apex.py` & `tools/build_system_and_boot_a17.py`)**:
  - Repacked LineageOS 18.1 VNDK v30 libraries into a 4096-byte-aligned `com.android.vndk.v30.signed.apex` signed with both AVB (`SHA256_RSA4096` hashtree) and outer APK Signature Scheme v2/v3.
  - Programmatically synthesized `/system/etc/selinux/mapping/30.0.cil` and `30.0.compat.cil` (handling split Android 11 attributes such as `ffs_prop`, `exported_*_prop`, and `cgroup_bpf`), verified offline during every image build by executing Android 17's own `/system/bin/secilc` at policy version `31`.
  - Restored `compatibility_matrix.5.xml` with `android.hardware.graphics.mapper@2.0-1` allowed and legacy 4.x kernel locks removed.

### 2.4. `com.android.virt.apex` EROFS Payload and Outer APK v2/v3 Signature Enforcement
- **Root Cause**:
  1. Android 17 ships `com.android.virt.apex` with a compressed `EROFS` payload, causing `apexd` to fail mounting APEXes when `CONFIG_EROFS_FS` is absent in the kernel.
  2. While `apexd` only checks the inner `apex_payload.img` AVB footer, `SystemServer`'s `PackageManagerService` (`scanApexPackagesTraced`) enforces outer ZIP **APK Signature Scheme v2/v3** (`minSdkVersion 24`) on every `.apex`, aborting `SystemServer` with `No APK Signature Scheme v2 signature` if unsigned.
- **Solution (`tools/repack_virt_apex_ext4.py`)**:
  - Extracted the EROFS payload (preserving all per-binary `security.selinux` labels such as `crosvm_exec` and `early_virtmgr_exec`) into an `ext4` (`-b 4096 -O ^has_journal`) image, signed its AVB hashtree, packed an uncompressed 4096-byte-aligned `.apex`, and signed both `virt` and `vndk.v30` APEX containers with `apksigner` (`--v1-signing-enabled false --v2-signing-enabled true --v3-signing-enabled true --min-sdk-version 24`). All 45/45 APEX packages verify in `0.95s`.

### 2.5. `cgroups.json` Mandatory Controllers on Linux 5.4
- **Root Cause**: Android 17 marks `blkio` (cgroup v1) and `freezer` (cgroup v2) as mandatory in `/system/etc/cgroups.json`. When absent or differently configured on Linux 5.4, `libprocessgroup` aborts cgroup setup early before activating the cgroup v2 `memory` controller.
- **Solution (`configs/cgroups/cgroups.json`)**: Added `"Optional": true` to both `blkio` and `freezer`.

### 2.6. Mainline eBPF (`NetBpfLoad` + `.android_progs` KVER Gates) on Linux 5.4.302
- **Root Cause**: Android 17's `com.android.tethering` module enforces a higher minimum kernel check in `NetBpfLoad`, and its `netd.o` / `offload.o` objects ship both clean non-BTF `4.19..5.4.0` programs (`min_kver=0x04130000`, `max_kver=0x05040000`) and newer `5.4.0+` ringbuf/CO-RE programs (`min_kver=0x05040000`). On Linux `5.4.302` (`0x0504012e > 0x05040000`), `NetBpfLoad` skips the `4.19` programs and attempts to load the `5.4.0+` programs whose helpers/maps are unavailable on `sov35-kernel` 5.4.
- **Solution (`tools/patch_bpf_54.py` & `configs/init/netbpfload.rc`)**:
  - Patched the kernel version branch in `netbpfload_54` (`0x98c4` and `0xa598`).
  - Patched `.android_progs` in `netd.o` and `offload.o` to disable the incompatible `5.4.0+` entries (`0xffffffff`) and extend `max_kver` of the verified `4.19` non-BTF entries to `5.10.0` (`0x050a0000`), bind-mounted in `on load-bpf-programs`. Result: `bpf.progs_loaded=1` and `netd` starts cleanly.

### 2.7. Missing `BPF_MAP_TYPE_RINGBUF` in `ConnectivityService` (`libservice-connectivity.so`)
- **Root Cause**: Linux `5.4` predates `BPF_MAP_TYPE_RINGBUF` (introduced in Linux `5.8`). Android 17's `/apex/com.android.tethering/lib64/libservice-connectivity.so` calls `abort()` in two places when those ringbuf maps do not exist:
  1. `LocalNetEventHandler::GetRingbuf()` (`map_netd_local_net_note_op_ringbuf`) during `ConnectivityService.<init>`, while `LocalNetEventListener.start()` passes the returned `FileDescriptor` into `MessageQueue.addOnFileDescriptorEventListener()` (which throws `IllegalArgumentException` if `null`).
  2. `LoopbackEventHandler::GetPoller()` (`map_netd_loopback_access_ringbuf`) during `ConnectivityService.systemReady()`.
- **Solution (`tools/patch_tethering_54.py`)**:
  - Patched `nativeGetLocalNetAccessRingbufFd` (`0xdf18..0xdf28`) to return a valid, idle `eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK)` via `eventfd@plt` (`0x15130`), satisfying `MessageQueue` epoll registration with zero CPU wakeups.
  - Patched `nativeConsumeAllLocalNetAccessEvents` (`0xe2b0`) to return an empty `int[0]`.
  - Patched the `LoopbackEventHandler::GetPoller()` initializer lambda (`0x11f10..0x11f18`) to `mov x0, xzr; autiasp; ret` (`nullptr`), leveraging `LoopbackEventHandler`'s built-in `nullptr` guard.

### 2.8. Restoring Gralloc 2.0/3.0 Graphics Support on SDK 37 (`libui.so`) & Adreno 530 EGL
- **Root Cause**:
  1. Missing `ro.hardware.egl=adreno` prevented `libEGL` from locating `/vendor/lib64/egl/libGLESv2_adreno.so`.
  2. In Android 17 (`SDK 37`), `GraphicBufferMapper` and `preloadHal()` inside `libui.so` call `android_get_device_api_level()` (returning `37`), compare `cmp w0, #0x23` (`SDK 35`), and skip `Gralloc3Mapper` / `Gralloc2Mapper` completely (`b.gt`), crashing `SurfaceFlinger` with `gralloc-mapper is missing`.
  3. Vendor `manifest.xml` also advertised unimplemented `@3.0` and `@4.0::IMapper/default` entries alongside `@2.0`.
- **Solution (`tools/patch_libui_gralloc2.py` & `tools/build_vendor_oem.sh`)**:
  - Added `ro.hardware.egl=adreno` and stripped unimplemented `@3.0`/`@4.0` `IMapper` entries from `/vendor/etc/vintf/manifest.xml`.
  - Replaced the `b.gt` instruction immediately following `cmp w0, #0x23` with `nop` in 64-bit (`0x34d98`, `0x5a1f4`) and 32-bit (`0x2184a`, `0x3e670`) `/system/lib*/libui.so` as well as `com.android.media.swcodec`'s `libui.so`. Result: **Adreno 530 OpenGL ES 3.2**, **Gralloc 2.0**, and **HWComposer 2.1 (`DEVICE` composition)** render at full **1080x1920 @ 60 Hz**.

### 2.9. USB FunctionFS `adbd` SELinux Property Denial on `user` GSI
- **Root Cause**: Setting `service.adb.root=1` on a `user` GSI transitions `adbd` into `u:r:su:s0`. Because `init`'s userspace `property_service` checks SELinux property permissions even when the kernel is permissive—and `su` has zero property write rules in `user` sepolicy—`adbd` is denied setting `sys.usb.ffs.ready=1`, preventing USB gadget binding.
- **Solution**: Set `service.adb.root=0` in `configs/props/system_keyaki.prop` so `adbd` runs in its standard `u:r:adbd:s0` domain and binds ConfigFS gadget `0x4EE7` reliably ~22s into boot.

### 2.10. Audio DLKMs (`wcd9335` + `wsa881x`), PCIe Wi-Fi (`brcmfmac`), and Nougat Modem Guard
- **Audio**: Compiled and installed all 17 Linux `5.4.302` Qualcomm audio DLKM modules into `/vendor/lib/modules` with `keyaki`'s stereo `mixer_paths_tasha.xml`.
- **Wi-Fi**: Installed `/vendor/firmware/brcm/brcmfmac4359-pcie.bin` + `somc,keyaki` NVRAM files and redirected legacy `bcmdhd` `/sys/module/bcmdhd/parameters/firmware_path` writes in `/vendor/lib64/libwifi-hal.so` to `/dev/null` for mainline `brcmfmac` compatibility.
- **Modem Guard**: Bind-mounted `/dev/null` over `/vendor/firmware_mnt/image/modem.mdt` in `configs/init/init.keyaki.rc` to prevent legacy Nougat (`LA2.0_N_117`) modem IPA/SSR crashes until baseband firmware is upgraded to Oreo.

---

### 2.11. Developer Options on a Debuggable User GSI

Settings crashed while setting `logd.logpersistd=clear`: the port enables
`ro.debuggable=1`, exposing a controller omitted from user-policy permissions.
`patch_settings_logpersist_policy.py` grants only the required
`logpersistd_logging_prop` access to `system_app`, preserving file metadata.
Offline secilc passed and the actual Developer options page was verified.

### 2.12. Camera Media ABI and Correct Sensors

The legacy HAL expects subdevice type `0x20000` plus numeric group IDs. The 5.4
camera tree instead uses functions `0x10fxx`. The camera mapping patch restores
legacy ENUM_ENTITIES output for `msm_config` subdevices and `msm_camera` video
nodes (group 2), including the CSID/buffer-manager group swap. Native/compat
probes agree. Vendor XMLs must use keyaki IMX400/IMX258, matching real chip IDs,
instead of the donor IMX300/IMX214 configuration. Both sensors then probe and
CameraService exposes IDs 0 and 1. Full strace was removed before functional
preview verification; the owner confirmed both cameras work.

### 2.13. Bluetooth Preservation and Release Artifacts

The existing `build_vendor_oem.sh` UART LPM workaround for BCM4359 is retained.
The owner confirmed Bluetooth working, with ON/zero-crash status observed.
Production vendor resets temporary camera debug levels to 0 and omits all probe
executables. Use the explicitly selected camera kernel when rebuilding boot.
See [release notes](SETTINGS_CAMERA_BRINGUP.md) for checksums, verification scope,
reproduction commands and the guarded boot/OEM recovery installer.

## 3. Live Verification Summary

- **OS & Boot**: Android `17` (`CP3A.260905.010`, SDK `37`, Security Patch `2026-09-05`), standalone eMMC cold boot to `sys.boot_completed=1` in **~38 seconds**, **0 crashes** in `logcat -b crash`.
- **Display & Graphics**: `SurfaceFlinger` + `HWComposer 2.1` (`DEVICE` hardware composition) + **Qualcomm Adreno 530** (`OpenGL ES 3.2 V@415.0`), `1080x1920 @ 60 Hz`, responsive Synaptics `clearpad` multitouch.
- **Wi-Fi & Audio**: `brcmfmac` (`wlan0`) enables and scans 2.4/5 GHz APs; `msm8996-tasha-mtp-snd-card` (`48000 Hz` stereo) active in `AudioFlinger`.
- **Storage & Sensors**: `/data` (`~20.8 GiB` ext4 rw with `fsverity`), `1 GiB` `zram0` swap, and full hardware sensor suite (`BMI160`, `AK09915`, `APDS-9940`, `HSPPAD042A`) verified via `SensorService`.

# Camera, Bluetooth and Settings update — 2026-11-13

## English

### Final installation verified

On 2026-11-13 the release images were permanently written to boot and OEM from
root TWRP. Read-back SHA-256 matched all 12,402,688 bytes of the boot image and
all 419,430,400 bytes of OEM. The existing Settings policy on system was also
hash-verified. Userdata and the standalone FOTAKernel recovery were preserved.

Android then booted from eMMC with `sys.boot_completed=1`, kernel build 7 and two
camera devices. The post-flash camera session delivered 37 preview frames and
42 ImageReader frames before the app was closed. Bluetooth remained ON with
zero recorded crashes; the Developer options page opened correctly and the
crash buffer was empty. The final record is in the release manifest under
`deployment.post_flash_checks`.

### Verified result

- Android 17 (`CP3A.260905.010`, SDK 37) boots from eMMC using
  `5.4.302-g32a306e084db-dirty`, kernel build 7.
- CameraService exposes two public cameras: rear IMX400 (ID 0), front IMX258
  (ID 1), through the legacy HIDL provider. Both sensors pass hardware ID probing.
- Rear preview was observed directly; the untraced camera dump recorded 211
  preview frames and 216 ImageReader frames. The owner confirmed that both
  cameras work. Torch, video recording and high-speed modes were not separately
  verified in this session.
- Bluetooth was confirmed working by the owner; the observed stack remained ON
  with zero recorded crashes. Its existing UART LPM patch is preserved.
- Developer options opens and displays its actual Settings page without the
  original property-write crash. Individual developer settings were not all tested.
- Strace, its provider wrapper and both media-probe executables were removed
  from vendor. `init.keyaki.camera.rc` resets the three temporary camera debug
  properties to 0. Private diagnostic logs remain excluded from Git.

### Fixes and evidence

1. **Legacy media-controller enumeration.** The 5.4 tree encodes private camera
   kinds in `entity.function` at `0x10f00`, while the shipped HAL searches for
   legacy type `0x20000` and numeric `group_id`. Earlier small-integer mapping
   did not match the real values. `patch_camera_media_legacy.py` translates
   subdevices in `msm_config` and video nodes in both `msm_config` and
   `msm_camera`. It restores CSID group 1, buffer-manager group 13 and video
   group 2. The modern topology function values remain intact. Independent
   ARM32/ARM64 probes agreed before and after the change. See the
   [legacy Qualcomm definitions](https://android.googlesource.com/kernel/msm/+/52d38cbdd40c2e334ceb69e8121d1f86095704e7/include/uapi/media/msmb_camera.h)
   and local `base_rom/device-tone-common/camera/QCamera2/stack/mm-camera-interface/src/mm_camera_interface.c`.
2. **Correct keyaki sensors.** The donor vendor XML requested IMX300/IMX214.
   I2C reads returned actual IDs `0x400`/`0x258`. Installing `camera_config.xml`,
   `imx400_chromatix.xml` and `imx258_chromatix.xml` from
   `base_rom/device-keyaki/rootdir/vendor/etc/camera/` made both probes succeed.
   The vendor builder now installs these three files, preserving root:root,
   mode 0644 and NUL-terminated `vendor_configs_file` SELinux labels.
3. **Remove intrusive tracing for functional tests.** With full syscall tracing and verbose logs enabled, frame-request delays and
   buffer errors were observed; the app remained on its loading screen.
   With the wrapper removed, live preview and advancing frame counters were observed.
   Do not ship `prepare_camera_trace.py` output as production vendor configuration.
4. **Developer options permission.** This port exposes the logpersist controller
   through `ro.debuggable=1`, but the user GSI omits its `system_app` permission.
   `patch_settings_logpersist_policy.py` grants only property-set and property-file
   read access for `logpersistd_logging_prop`. It is integrated before the system
   builder's offline compilation. Full Android 17 secilc compilation at policy
   version 31 passed (1,561,208-byte policy). The installed CIL hash is
   `92d5d8a3161f99d458e9f1e9df727ae5c9f5902d0cf748fe60d466265cf3aee3`.

### Images and reproduction

Production artifact names under `out/` are:

- `boot-a17-keyaki.img`: build-7 camera kernel, unchanged verified ramdisk/load header.
- `oem-a17-keyaki.img`: raw 400 MiB snapshot of the working vendor after diagnostic
  removal, retaining the live Bluetooth/audio modules and keyaki camera XMLs.
- `oem-a17-keyaki.sparse.img`: sparse form of the same vendor filesystem.
- `system-a17-keyaki.sparse.img`: system image including the Settings policy fix.
- `SHA256SUMS.txt`: checksums of these four images. The release manifest is
  `manifests/camera-settings-release-20261113.json`.

The initial `prebuilt/Image.gz-dtb` is retained as a historical boot baseline.
Select the camera-capable kernel explicitly when running the full system/boot builder:

```sh
docker exec xzs17-box bash /work/tools/build_kernel_a17.sh
docker exec xzs17-box bash /work/tools/build_vendor_oem.sh
docker exec -e XZS17_KERNEL_IMAGE=/work/out/kernel_a17/Image.gz-dtb \
  xzs17-box python3 /work/tools/build_system_and_boot_a17.py
```

This rebuilds the kernel and repacks existing Android images; it does not compile
Android 17 from scratch. `replace_boot_kernel.py` can instead replace only the
kernel in an existing boot image, verifying that ramdisk and load parameters match.

### Installing this update on the current device

The Settings CIL patch is already installed on system. The completed final
installation wrote boot and OEM, with read-back hashes covering every written byte.
It preserves userdata and the standalone TWRP in FOTAKernel. A fresh installation
from another ROM uses the full three-image Fastboot procedure in the README.

From root TWRP, after checking `out/SHA256SUMS.txt`:

```sh
python3 tools/flash_keyaki_images_recovery.py out/boot-a17-keyaki.img \
  --backup backup/checkpoints/codex-takeover-20261113-104445/boot-live.img \
  --oem out/oem-a17-keyaki.img \
  --oem-backup backup/checkpoints/codex-takeover-20261113-104445/oem-live.img
adb reboot
```

The helper requires existing full backups, checks root recovery and exact
partition mappings/sizes, rejects mounted targets and sparse OEM input, verifies
transfer hashes, writes only boot `mmcblk0p30` and OEM `mmcblk0p53`, and verifies
read-back. It does not reboot on its own. Old TWRP does not support `dd conv=fsync`;
the helper uses a separate `sync`. If verification fails, remain in TWRP.

Automatic recovery reboots have intermittently failed to enumerate USB. Use a
physical-key recovery entry when needed. Never overwrite FOTAKernel, TA,
bootloader or calibration partitions. The original boot/vendor checkpoint and
`boot-media-enum-verified.img` are retained under `backup/checkpoints/`.

## Tiếng Việt

### Đã xác minh lần nạp chính thức

Ngày 13/11/2026 đã ghi vĩnh viễn image phát hành vào boot và OEM qua root TWRP.
SHA-256 đọc lại khớp đủ 12.402.688 byte image boot và toàn bộ 419.430.400 byte
OEM. Hash policy Settings đã có trên system cũng được xác minh. Userdata và
recovery độc lập FOTAKernel được giữ nguyên.

Sau đó Android boot từ eMMC với `sys.boot_completed=1`, kernel số 7 và hai
camera. Phiên camera sau flash đã trả 37 frame preview và 42 frame ImageReader
trước khi ứng dụng đóng. Bluetooth vẫn ON, crash bằng 0; Developer options mở
đúng trang và crash buffer trống. Bản ghi cuối nằm trong manifest tại
`deployment.post_flash_checks`.

### Kết quả đã kiểm chứng

- Android 17 (`CP3A.260905.010`, SDK 37) boot từ eMMC với kernel
  `5.4.302-g32a306e084db-dirty`, bản số 7.
- CameraService nhận hai camera công khai: IMX400 sau (ID 0), IMX258 trước
  (ID 1), thông qua provider HIDL cũ. Cả hai cảm biến dò ID phần cứng thành công.
- Đã quan sát preview camera sau; dump khi gỡ tracing ghi nhận 211 frame preview
  và 216 frame ImageReader. Chủ máy xác nhận cả hai camera hoạt động. Chưa kiểm
  chứng riêng đèn pin, quay video và các chế độ tốc độ cao trong phiên này.
- Bluetooth được chủ máy xác nhận hoạt động; các lần kiểm tra ghi nhận ON và
  crash bằng 0. Giữ nguyên bản vá UART LPM đang chạy tốt.
- Developer options hiển thị đúng trang, hết crash do ghi thuộc tính. Chưa kiểm
  thử từng tùy chọn phát triển bên trong.
- Đã gỡ strace, wrapper provider và hai binary probe khỏi vendor.
  `init.keyaki.camera.rc` trả ba thuộc tính debug camera tạm về 0. Log riêng tư
  được giữ ngoài Git.

### Nguyên nhân và bản sửa

1. Kernel 5.4 mã hóa loại camera bằng function `0x10fxx`; HAL cũ tìm type
   `0x20000` và group số. Script mới chuyển kết quả ENUM_ENTITIES cho subdevice
   trong `msm_config`, video node trong cả `msm_config` và `msm_camera`: CSID
   group 1, buffer-manager 13, video 2. Giữ nguyên function của API topology mới.
   Probe ARM32/ARM64 trả kết quả giống nhau trước và sau khi vá.
2. Vendor donor dùng nhầm IMX300/IMX214, trong khi đọc I2C nhận `0x400`/`0x258`.
   Đã cài ba XML keyaki: `camera_config.xml`, `imx400_chromatix.xml`,
   `imx258_chromatix.xml`. Builder giữ owner root:root, mode 0644 và nhãn SELinux
   `vendor_configs_file` kết thúc byte NUL.
3. Khi bật strace toàn bộ syscall và log chi tiết, đã ghi nhận trễ yêu cầu frame
   và lỗi buffer, ứng dụng dừng ở màn hình tải. Gỡ wrapper xong đã có preview và bộ đếm frame tăng. Cấu hình
   do `prepare_camera_trace.py` tạo chỉ dùng chẩn đoán, không đưa vào bản chạy chính.
4. GSI user thiếu quyền cho controller logpersist khi port bật `ro.debuggable=1`.
   Script policy chỉ thêm quyền ghi thuộc tính và đọc file thuộc tính
   `logpersistd_logging_prop` cho `system_app`. Đã tích hợp builder và biên dịch
   secilc toàn bộ policy phiên bản 31 thành công, kích thước 1.561.208 byte.
   Hash CIL trên máy được ghi ở phần tiếng Anh phía trên.

### Image, tái tạo và nạp bản cập nhật

Bốn image trong `out/` cùng `SHA256SUMS.txt` được liệt kê phía trên. Boot chứa
kernel số 7, vendor là snapshot thật đã gỡ tracing và giữ Bluetooth/audio,
System chứa bản vá Settings. Có manifest tại
`manifests/camera-settings-release-20261113.json`. Kernel prebuilt ban đầu vẫn
được giữ làm baseline lịch sử; khi tái tạo cần chọn kernel có camera bằng
`XZS17_KERNEL_IMAGE=/work/out/kernel_a17/Image.gz-dtb` như ba lệnh ở trên.
Đây là biên dịch kernel và đóng gói image sẵn có, không build lại toàn bộ Android.
Công cụ thay riêng kernel kiểm tra ramdisk và tham số nạp không đổi.

Trên máy hiện tại, policy Settings đã nằm trong system. Lần nạp chính thức ghi
boot và OEM, giữ userdata/TWRP. Vào root TWRP rồi dùng lệnh helper ở trên với hai
backup đầy đủ. Helper kiểm tra ánh xạ/kích thước phân vùng, không nhận OEM sparse,
không ghi khi target còn mount, kiểm tra hash file đẩy lên và hash đọc lại sau ghi.
Chỉ ghi boot `mmcblk0p30` và OEM `mmcblk0p53`; không tự reboot. Chỉ chạy `adb reboot`
sau khi cả hai báo khớp. TWRP cũ không hỗ trợ `dd conv=fsync`, nên dùng `sync` riêng.
Nếu kiểm tra không đạt, giữ máy ở TWRP. Cài mới từ ROM khác dùng đủ ba image theo
README; lần cập nhật này không format dữ liệu.

Reboot recovery đôi lúc không nhận USB, cần vào bằng phím cứng. Không ghi đè
FOTAKernel, TA, bootloader hay phân vùng hiệu chuẩn. Backup boot/vendor gốc và
boot số 6 đã kiểm chứng vẫn được giữ trong `backup/checkpoints/`.

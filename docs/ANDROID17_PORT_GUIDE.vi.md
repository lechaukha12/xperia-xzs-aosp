# Hướng Dẫn Kỹ Thuật Port Android 17 AOSP Lên Sony Xperia XZs (`keyaki` / `SO-03J`)

**Ngôn ngữ / Language**: [English (Default - ANDROID17_PORT_GUIDE.md)](ANDROID17_PORT_GUIDE.md) | **Tiếng Việt**

**Cập nhật 13/11/2026:** kernel số 7, hai camera và Bluetooth hoạt động, Developer options hết crash. Xem [ghi chú phát hành](SETTINGS_CAMERA_BRINGUP.md) cho kết quả kiểm chứng và manifest image.

## 1. Tổng Quan Dự Án & Kiến Trúc Hệ Thống

Tài liệu này mô tả chi tiết toàn bộ quy trình kỹ thuật, các rào cản kiến trúc qua **7 thế hệ Android** (từ Android 8.0 / Android 11 Project Treble VNDK 30 lên **Android 17 "Cinnamon Bun" — `CP3A.260905.010`, SDK 37 / API 37.1**), và giải pháp khắc phục triệt để đã được kiểm chứng thực tế trên thiết bị **Sony Xperia XZs (`SO-03J` / `keyaki`, Qualcomm Snapdragon 820 `MSM8996`, nền tảng Sony `tone`)**.

### Thông Số Thành Phần Bản Port
| Thành phần | Phiên bản / Nguồn | Phân vùng đích | Ghi chú kỹ thuật |
| :--- | :--- | :--- | :--- |
| **System (OS)** | Google Android 17 AOSP ARM64 GSI (`CP3A.260905.010`, SDK `37`) | `system` (`mmcblk0p55`, `7.18 GiB`) | Mở rộng ext4 `2.6 GiB`, unshare blocks, tích hợp VNDK v30 + ext4 `virt` APEX + SELinux `30.0.cil` |
| **Vendor (HAL)** | LineageOS 18.1 Treble Vendor (`tone` / `keyaki`, VNDK `30`) | `oem` (`mmcblk0p53`, `400 MiB`) | Mount trực tiếp vào `/vendor` từ giai đoạn First-Stage Init |
| **Kernel** | Linux `5.4.302-g32a306e084db-dirty (#7)` (`nec093/sov35-kernel`) | `boot` (`mmcblk0p30`, `64 MiB`) | Hỗ trợ eBPF, cgroup v2, 17 module âm thanh DLKM `msm8996-tasha`, Wi-Fi PCIe `brcmfmac` |
| **First-Stage Init** | Custom static C (`tools/keyaki_first_stage_init.c`) | `boot` ramdisk (`/init`) | Khởi tạo node eMMC + RPMB, mount `/system` & `/vendor`, `SwitchRoot`, giữ shadow SELinux |
| **Recovery dự phòng** | TWRP `3.7.0_9-0` (Linux `3.18.71`) (`FOTAKernel`) | `FOTAKernel` (`mmcblk0p48`, `64 MiB`) | Giữ nguyên bản gốc không chạm tới (`adb reboot recovery` hoặc `Nguồn + Giảm âm lượng`) |

> [!CAUTION]
> Tuyệt đối không bao giờ ghi đè các phân vùng nhạy cảm của Sony gồm `TA` (`mmcblk0p1` — DRM keys và hiệu chuẩn), `aboot` (`mmcblk0p13` — `S1_Boot`), `FOTAKernel` (`mmcblk0p48`), `modemst1`, `modemst2`, `persist`, và `fsg`.

---

## 2. Chi Tiết Các Rào Cản Kỹ Thuật Cốt Lõi & Giải Pháp Triệt Để

### 2.1. Tương thích Bootloader Sony `S1_Boot` (Màn hình đen + Đèn LED xanh lá)
- **Nguyên nhân**: Bootloader `S1_Boot` của dòng Xperia XZs (`MSM8996`) kiểm tra nghiêm ngặt cấu trúc `Image.gz-dtb` appended DTB của Sony `keyaki` và trường `os_version` trong Android Boot Image Header v0. Nếu đặt `--os_version 17.0.0`, `S1_Boot` từ chối giải nén và treo sớm với đèn LED xanh lá.
- **Giải pháp**: Đóng gói `prebuilt/Image.gz-dtb` (`5.4.302-xzs54`) với thông số tải chuẩn `base=0x80000000`, `kernel_offset=0x8000`, `ramdisk_offset=0x2000000`, `tags_offset=0x1e00000`, `pagesize=4096` và header `--os_version 10.0.0 --os_patch_level 2020-03`.

### 2.2. Thiết kế First-Stage Init, `/metadata` và SELinux Shadow trên GSI `user`
- **Nguyên nhân**:
  1. Sony XZs xuất xưởng với bố cục non-A/B cũ, không có phân vùng `metadata` vật lý, không dùng `super` dynamic partitions và đặt `/vendor` trên phân vùng `oem` (`mmcblk0p53`).
  2. Bản GSI chính thức của Google (`CP3A.260905.010`) được biên dịch ở chế độ `user` (`ALLOW_PERMISSIVE_SELINUX=0`), khiến `init` luôn tự ghi `'1'` vào `/sys/fs/selinux/enforce` bất kể tham số `androidboot.selinux=permissive` trên kernel cmdline.
- **Giải pháp (`tools/keyaki_first_stage_init.c`)**:
  - Viết trình khởi tạo tĩnh nhẹ gọn chạy ở PID 1: tự động quét `/sys/block/mmcblk0` và `/sys/bus/mmc/devices/mmc0:0001/mmcblk0rpmb` để tạo đầy đủ block/char node trong `/dev/block/.../by-name` và `/dev/mmcblk0rpmb`.
  - Tạo `tmpfs` cho `/metadata` và `/second_stage_resources` (`ro.boot.dynamic_partitions=false`).
  - Mount `/dev/block/mmcblk0p55` vào `/system_root` và `/dev/block/mmcblk0p53` vào `/system_root/vendor`, di chuyển (`MS_MOVE`) các mount ảo rồi `SwitchRoot` (`chroot`) sang `/system/bin/init selinux_setup`.
  - Bind-mount file bóng `/dev/.selinux_enforce_shadow` lên `/sys/fs/selinux/enforce` trong giai đoạn khởi động để kernel giữ chế độ permissive cho các daemon HAL cũ của MSM8996 trong khi userspace `init` hoàn tất `selinux_setup`.

### 2.3. SELinux Mapping `30.0.cil`, VINTF Matrix 5 & VNDK v30 cho Android 17
- **Nguyên nhân**: Android 17 đã gỡ bỏ hoàn toàn tập tin ánh xạ SELinux `30.0.cil`, `compatibility_matrix.5.xml`, và `com.android.vndk.v30.apex` (vốn bắt buộc cho Vendor Android 11 / VNDK 30).
- **Giải pháp (`tools/build_vndk30_apex.py` & `tools/build_system_and_boot_a17.py`)**:
  - Đóng gói lại toàn bộ thư viện VNDK v30 thành `com.android.vndk.v30.signed.apex` (căn lề `apex_payload.img` 4096-byte + AVB hashtree `SHA256_RSA4096` + chữ ký APK v2/v3).
  - Sinh tự động bảng ánh xạ `/system/etc/selinux/mapping/30.0.cil` & `30.0.compat.cil` (xử lý các thuộc tính tách đôi từ Android 11 như `ffs_prop`, `exported_*_prop`, `cgroup_bpf`) và kiểm tra biên dịch offline ngay bằng `/system/bin/secilc` của chính Android 17 ở policy version `31`.
  - Bổ sung `compatibility_matrix.5.xml` (cho phép `android.hardware.graphics.mapper@2.0-1` và loại bỏ khóa phiên bản kernel 4.x cũ).

### 2.4. Chuyển đổi `com.android.virt.apex` (`EROFS` -> `ext4`) & Chữ ký APK v2/v3 cho `PackageManagerService`
- **Nguyên nhân**:
  1. Trên Android 17, `com.android.virt.apex` sử dụng định dạng payload `EROFS`, nhưng kernel `5.4.302` không bật `CONFIG_EROFS_FS` khiến `apexd` thất bại khi mount APEX.
  2. Khi đóng gói lại `com.android.virt.apex` và `com.android.vndk.v30.apex`, `apexd` chỉ kiểm tra AVB footer của `apex_payload.img`, nhưng đến giai đoạn `SystemServer`, `PackageManagerService` (`scanApexPackagesTraced`) yêu cầu lớp vỏ ZIP ngoài của mọi `.apex` phải có **APK Signature Scheme v2/v3** (`minSdkVersion 24`). Nếu thiếu chữ ký ngoài, `SystemServer` ném `PackageManagerException: No APK Signature Scheme v2 signature`.
- **Giải pháp (`tools/repack_virt_apex_ext4.py`)**:
  - Trích xuất payload EROFS (giữ nguyên toàn bộ nhãn SELinux chi tiết như `crosvm_exec`, `early_virtmgr_exec`) sang image `ext4` (`-b 4096 -O ^has_journal`), ký AVB hashtree, đóng gói ZIP không nén căn lề `4096` byte, và ký lớp vỏ ngoài bằng `apksigner` (`--v1-signing-enabled false --v2-signing-enabled true --v3-signing-enabled true --min-sdk-version 24`). Kết quả: 45/45 gói APEX được `PackageManagerService` xác thực thành công trong `0.95 giây`.

### 2.5. Tương thích `cgroups.json` trên Kernel Linux 5.4
- **Nguyên nhân**: Android 17 đánh dấu controller `blkio` (cgroup v1) và `freezer` (cgroup v2) là bắt buộc. Khi thiết lập thất bại trên Linux 5.4, `libprocessgroup` dừng sớm trước khi kích hoạt `memory` controller.
- **Giải pháp (`configs/cgroups/cgroups.json`)**: Thêm `"Optional": true` cho `blkio` và `freezer` trong `/system/etc/cgroups.json`.

### 2.6. Mainline eBPF (`NetBpfLoad` + `.android_progs` KVER) trên Kernel Linux 5.4.302
- **Nguyên nhân**: Module `com.android.tethering` của Android 17 chặn ngưỡng kernel trong `NetBpfLoad`, đồng thời `netd.o` và `offload.o` chứa cả nhánh chương trình BPF không BTF cho `4.19..5.4.0` (`min_kver=0x04130000`, `max_kver=0x05040000`) lẫn nhánh `5.4.0+` dùng ringbuf/CO-RE (`min_kver=0x05040000`). Trên Linux `5.4.302` (`0x0504012e > 0x05040000`), `NetBpfLoad` bỏ qua nhánh `4.19` và cố nạp nhánh `5.4.0+` khiến việc nạp BPF thất bại.
- **Giải pháp (`tools/patch_bpf_54.py` & `configs/init/netbpfload.rc`)**:
  - Hạ kiểm tra kernel version trong `netbpfload_54` (`0x98c4`, `0xa598`).
  - Cập nhật `.android_progs` trong `netd.o` và `offload.o`: vô hiệu hóa các mục `5.4.0+` không tương thích (`0xffffffff`) và nâng `max_kver` của các mục `4.19` không BTF lên `5.10.0` (`0x050a0000`), sau đó bind-mount trong `on load-bpf-programs`. Kết quả: `bpf.progs_loaded=1`, `netd` khởi động hoàn chỉnh.

### 2.7. Tương thích `BPF_MAP_TYPE_RINGBUF` trong `ConnectivityService` (`libservice-connectivity.so`)
- **Nguyên nhân**: Kernel Linux `5.4` chưa có `BPF_MAP_TYPE_RINGBUF` (ra mắt từ Linux `5.8`). Thư viện `/apex/com.android.tethering/lib64/libservice-connectivity.so` gọi `abort()` tại hai vị trí khi không tìm thấy ringbuf map:
  1. `LocalNetEventHandler::GetRingbuf()` (`map_netd_local_net_note_op_ringbuf`) ngay trong `ConnectivityService.<init>`, đồng thời `LocalNetEventListener.start()` truyền `FileDescriptor` này vào `MessageQueue.addOnFileDescriptorEventListener()` (sẽ ném `IllegalArgumentException` nếu trả về `null`).
  2. `LoopbackEventHandler::GetPoller()` (`map_netd_loopback_access_ringbuf`) khi `ConnectivityService.systemReady()` chạy.
- **Giải pháp (`tools/patch_tethering_54.py`)**:
  - Vá `nativeGetLocalNetAccessRingbufFd` (`0xdf18..0xdf28`) để cấp phát một `eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK)` rỗi hợp lệ qua `eventfd@plt` (`0x15130`), giúp `MessageQueue` đăng ký `epoll` sạch sẽ mà không tốn CPU.
  - Vá `nativeConsumeAllLocalNetAccessEvents` (`0xe2b0`) trả về mảng rỗng `int[0]`.
  - Vá lambda khởi tạo `LoopbackEventHandler::GetPoller()` (`0x11f10..0x11f18`) trả về `nullptr` (`mov x0, xzr; autiasp; ret`), tận dụng nhánh xử lý `nullptr` an toàn sẵn có của `LoopbackEventHandler`.

### 2.8. Khôi phục Đồ họa Gralloc 2.0/3.0 trên SDK 37 (`libui.so`) & Adreno 530 EGL
- **Nguyên nhân**:
  1. Thiếu `ro.hardware.egl=adreno` khiến `libEGL` không tìm thấy `/vendor/lib64/egl/libGLESv2_adreno.so`.
  2. Trên Android 17 (`SDK 37`), `GraphicBufferMapper` và `preloadHal()` trong `libui.so` gọi `android_get_device_api_level()` (`37`), so sánh `cmp w0, #0x23` (`SDK 35`) và nhảy qua toàn bộ nhánh nạp `Gralloc3Mapper` / `Gralloc2Mapper` (`b.gt`), khiến `SurfaceFlinger` sập với lỗi `gralloc-mapper is missing`.
  3. `/vendor/etc/vintf/manifest.xml` khai báo dư `@3.0` và `@4.0::IMapper/default` không thực thi.
- **Giải pháp (`tools/patch_libui_gralloc2.py` & `tools/build_vendor_oem.sh`)**:
  - Khai báo `ro.hardware.egl=adreno` và loại bỏ `@3.0`/`@4.0` `IMapper` khỏi `/vendor/etc/vintf/manifest.xml`.
  - Thay lệnh nhảy `b.gt` sau `cmp w0, #0x23` (64-bit tại `0x34d98`, `0x5a1f4`; 32-bit tại `0x2184a`, `0x3e670`, cùng bản sao trong `com.android.media.swcodec` APEX) bằng lệnh `nop`. Kết quả: **Adreno 530 OpenGL ES 3.2**, **Gralloc 2.0**, và **HWComposer 2.1 (`DEVICE` composition)** kết xuất mượt ở **1080x1920 @ 60 Hz**.

### 2.9. Khắc phục Quyền USB FunctionFS của `adbd` trên GSI `user`
- **Nguyên nhân**: Khi đặt `service.adb.root=1` trên bản GSI `user`, `adbd` chuyển sang ngữ cảnh `u:r:su:s0`. Do `property_service` của `init` trên bản `user` luôn kiểm tra quyền SELinux đối với property và domain `su` không có rule ghi property, `adbd` bị từ chối ghi `sys.usb.ffs.ready=1` khiến cổng USB ADB không bật lên.
- **Giải pháp**: Đặt `service.adb.root=0` trong `configs/props/system_keyaki.prop` để `adbd` chạy đúng domain chuẩn `u:r:adbd:s0`, kết nối USB ADB ổn định sau ~22 giây từ lúc bật nguồn.

### 2.10. Âm thanh (`wcd9335` + `wsa881x`), Wi-Fi (`brcmfmac` BCM4359) & Bảo vệ Modem Nougat
- **Âm thanh**: Biên dịch và cài đặt 17 module kernel DLKM âm thanh của Linux `5.4.302` vào `/vendor/lib/modules` cùng cấu hình loa kép `mixer_paths_tasha.xml` của `keyaki`.
- **Wi-Fi**: Cung cấp firmware `/vendor/firmware/brcm/brcmfmac4359-pcie.bin` + NVRAM theo board `somc,keyaki` và chuyển hướng ghi `firmware_path` kiểu cũ của `bcmdhd` trong `/vendor/lib64/libwifi-hal.so` sang `/dev/null`.
- **Modem Guard**: Trên nền firmware baseband Nougat cũ (`LA2.0_N_117`), bind-mount `/dev/null` lên `modem.mdt` trong `configs/init/init.keyaki.rc` để ngăn lỗi IPA/SSR cho đến khi nâng cấp baseband lên Oreo.

---

### 2.11. Developer options trên GSI user bật debug

Settings crash khi ghi `logd.logpersistd=clear`: port bật `ro.debuggable=1`,
hiển thị controller nhưng policy user thiếu quyền. Script policy chỉ cấp quyền
cần thiết cho `system_app` với `logpersistd_logging_prop`, giữ metadata file.
Secilc offline biên dịch thành công và đã xác nhận đúng trang Developer options.

### 2.12. ABI Media camera và cấu hình cảm biến keyaki

HAL cũ tìm type `0x20000` cùng group số; kernel 5.4 dùng function `0x10fxx`.
Bản vá chuyển kết quả ENUM_ENTITIES cho subdevice `msm_config` và video node
`msm_camera` (group 2), đảo lại group CSID/buffer-manager. Probe 32/64-bit khớp
nhau. XML phải dùng IMX400/IMX258 của keyaki, khớp ID chip thật, thay cấu hình
IMX300/IMX214 của donor. Sau đó hai cảm biến dò thành công, CameraService có ID
0 và 1. Đã gỡ strace trước khi kiểm chứng preview; chủ máy xác nhận cả hai camera
hoạt động.

### 2.13. Giữ Bluetooth và đóng gói bản cập nhật

Giữ nguyên bản vá UART LPM BCM4359 trong builder vendor. Chủ máy xác nhận
Bluetooth hoạt động; đã quan sát ON và crash bằng 0. Vendor chạy chính trả mức
debug camera về 0, không chứa binary probe. Khi tái tạo boot phải chọn rõ kernel
đã có bản vá camera. Xem [ghi chú phát hành](SETTINGS_CAMERA_BRINGUP.md) để biết
checksum, phạm vi kiểm chứng, lệnh tái tạo và helper ghi boot/OEM có đọc lại.

## 3. Kết Quả Kiểm Chứng Thực Tế Trên Thiết Bị (`SO-03J`)

- **Hệ điều hành**: Android `17` (`CP3A.260905.010`, SDK `37`, Security Patch `2026-09-05`), cold boot đạt `sys.boot_completed=1` trong **~38 giây**, **0 crash** trong `logcat -b crash`.
- **Hiển thị & GPU**: `SurfaceFlinger` + `HWComposer 2.1` (`DEVICE` composition) + **Qualcomm Adreno 530** (`OpenGL ES 3.2 V@415.0`), độ phân giải `1080x1920 @ 60 Hz`, cảm ứng `clearpad` mượt.
- **Wi-Fi & Âm thanh**: `brcmfmac` (`wlan0`) bật và quét mạng Wi-Fi 2.4/5 GHz thành công; sound card `msm8996-tasha-mtp-snd-card` (`48000 Hz` stereo) hoạt động ổn định trong `AudioFlinger`.
- **Bộ nhớ & Cảm biến**: Phân vùng `/data` (`~20.8 GiB` ext4 đọc/ghi kèm `fsverity`), `1 GiB` `zram0` swap, và toàn bộ cảm biến phần cứng (`BMI160`, `AK09915`, `APDS-9940`, `HSPPAD042A`) hoạt động đầy đủ trong `SensorService`.

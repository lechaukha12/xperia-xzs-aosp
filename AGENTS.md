# Project Guidelines and Hardware Safety Rules (EN / VI)

[English](#english) | [Tiếng Việt](#tieng-viet)

---

## English

### 1. Project Status and Scope
- **Current Milestone (Frozen Baseline)**: Pure **Android 17 AOSP (`CP3A.260905.010`, SDK 37)** boots standalone from internal eMMC on **Sony Xperia XZs (`SO-03J` / `keyaki`, Qualcomm Snapdragon 820 `MSM8996`)** to Launcher3 with GPU hardware acceleration, touchscreen, Wi-Fi, stereo audio, sensors, internal storage, and ADB working.
- **Next Phase**: Incremental subsystem bring-up (Bluetooth stability, Camera HAL, Oreo baseband + RIL/cellular, Codec2 hardware video, and SELinux enforcing rules) without breaking the verified boot baseline.

### 2. Device and Partition Safety Rules (Mandatory)
1. **Never overwrite irreproducible or critical device partitions**:
   - `TA` (`mmcblk0p1` — Sony Trim Area / DRM / per-unit calibration)
   - `aboot` / `abootbak`, `s1sbl*`, `xbl*`, `tz*`, `hyp*`, `rpm*`, `pmic*`, `devcfg*`, `keymaster*`, `cmnlib*`
   - `modemst1`, `modemst2`, `fsg`, `persist`, `frp`, `LTALabel`
   - `FOTAKernel` (`mmcblk0p48` — standalone TWRP recovery safety net; do not overwrite during OS experiments)
2. **Variant discipline**:
   - `SO-03J` (NTT Docomo Japan) is not identical to international `G8231`/`G8232` in NFC/FeliCa, baseband firmware, and carrier partitions. Never blind-flash full international firmware or Snapdragon 835 (`yoshino`) boot/bootloader images.
   - Xperia XZs uses **legacy non-A/B, non-dynamic** partitions (`boot` on `mmcblk0p30`, `oem` mounted as `/vendor` on `mmcblk0p53`, `system` on `mmcblk0p55`, `userdata` on `mmcblk0p54`). There are no `super`, `vbmeta`, `vendor_boot`, or `init_boot` partitions.
3. **Root-cause engineering**:
   - Every change must correspond to a verified root cause with reproducible build scripts under `tools/` and `configs/`.
   - Never fake Android version properties (`ro.build.version.*`), delete APEX modules wholesale, or leave undocumented manual live-device edits uncaptured by the build scripts in `tools/`.
   - Preserve NUL-terminated `security.selinux` extended attributes (`xattr`) on every modified file in `/system` and `/vendor`, and pass offline `secilc` compilation before flashing.

### 3. Privacy, Security, and Repository Hygiene
- **Zero PII / Device Secrets**: Never commit or publish device serial numbers, IMEIs, Wi-Fi/Bluetooth MAC addresses, `TA.img`, `modemst*`, `fsg`, private signing keys (`*.pk8`, private `*.pem`), or unredacted device logs.
- **Zero Large Binary Blobs in Git**: Keep `.img`, `.sparse.img`, `.zip`, `.apex`, and `.ko` outputs out of Git via `.gitignore`. Track only clean source code, deterministic patchers, static configurations, manifests, and documentation.
- **Formatting Policy**: Default repository language is **English** with full **Vietnamese** documentation counterparts. **Do not use emojis** anywhere in code, documentation, commit messages, or repository metadata.

---

<a id="tieng-viet"></a>
## Tiếng Việt

### 1. Trạng Thái Dự Án và Phạm Vi
- **Cột mốc hiện tại (Baseline đã đóng băng)**: **Android 17 AOSP thuần (`CP3A.260905.010`, SDK 37)** đã cold boot độc lập từ eMMC trên **Sony Xperia XZs (`SO-03J` / `keyaki`, Qualcomm Snapdragon 820 `MSM8996`)** vào màn hình chính Launcher3 với GPU tăng tốc phần cứng, cảm ứng, Wi-Fi, loa kép stereo, cảm biến, bộ nhớ trong và ADB hoạt động ổn định.
- **Giai đoạn tiếp theo**: Hoàn thiện từng phân hệ phần cứng còn thiếu (Bluetooth, Camera HAL, baseband Oreo + RIL/mạng di động, giải mã video phần cứng Codec2, và SELinux enforcing) mà không làm hỏng nền tảng boot đã đóng băng.

### 2. Quy Tắc An Toàn Phân Vùng và Phần Cứng (Bắt Buộc)
1. **Tuyệt đối không ghi đè các phân vùng nhạy cảm hoặc không thể tái tạo**:
   - `TA` (`mmcblk0p1` — Sony Trim Area / khóa DRM / dữ liệu hiệu chuẩn riêng của máy)
   - `aboot` / `abootbak`, `s1sbl*`, `xbl*`, `tz*`, `hyp*`, `rpm*`, `pmic*`, `devcfg*`, `keymaster*`, `cmnlib*`
   - `modemst1`, `modemst2`, `fsg`, `persist`, `frp`, `LTALabel`
   - `FOTAKernel` (`mmcblk0p48` — TWRP Recovery độc lập dùng để cứu máy; không ghi đè khi thử nghiệm OS)
2. **Kỷ luật biến thể phần cứng**:
   - `SO-03J` (bản Nhật NTT Docomo) khác với `G8231`/`G8232` quốc tế ở NFC/FeliCa, firmware baseband và phân vùng nhà mạng. Không flash mù firmware quốc tế hoặc boot/bootloader của dòng Snapdragon 835 (`yoshino`).
   - Xperia XZs sử dụng bố cục phân vùng **legacy non-A/B, không dynamic** (`boot` tại `mmcblk0p30`, `oem` mount làm `/vendor` tại `mmcblk0p53`, `system` tại `mmcblk0p55`, `userdata` tại `mmcblk0p54`). Máy không có phân vùng `super`, `vbmeta`, `vendor_boot` hay `init_boot`.
3. **Kỹ thuật xử lý tận gốc**:
   - Mọi thay đổi phải xuất phát từ nguyên nhân gốc đã kiểm chứng và được đóng gói thành script tái tạo được trong `tools/` và `configs/`.
   - Không giả mạo thuộc tính phiên bản (`ro.build.version.*`), không xóa bừa các gói APEX, và không để các chỉnh sửa thủ công trên máy mà chưa cập nhật vào script build.
   - Luôn bảo toàn nhãn `security.selinux` (`xattr` kết thúc bằng byte NUL) cho mọi tập tin sửa đổi trên `/system` và `/vendor`, đồng thời kiểm tra biên dịch offline bằng `secilc` trước khi flash.

### 3. Bảo Mật Thông Tin và Quy Chuẩn Kho Mã Nguồn
- **Không lộ dữ liệu định danh thiết bị**: Tuyệt đối không commit số serial, IMEI, địa chỉ MAC Wi-Fi/Bluetooth, `TA.img`, `modemst*`, `fsg`, khóa ký riêng (`*.pk8`, `*.pem`), hoặc log chưa che thông tin nhạy cảm.
- **Không đưa file nhị phân dung lượng lớn lên Git**: Loại trừ `.img`, `.sparse.img`, `.zip`, `.apex`, `.ko` qua `.gitignore`. Chỉ quản lý mã nguồn, script và cấu hình tái tạo bản build, manifest, và tài liệu kỹ thuật.
- **Quy ước trình bày**: Ngôn ngữ mặc định trong repo là **Tiếng Anh** kèm bản dịch **Tiếng Việt** đầy đủ. **Tuyệt đối không sử dụng emoji** trong mã nguồn, tài liệu, commit message hay mô tả repository.

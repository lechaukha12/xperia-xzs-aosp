# Partition Layout — Sony Xperia XZs (`SO-03J` / `keyaki`)

[English](#english) | [Tiếng Việt](#tieng-viet)

---

## English

### 1. Storage Architecture Overview
- **SoC / Storage Controller**: Qualcomm Snapdragon 820 (`MSM8996`), internal eMMC at `/dev/block/mmcblk0` (`7464900.sdhci`), total user-addressable capacity ~32 GB, plus hardware RPMB partition `/dev/mmcblk0rpmb`.
- **Partition Scheme**: Legacy **non-A/B**, **non-dynamic** GPT layout (no `super`, `vbmeta`, `vendor_boot`, or `init_boot`).
- **Project Treble Mapping**: Like official LineageOS 18.1 for Sony `tone` devices, the 400 MiB `oem` partition (`mmcblk0p53`) serves as `/vendor`, mounted read-only during first-stage init alongside `/system` (`mmcblk0p55`).

### 2. Primary OS, Vendor, Recovery, and Data Partitions

| Partition Name | Block Device | Size (Bytes) | Size | Role in Android 17 Port | Flash Policy |
| :--- | :--- | ---: | ---: | :--- | :--- |
| `TA` | `/dev/block/mmcblk0p1` | 2,097,152 | 2 MiB | Sony Trim Area (DRM keys, hardware calibration, `tad_static`) | **NEVER WRITE / BACKUP ONLY** |
| `aboot` | `/dev/block/mmcblk0p13` | 1,048,576 | 1 MiB | Sony `S1_Boot` bootloader (`fastboot` + boot image loader) | **NEVER WRITE** |
| `boot` | `/dev/block/mmcblk0p30` | 67,108,864 | 64 MiB | `boot-a17-keyaki.img` (`Linux 5.4.302-xzs54` + `keyaki_first_stage_init`) | Safe to flash (`fastboot flash boot`) |
| `modem` | `/dev/block/mmcblk0p31` | 99,614,720 | 95 MiB | VFAT firmware image mounted at `/vendor/firmware_mnt` | Read-only (do not modify in Phase 1) |
| `dsp` | `/dev/block/mmcblk0p32` | 16,777,216 | 16 MiB | Qualcomm ADSP/CDSP firmware mounted at `/vendor/dsp` | Read-only |
| `modemst1` | `/dev/block/mmcblk0p41` | 2,097,152 | 2 MiB | EFS / NV calibration storage 1 | **NEVER WRITE / BACKUP ONLY** |
| `modemst2` | `/dev/block/mmcblk0p42` | 2,097,152 | 2 MiB | EFS / NV calibration storage 2 | **NEVER WRITE / BACKUP ONLY** |
| `cache` | `/dev/block/mmcblk0p43` | 268,435,456 | 256 MiB | `/cache` (`ext4`) | Safe to format (`ext4`) |
| `persist` | `/dev/block/mmcblk0p44` | 33,554,432 | 32 MiB | `/mnt/vendor/persist` (`ext4` sensor/Wi-Fi/DRM persistent data) | **DO NOT FORMAT** |
| `FOTAKernel` | `/dev/block/mmcblk0p48` | 67,108,864 | 64 MiB | Standalone TWRP `3.18.71` recovery image | Preserve untouched as recovery lifeline |
| `apps_log` | `/dev/block/mmcblk0p50` | 10,485,760 | 10 MiB | Mapped as `/misc` in `fstab.keyaki` | Raw misc / BCB partition |
| `oem` | `/dev/block/mmcblk0p53` | 419,430,400 | 400 MiB | Mounted at `/vendor` (`oem-a17-keyaki.img`, `ext4` ro) | Safe to flash (`fastboot flash oem`) |
| `userdata` | `/dev/block/mmcblk0p54` | 22,347,251,712 | ~20.81 GiB | Mounted at `/data` (`ext4` rw, `quota`, `fsverity`) | Format `ext4` on clean install |
| `system` | `/dev/block/mmcblk0p55` | 7,707,033,600 | ~7.18 GiB | System-as-root `/` (`system-a17-keyaki.sparse.img`, `ext4` ro) | Safe to flash (`fastboot flash system`) |

### 3. Complete GPT Partition Map (`mmcblk0`)

```text
mmcblk0p1   TA               2,097,152 B  (2 MiB)
mmcblk0p2   LTALabel        16,777,216 B  (16 MiB)
mmcblk0p3   xbl              2,097,152 B  (2 MiB)
mmcblk0p4   xblbak           2,097,152 B  (2 MiB)
mmcblk0p5   tz               2,097,152 B  (2 MiB)
mmcblk0p6   tzbak            2,097,152 B  (2 MiB)
mmcblk0p7   rpm                512,000 B  (500 KiB)
mmcblk0p8   rpmbak             512,000 B  (500 KiB)
mmcblk0p9   hyp                524,288 B  (512 KiB)
mmcblk0p10  hypbak             524,288 B  (512 KiB)
mmcblk0p11  pmic               524,288 B  (512 KiB)
mmcblk0p12  pmicbak            524,288 B  (512 KiB)
mmcblk0p13  aboot            1,048,576 B  (1 MiB)
mmcblk0p14  abootbak         1,048,576 B  (1 MiB)
mmcblk0p15  keymaster          524,288 B  (512 KiB)
mmcblk0p16  keymasterbak       524,288 B  (512 KiB)
mmcblk0p17  cmnlib             262,144 B  (256 KiB)
mmcblk0p18  cmnlibbak          262,144 B  (256 KiB)
mmcblk0p19  cmnlib64           262,144 B  (256 KiB)
mmcblk0p20  cmnlib64bak        262,144 B  (256 KiB)
mmcblk0p21  devcfg             131,072 B  (128 KiB)
mmcblk0p22  devcfgbak          131,072 B  (128 KiB)
mmcblk0p23  s1sbl           31,457,280 B  (30 MiB)
mmcblk0p24  s1sblbak        31,457,280 B  (30 MiB)
mmcblk0p25  tzs1attest         102,400 B  (100 KiB)
mmcblk0p26  tzs1attestbak      102,400 B  (100 KiB)
mmcblk0p27  tzs1sbl            524,288 B  (512 KiB)
mmcblk0p28  tzs1sblbak         524,288 B  (512 KiB)
mmcblk0p29  fsg              2,097,152 B  (2 MiB)
mmcblk0p30  boot            67,108,864 B  (64 MiB)
mmcblk0p31  modem           99,614,720 B  (95 MiB)
mmcblk0p32  dsp             16,777,216 B  (16 MiB)
mmcblk0p33  devinfo              1,024 B  (1 KiB)
mmcblk0p34  apdp               262,144 B  (256 KiB)
mmcblk0p35  msadp              262,144 B  (256 KiB)
mmcblk0p36  dpo                  1,024 B  (1 KiB)
mmcblk0p37  splash          34,226,176 B  (32.64 MiB)
mmcblk0p38  ddr              1,048,576 B  (1 MiB)
mmcblk0p39  sec                131,072 B  (128 KiB)
mmcblk0p40  ssd                  8,192 B  (8 KiB)
mmcblk0p41  modemst1         2,097,152 B  (2 MiB)
mmcblk0p42  modemst2         2,097,152 B  (2 MiB)
mmcblk0p43  cache          268,435,456 B  (256 MiB)
mmcblk0p44  persist         33,554,432 B  (32 MiB)
mmcblk0p45  keystore           524,288 B  (512 KiB)
mmcblk0p46  frp                524,288 B  (512 KiB)
mmcblk0p47  sti              2,097,152 B  (2 MiB)
mmcblk0p48  FOTAKernel      67,108,864 B  (64 MiB)
mmcblk0p49  rdimage         33,554,432 B  (32 MiB)
mmcblk0p50  apps_log        10,485,760 B  (10 MiB)
mmcblk0p51  diag            16,777,216 B  (16 MiB)
mmcblk0p52  Qnovo           20,971,520 B  (20 MiB)
mmcblk0p53  oem            419,430,400 B  (400 MiB)
mmcblk0p54  userdata    22,347,251,712 B  (20.81 GiB)
mmcblk0p55  system       7,707,033,600 B  (7.18 GiB)
```

---

<a id="tieng-viet"></a>
## Tiếng Việt

### 1. Tổng Quan Kiến Trúc Lưu Trữ
- **SoC / Bộ điều khiển lưu trữ**: Qualcomm Snapdragon 820 (`MSM8996`), bộ nhớ trong eMMC tại `/dev/block/mmcblk0` (`7464900.sdhci`), dung lượng ~32 GB kèm phân vùng phần cứng RPMB `/dev/mmcblk0rpmb`.
- **Sơ đồ phân vùng**: Bố cục GPT **non-A/B**, **non-dynamic** kiểu cũ (không có `super`, `vbmeta`, `vendor_boot` hay `init_boot`).
- **Ánh xạ Project Treble**: Tương tự LineageOS 18.1 cho dòng Sony `tone`, phân vùng `oem` dung lượng 400 MiB (`mmcblk0p53`) đóng vai trò là `/vendor`, được mount chỉ đọc (read-only) ngay trong giai đoạn first-stage init cùng với `/system` (`mmcblk0p55`).

### 2. Các Phân Vùng Chính Và Quy Tắc Ghi

| Tên phân vùng | Thiết bị khối | Dung lượng | Vai trò trong bản Port Android 17 | Quy tắc thao tác |
| :--- | :--- | ---: | :--- | :--- |
| `TA` | `/dev/block/mmcblk0p1` | 2 MiB | Sony Trim Area (khóa DRM, dữ liệu hiệu chuẩn, `tad_static`) | **TUYỆT ĐỐI KHÔNG GHI / CHỈ SAO LƯU** |
| `aboot` | `/dev/block/mmcblk0p13` | 1 MiB | Bootloader `S1_Boot` của Sony | **TUYỆT ĐỐI KHÔNG GHI** |
| `boot` | `/dev/block/mmcblk0p30` | 64 MiB | `boot-a17-keyaki.img` (`Linux 5.4.302-xzs54` + `keyaki_first_stage_init`) | Được phép flash (`fastboot flash boot`) |
| `modem` | `/dev/block/mmcblk0p31` | 95 MiB | Ảnh firmware VFAT mount tại `/vendor/firmware_mnt` | Chỉ đọc (giữ nguyên trong Giai đoạn 1) |
| `dsp` | `/dev/block/mmcblk0p32` | 16 MiB | Firmware ADSP/CDSP mount tại `/vendor/dsp` | Chỉ đọc |
| `modemst1` / `2` | `mmcblk0p41` / `p42` | 2 MiB x2 | Dữ liệu hiệu chuẩn sóng / EFS NV | **TUYỆT ĐỐI KHÔNG GHI / CHỈ SAO LƯU** |
| `cache` | `/dev/block/mmcblk0p43` | 256 MiB | Phân vùng `/cache` (`ext4`) | Có thể format `ext4` |
| `persist` | `/dev/block/mmcblk0p44` | 32 MiB | `/mnt/vendor/persist` (dữ liệu cảm biến, Wi-Fi, DRM) | **KHÔNG FORMAT** |
| `FOTAKernel` | `/dev/block/mmcblk0p48` | 64 MiB | Ảnh TWRP `3.18.71` Recovery độc lập | Giữ nguyên làm đường cứu hộ an toàn |
| `oem` | `/dev/block/mmcblk0p53` | 400 MiB | Mount làm `/vendor` (`oem-a17-keyaki.img`, `ext4` ro) | Được phép flash (`fastboot flash oem`) |
| `userdata` | `/dev/block/mmcblk0p54` | ~20.81 GiB | Mount làm `/data` (`ext4` rw, `quota`, `fsverity`) | Format `ext4` khi cài mới |
| `system` | `/dev/block/mmcblk0p55` | ~7.18 GiB | System-as-root `/` (`system-a17-keyaki.sparse.img`, `ext4` ro) | Được phép flash (`fastboot flash system`) |

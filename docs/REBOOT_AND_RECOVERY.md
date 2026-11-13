# Bootloader, Reboot Modes, and Recovery Guide (`S1_Boot` / `keyaki`)

[English](#english) | [Tiếng Việt](#tieng-viet)

---

## English

### 1. Sony `S1_Boot` Boot Image Requirements
Sony's `S1_Boot` (`1299-4832_S1_Boot_MSM8996`) on Xperia XZs enforces strict checks on Android Boot Image v0 headers and appended DTBs:
- **Load Offsets**: `base=0x80000000`, `kernel_offset=0x00008000`, `ramdisk_offset=0x02000000`, `tags_offset=0x01e00000`, `pagesize=4096`, `header_version=0`.
- **OS Version Header Quirk**: `S1_Boot` rejects or hangs early (solid green notification LED + black screen) if `--os_version` is set to modern values like `17.0.0`. Always build `boot.img` with `--os_version 10.0.0 --os_patch_level 2020-03`.
- **Appended DTB**: Kernel must be an `Image.gz-dtb` containing the Sony `keyaki` (`msm8996-tone-keyaki`) device tree descriptor expected by `S1_Boot`.

### 2. Reboot Reason Codes (`warmboot`) on MSM8996 `S1_Boot`
Inspection of `aboot` (`mmcblk0p13`) and live hardware behavior confirms the following PMIC PON / warmboot behavior:
- **`adb reboot recovery`**: Sets recovery reason (`0x77665502`), causing `S1_Boot` to boot standalone TWRP from `FOTAKernel` (`mmcblk0p48`). Note that USB ADB enumeration in TWRP takes ~35 seconds after rebooting from Linux 5.4.
- **`adb reboot bootloader`**: Notice that `S1_Boot` looks for Sony's proprietary magic `0x6f656d46` (`oemF` — `warmboot=0x6f656d46`), whereas upstream `sov35-kernel` writes standard Qualcomm `0x77665500` on `bootloader` reboot. Because of this mismatch, `adb reboot bootloader` from Linux 5.4 does **not** enter Fastboot; when USB power is attached, `S1_Boot` falls into offline charging mode (`androidboot.mode=charger`).
- **Plain `adb reboot` while USB cable is plugged in**: On Sony `S1_Boot`, a warm reset with VBUS present can also enter offline charger mode unless booted cold or triggered via `fastboot reboot`.

### 3. Reliable Hardware Key Combinations
1. **Enter Fastboot Mode (Blue LED)**:
   - Power off the phone completely (or force power-off by holding **Power + Volume Up** for ~8–10 seconds until it vibrates, then release immediately).
   - Hold **Volume Up** and plug the USB cable into the host computer.
   - Wait for the notification LED to turn **solid blue** and verify with `fastboot devices`.
2. **Enter TWRP Recovery (`FOTAKernel`)**:
   - From booted Android 17: run `adb reboot recovery` and wait ~35–40 seconds for TWRP ADB.
   - From powered-off state (USB unplugged): hold **Power + Volume Down** until the Sony logo appears.
3. **Force Hard Reset (if unresponsive)**:
   - Hold **Power + Volume Up**:
     - ~3 seconds (1 vibration): warm reset.
     - ~8–10 seconds (3 vibrations): hard power-off (equivalent to battery disconnect).

### 4. Restoring Stock / Previous State
With local partition backups stored in `backup/`, the device can be restored at any time from Fastboot or TWRP:
```bash
fastboot flash boot backup/boot.img
fastboot flash oem backup/oem.img
```

---

<a id="tieng-viet"></a>
## Tiếng Việt

### 1. Yêu Cầu Header Boot Image Của Sony `S1_Boot`
Bootloader `S1_Boot` (`1299-4832_S1_Boot_MSM8996`) trên Xperia XZs kiểm tra nghiêm ngặt cấu trúc Android Boot Image v0 và DTB đính kèm:
- **Thông số địa chỉ nạp**: `base=0x80000000`, `kernel_offset=0x00008000`, `ramdisk_offset=0x02000000`, `tags_offset=0x01e00000`, `pagesize=4096`, `header_version=0`.
- **Lưu ý trường `os_version`**: `S1_Boot` sẽ treo sớm (màn hình đen + đèn LED xanh lá) nếu đặt `--os_version 17.0.0`. Luôn đóng gói `boot.img` với `--os_version 10.0.0 --os_patch_level 2020-03`.
- **DTB đính kèm**: Kernel phải ở định dạng `Image.gz-dtb` chứa device tree `keyaki` (`msm8996-tone-keyaki`) tương thích với `S1_Boot`.

### 2. Cơ Chế Mã Khởi Động Lại (`warmboot`) Trên `S1_Boot`
Qua phân tích nhị phân `aboot` (`mmcblk0p13`) và kiểm chứng thực tế trên máy:
- **`adb reboot recovery`**: Ghi mã recovery (`0x77665502`), `S1_Boot` nạp TWRP độc lập từ phân vùng `FOTAKernel` (`mmcblk0p48`). Lưu ý TWRP mất khoảng ~35 giây để nhận USB ADB khi chuyển từ kernel 5.4 sang.
- **`adb reboot bootloader`**: `S1_Boot` của Sony yêu cầu mã riêng `0x6f656d46` (`oemF`), trong khi `sov35-kernel` ghi mã Qualcomm tiêu chuẩn `0x77665500`. Do đó `adb reboot bootloader` từ kernel 5.4 không vào thẳng Fastboot mà sẽ chuyển sang chế độ sạc tắt máy (`charger`) nếu đang cắm cáp USB.
- **`adb reboot` thường khi đang cắm cáp USB**: Trên `S1_Boot`, khởi động lại nóng khi có nguồn USB VBUS có thể khiến bootloader vào chế độ sạc tắt máy. Khuyến nghị khởi động từ trạng thái tắt nguồn hoặc dùng `fastboot reboot`.

### 3. Tổ Hợp Phím Cứng An Toàn Nhất
1. **Vào chế độ Fastboot (Đèn LED xanh dương)**:
   - Tắt nguồn máy hoàn toàn (hoặc cưỡng bức tắt nguồn bằng cách giữ **Nguồn + Tăng âm lượng** trong ~8–10 giây đến khi rung 3 nhịp rồi thả tay ngay).
   - Nhấn giữ phím **Tăng âm lượng (Volume Up)** và cắm cáp USB vào máy tính.
   - Đèn LED chuyển sang màu **xanh dương**, kiểm tra bằng `fastboot devices`.
2. **Vào TWRP Recovery (`FOTAKernel`)**:
   - Khi đang ở trong Android 17: chạy `adb reboot recovery` và đợi ~35–40 giây.
   - Khi máy đang tắt nguồn (rút cáp USB): nhấn giữ **Nguồn + Giảm âm lượng (Volume Down)** đến khi hiện logo Sony.
3. **Cưỡng bức tắt nguồn khi treo**:
   - Nhấn giữ **Nguồn + Tăng âm lượng**:
     - ~3 giây (rung 1 nhịp): khởi động lại nóng.
     - ~8–10 giây (rung 3 nhịp): ngắt nguồn cứng.

### 4. Khôi Phục Trạng Thái Trước Khi Flash
Với bản sao lưu lưu tại `backup/`, có thể khôi phục lại `boot` và `oem` bất cứ lúc nào qua Fastboot:
```bash
fastboot flash boot backup/boot.img
fastboot flash oem backup/oem.img
```

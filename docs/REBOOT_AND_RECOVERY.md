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
The current source is `drivers/power/reset/msm-poweroff.c`. Its reason values
are conditional on Sony target definitions; do not treat `oemF` as a universal
Fastboot code.

- **Recovery**: the `TARGET_SOMC_S1BOOT` branch writes `0x6f656d46` (`oemF`);
  the generic branch writes `0x77665502`. Recovery targets the standalone TWRP
  in FOTAKernel. Some transitions returned ADB after roughly 35–60 seconds;
  others did not enumerate USB and required a physical-key entry.
- **Bootloader**: the generic `bootloader` branch writes `0x77665500`. A separate
  `s1bootloader` branch writes `0x6f656d53`, but that route has not been validated
  in this bring-up. Use the hardware Volume Up + USB method for Fastboot.
- **System reboot from TWRP**: `adb reboot` successfully started the installed
  Android kernel during camera verification. Reboot behavior from Linux 5.4
  has been less reliable; allow for manual recovery entry rather than repeatedly
  issuing commands to an absent USB device.

### 3. Reliable Hardware Key Combinations
1. **Enter Fastboot Mode (Blue LED)**:
   - Power off the phone completely (or force power-off by holding **Power + Volume Up** for ~8–10 seconds until it vibrates, then release immediately).
   - Hold **Volume Up** and plug the USB cable into the host computer.
   - Wait for the notification LED to turn **solid blue** and verify with `fastboot devices`.
2. **Enter TWRP Recovery (`FOTAKernel`)**:
   - From Android 17, try `adb reboot recovery`. If TWRP USB does not return, use the physical-key sequence below.
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
Nguồn hiện tại là `drivers/power/reset/msm-poweroff.c`. Mã reason phụ thuộc
nhánh biên dịch Sony; không coi `oemF` là mã Fastboot dùng chung.

- **Recovery**: nhánh `TARGET_SOMC_S1BOOT` ghi `0x6f656d46` (`oemF`), nhánh
  generic ghi `0x77665502`. Recovery nằm ở FOTAKernel. Một số lần nhận ADB sau
  khoảng 35–60 giây; một số lần không xuất hiện trên USB, phải vào bằng phím cứng.
- **Bootloader**: nhánh `bootloader` generic ghi `0x77665500`. Nguồn còn có nhánh
  `s1bootloader` ghi `0x6f656d53`, nhưng chưa kiểm chứng đường này trong phiên
  bring-up. Dùng Tăng âm lượng + cắm USB để vào Fastboot.
- **Reboot hệ thống từ TWRP**: `adb reboot` đã boot được kernel Android đã nạp
  trong các lần kiểm tra camera. Reboot từ Linux 5.4 chưa ổn định bằng; nếu USB
  không nhận lại thì vào recovery bằng phím, không lặp lệnh với máy chưa kết nối.

### 3. Tổ Hợp Phím Cứng An Toàn Nhất
1. **Vào chế độ Fastboot (Đèn LED xanh dương)**:
   - Tắt nguồn máy hoàn toàn (hoặc cưỡng bức tắt nguồn bằng cách giữ **Nguồn + Tăng âm lượng** trong ~8–10 giây đến khi rung 3 nhịp rồi thả tay ngay).
   - Nhấn giữ phím **Tăng âm lượng (Volume Up)** và cắm cáp USB vào máy tính.
   - Đèn LED chuyển sang màu **xanh dương**, kiểm tra bằng `fastboot devices`.
2. **Vào TWRP Recovery (`FOTAKernel`)**:
   - Khi đang ở Android 17, thử `adb reboot recovery`. Nếu TWRP không nhận USB thì dùng tổ hợp phím bên dưới.
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

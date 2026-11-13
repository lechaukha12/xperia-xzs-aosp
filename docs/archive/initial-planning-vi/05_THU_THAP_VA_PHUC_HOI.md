# Thu thập thông tin và phục hồi

**Tài liệu chuẩn bị; các lệnh bên dưới chưa chạy trên điện thoại.** Chỉ đọc trong chế độ đang có. Thay `SERIAL` bằng thiết bị đã xác định, đặc biệt nếu kết nối nhiều máy. Không chia sẻ serial/IMEI lên báo cáo công khai.

## Khi máy đang ở TWRP

Các ví dụ dưới đây đọc dữ liệu, không mount/format/flash. Lệnh không hỗ trợ hoặc thiếu quyền thì lưu lỗi, không tự flash recovery khác để có lệnh đó.

```sh
adb devices -l
adb -s SERIAL shell uname -a
adb -s SERIAL shell cat /proc/cmdline
adb -s SERIAL shell cat /proc/partitions
adb -s SERIAL shell cat /proc/mounts
adb -s SERIAL shell cat /proc/filesystems
adb -s SERIAL shell ls -l /dev/block/bootdevice/by-name
adb -s SERIAL shell ls -l /dev/block/by-name
adb -s SERIAL shell ls -l /sys/fs/pstore
adb -s SERIAL shell cat /etc/recovery.fstab
adb -s SERIAL shell cat /etc/twrp.fstab
adb -s SERIAL shell getprop ro.product.model
adb -s SERIAL shell getprop ro.product.device
adb -s SERIAL shell getprop ro.boot.hardware
adb -s SERIAL shell getprop ro.boot.slot_suffix
adb -s SERIAL shell getprop ro.twrp.version
adb -s SERIAL shell getprop ro.boot.flash.locked
```

Một trong hai đường dẫn by-name hoặc fstab có thể không tồn tại. `uname`, `/proc/filesystems`, props ở đây thuộc **recovery đang chạy**, không chứng minh kernel, SDK, Treble hoặc filesystem support của ROM đích. Không dùng `ro.treble.enabled=false` trong recovery để kết luận mọi nền Treble đều bất khả thi.

Sau khi resolve đúng block path của từng partition, có thể đọc kích thước bằng `blockdev --getsize64` nếu tool tồn tại; đối chiếu sysfs sector count nếu không có. Chưa biết path thì chưa có lệnh backup/flash cụ thể. Không suy ra block number từ Internet.

Đọc fstab/init/vendor manifest/build props của phân vùng đã mount nếu tồn tại. Không tự mount đọc-ghi. Thực hiện trích xuất image và đọc offline khi hợp lý. Nếu đọc config qua `/proc/config.gz` được thì ghi đó là config recovery.

## Khi máy đang ở fastboot

```sh
fastboot devices
fastboot -s SERIAL getvar product
fastboot -s SERIAL getvar unlocked
fastboot -s SERIAL getvar version-bootloader
fastboot -s SERIAL getvar current-slot
fastboot -s SERIAL getvar has-slot:system
fastboot -s SERIAL getvar partition-size:boot
fastboot -s SERIAL getvar partition-size:system
fastboot -s SERIAL getvar partition-size:oem
```

Sony bootloader có thể không hỗ trợ một số getvar. `FAILED/unknown variable` là dữ liệu hạn chế, không phải lý do unlock/relock hay repartition. Người dùng đã xác nhận unlock; kiểm chứng là đối chiếu, không làm lại thủ tục. Getvar thường ghi ra stderr, cần lưu cả stdout/stderr khi lập log. Tránh `getvar all` nếu không cần vì dễ thu thêm định danh riêng.

## Backup trước khi ghi lần đầu

1. Lưu map by-name → block thật → size, ảnh/cách vào fastboot/TWRP và phiên bản công cụ.
2. Lưu bản sao image của vùng sắp thay, đặc biệt boot và recovery/FOTAKernel **sau khi xác minh mapping thực**. Không giả định tên `recovery` là tên partition vật lý.
3. Nếu nền Treble sẽ đổi oem/cache/system, sao lưu tương ứng và ghi cách trở lại mount layout cũ. Không bắt đầu bằng thay GPT.
4. Giữ dữ liệu calibration/TA/persist riêng nếu có thể đọc bằng quyền sẵn có; không tìm exploit hoặc thay vùng bảo vệ chỉ để hoàn tất danh mục backup.
5. Lưu backup trên host hoặc ổ ngoài, kiểm tra size/hash và đọc thử được. Bản sao nằm trong userdata điện thoại không đủ nếu sau đó wipe.

Chỉ tạo lệnh sao lưu cụ thể sau khi xác minh path và dung lượng. Sao lưu là đọc từ thiết bị ra file host; không dùng nhầm chiều `dd`, không chép image người khác vào vùng máy mình.

## Thu log boot đích

- Nếu Android đích có ADB: lấy `logcat -b all -d`, dmesg nếu được phép, danh sách process/service, `sys.boot_completed`, SDK/release và hình giao diện.
- Khi quay lại recovery: đọc ngay pstore/ramoops, last_kmsg nếu có, recovery log. Cơ chế này có thể không được kernel hỗ trợ hoặc log đã bị ghi đè; thiếu pstore không chứng minh lần boot thành công.
- Lưu theo ID thử; phân biệt rõ log recovery và log Android đích. Ghi timestamp host, thời gian từ lúc boot và các lần mất/kết nối USB.
- Không bật adbd không xác thực ra mạng; dùng kết nối USB có kiểm soát cho debug.

## Điều kiện để có đường phục hồi cụ thể

Cần có bộ file gốc/hash, map phân vùng và thứ tự khôi phục. Giữ được đường vào fastboot/recovery trước khi thay boot. Chưa có map thì không viết sẵn lệnh flash giả định. Không lấy một hướng dẫn “stock quốc tế full flash” làm phương án phục hồi SO-03J mặc định. Không relock để sửa bootloop.

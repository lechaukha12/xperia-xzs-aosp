# Nhật ký và bàn giao

## Trạng thái đầu ngày 12/11/2026

- Người dùng xác nhận SO-03J / Snapdragon 820, đã unlock bootloader.
- Đã wipe, vào được fastboot và TWRP; chưa có inventory trực tiếp.
- Đã nghiên cứu nguồn công khai, lấy metadata release và cấu hình nguồn nhỏ.
- Chưa tải image ROM, chưa build, chưa sửa image, chưa thao tác với USB/điện thoại.
- Mục tiêu M3 chưa đạt; M0 mới có dữ liệu người dùng, chưa có phép đo.
- Ưu tiên mới nhất: boot Android 17 trước; phần cứng sửa sau; chọn bản AOSP/vanilla gọn nếu tương thích.

## Mẫu INVENTORY

```text
Ngày/giờ, host/toolchain:
Model người dùng / model bootloader / model recovery:
Unlock: người dùng xác nhận / kiểm tra bổ sung:
Chế độ hiện tại, cách vào fastboot/TWRP:
Recovery image/version/location:
Boot image/kernel/DTB của ROM còn lại:
By-name map và size bytes:
Stock/SODP/Treble base và nguồn chứng minh:
Vendor mount thực tế, VNDK/FCM/HAL nếu đọc được:
SAR / slot / dynamic partition: từng trường riêng:
Filesystem trong recovery / kernel ROM đích: từng trường riêng:
Backup host + hashes:
Chưa biết / cách lấy dữ liệu tiếp:
```

## Mẫu EXPERIMENT_PLAN và log từng lần

```text
ID: E001
Mục tiêu/mốc:
Giả thuyết và bằng chứng hiện có:
Nền boot/kernel/vendor/DTB, nguồn/tag/hash:
GSI, nguồn/tag/asset, compressed hash/raw hash:
Filesystem và expanded bytes / partition capacity:
Thay đổi duy nhất hoặc nhóm thay đổi có quan hệ:
Patch/script tái tạo:
Image -> partition mapping đã xác minh:
Backup và quy trình quay lại:
Điều kiện trước thử / phạm vi thao tác:
Lệnh đã chạy và exit status:
Quan sát kernel/init/zygote/system_server/GUI:
Log/ảnh có đường dẫn:
Thời gian quan sát, có reboot/crash không:
Đạt M nào? Chưa chứng minh điều gì?
Hành động tiếp theo dựa trên lỗi đầu tiên:
```

## Mẫu KNOWN_ISSUES sau boot

| Thành phần | Trạng thái | Bằng chứng/ưu tiên sau M3 |
| --- | --- | --- |
| Hiển thị GUI | Chưa thử | |
| Cảm ứng | Chưa thử | Không chặn nghiệm thu boot nếu GUI đã lên |
| ADB Android đích | Chưa thử | Ưu tiên debug |
| Wi-Fi/Bluetooth | Chưa thử | Hoãn |
| SIM/data/VoLTE | Chưa thử | Hoãn |
| Camera trước/sau | Chưa thử | Hoãn |
| Âm thanh/mic | Chưa thử | Hoãn |
| NFC/FeliCa/vân tay | Chưa thử | Hoãn |
| Sleep/pin/nhiệt/sạc | Chưa thử | Hoãn tối ưu; theo dõi nhiệt bất thường khi thử |

## Cuối mỗi phiên

Ghi: mốc hiện tại; file đã tạo/sửa và hashes; cách tái tạo; lần thử cuối; điều gì đang hỏng; giả thuyết đã loại; việc tiếp theo cụ thể. Nếu thiếu máy/đầu vào thì nêu đúng dữ liệu cần, tiếp tục việc offline còn làm được. Không gọi một báo cáo nghiên cứu là ROM đã hoàn thành.

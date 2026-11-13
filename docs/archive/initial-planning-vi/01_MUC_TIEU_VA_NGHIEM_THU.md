# Mục tiêu và nghiệm thu

## Mục tiêu chính

Một bộ image/patch và quy trình có thể tái tạo, giúp **Android 17 thực sự khởi động đến giao diện Android** trên chiếc SO-03J này, giữ được khả năng quay lại fastboot/TWRP.

Ưu tiên AOSP/vanilla, không GApps/microG. AOSP thuần là ứng viên, không phải yêu cầu loại bỏ các bản vá legacy cần để boot. LineageOS vanilla/GSI cộng đồng được chấp nhận nếu giải thích rõ nền tảng và lý do tương thích. Không lược bỏ ngẫu nhiên thành phần hệ thống chỉ để giảm dung lượng.

## Mốc kiểm chứng

| Mốc | Ý nghĩa | Bằng chứng tối thiểu |
| --- | --- | --- |
| M0 | Hiểu trạng thái máy | Inventory có nguồn đo; phân biệt thông tin recovery và ROM; ghi rõ các trường chưa biết |
| M1 | Có bản thử phù hợp về cấu trúc | Nguồn/hash; image đã kiểm tra; map ghi; phương án phục hồi; không khẳng định đã boot |
| M2 | Kernel/init/userspace tiến triển | Log ngoài recovery cho thấy Android userspace chạy; nếu có ADB thì lưu service/process/log; vẫn chưa đạt giao diện |
| **M3** | **Boot Android 17 đến giao diện** | Hiện Setup Wizard/launcher/SystemUI của Android 17; framework đúng đời; một phiên đứng được khoảng 5 phút, không lặp reboot/crash system_server; log/hình quan sát được |
| M4 | Sửa phần cứng | Backlog riêng sau M3, do người dùng chọn ưu tiên |

Boot animation đơn thuần chỉ là tiến triển. Nếu system_server lên nhưng màn hình đen, ghi là **headless/userspace boot**, chưa đạt M3. Nếu GUI lên nhưng cảm ứng hỏng, vẫn có thể đạt M3. ADB rất nên có để debug; nếu chưa có thì dùng bằng chứng khác và ghi hạn chế. Dùng `sys.boot_completed=1` khi có thể quan sát; không coi một property đơn lẻ là đủ.

Android 17 phải được xác minh từ image/framework thật và dữ liệu trên máy, ví dụ SDK 37, zygote/system_server/SystemUI, log và màn hình. Recovery có SDK cũ là bình thường. Không đổi props để vượt nghiệm thu.

Sau phiên boot đầu, kiểm tra còn vào được đường phục hồi. Các lần cold boot lặp lại và tối ưu độ ổn định là bước tiếp nối, không kéo dài giai đoạn trước boot để sửa hết phần cứng.

## Ngoài phạm vi nghiệm thu hiện tại

Không bắt buộc: cảm ứng, GPU acceleration đầy đủ, Wi-Fi/Bluetooth/GNSS, SIM/data/VoLTE, camera, NFC/FeliCa, vân tay, mic/loa, DRM, 960fps, Google Play, ngân hàng, pin tốt hoặc OTA. Tuy nhiên storage/mount/graphics tối thiểu cần cho GUI vẫn là vấn đề chặn boot phải giải quyết.

## Gói kết quả khi đạt M3

- Image hoặc patch/script tạo image từ nguồn đã ghim, kèm SHA-256.
- Danh sách chính xác partition đã thay và thứ tự thao tác cho SO-03J này.
- Hướng dẫn quay lại bộ boot/recovery/nền trước thử nghiệm.
- Log boot, dấu hiệu phiên bản thật, ảnh/chứng cứ GUI, thời gian quan sát.
- Danh sách thay đổi chẩn đoán còn tồn tại: permissive, tắt dịch vụ, thay allocator, bỏ setup… nếu có.
- `KNOWN_ISSUES.md`: phần cứng chưa kiểm tra và lỗi đã thấy; không gọi bản này là daily driver.

Nếu chưa đạt M3, vẫn bàn giao artifact và log, nhưng kết luận phải là **chưa boot đến giao diện** cùng blocker cụ thể.

# Prompt khởi động agent

Bạn đang làm việc trong thư mục `xzs17` của tôi. Hãy đọc `AGENTS.md`, `README.md` và các tài liệu đánh số trước khi bắt đầu.

Máy của tôi là **Sony Xperia XZs SO-03J, Snapdragon 820, đã unlock bootloader**. Hiện đã wipe, chỉ vào được fastboot và TWRP. Tôi muốn **port Android 17 bằng image/nền có sẵn**, ưu tiên nền AOSP vanilla không GApps/microG. PC không đủ sức build toàn bộ Android từ đầu. Chưa có cấu hình PC cụ thể: kiểm tra host thực tế hoặc hỏi nếu bạn không truy cập được.

**Ưu tiên số một là Android 17 boot được đến giao diện.** Cảm ứng, Wi-Fi, SIM, camera, âm thanh và các lỗi phần cứng khác để giai đoạn sau; chỉ sửa ngay thành phần nào trực tiếp chặn boot. Không coi boot animation hoặc ADB của recovery là đã đạt mục tiêu.

Hãy tự tiếp tục nghiên cứu nguồn, kiểm tra artifact, phân tích kernel/vendor/Treble và chuẩn bị bản thử tái tạo được. Hồ sơ có ứng viên GSI Android 17 đã tồn tại, nhưng chưa có image nào được xác nhận chạy trên máy của tôi. Kiểm tra lại các link/tag, không tin danh sách ROM tổng hợp thay cho release và file thật.

Bắt đầu bằng inventory chỉ đọc trong chế độ máy đang có, lấy map phân vùng và xác định boot/recovery/kernel/vendor còn lại. Không giả định SO-03J có layout G8231, không giả định có `vendor`, `super`, `vbmeta` hoặc slot A/B. Chưa có điện thoại kết nối thì làm phần offline trước.

Đầu ra đầu tiên cần có: `outputs/INVENTORY.md`, `outputs/FEASIBILITY.md`, `outputs/EXPERIMENT_PLAN.md` với ứng viên đầu tiên, lý do chọn, hash, các điều kiện còn thiếu và đường phục hồi. Sau đó tiến tới thử boot khi các điều kiện kỹ thuật và phạm vi thao tác đã rõ. Không dừng ở một kế hoạch chung nếu còn làm được công việc cụ thể.

Không build toàn bộ AOSP trên host. Nếu cần, chỉ build thành phần nhỏ có bằng chứng bắt buộc. Không tự sử dụng dịch vụ trả phí, không sửa bootloader/TA/GPT để thử ROM, không hạ Android đích, không giả phiên bản bằng build.prop. Ghi log từng thử nghiệm và cập nhật `06_NHAT_KY_VA_BAN_GIAO.md` khi kết thúc phiên.

# Lộ trình ưu tiên boot

## P0 — Inventory, giữ đường phục hồi

- Đọc thông tin máy trong chế độ đang có, theo tài liệu 05. Không đổi chế độ tự động chỉ để lấy đủ một bảng.
- Nhận diện SO-03J bằng tổng hợp thông tin người dùng, bootloader, board/DTB và layout; ROM quốc tế có thể đổi model prop.
- Lưu map partition, kích thước, fstab, cmdline và cách vào TWRP. Sao lưu ở host các vùng sẽ bị thay, đặc biệt boot và recovery đang hoạt động.
- Xác định cái gì còn lại sau wipe. Không cài lại stock đầy đủ nếu chưa chứng minh cần.

**Đầu ra:** `outputs/INVENTORY.md`, trạng thái M0. Không đợi sửa phần cứng.

## P1 — Chọn một nền keyaki nhất quán

Ưu tiên tìm bộ boot/kernel/DTB + vendor/OEM Treble **có sẵn cho XZs**. Gói Sjll Android 10 là manh mối đầu tiên, không phải lệnh cài mặc định.

1. Lấy bài maintainer và nguồn tải gốc, xác minh còn truy cập được. Nếu mirror, ghi chuỗi nguồn và mức tin cậy.
2. Đọc installer để biết chính xác gói ghi những gì; kiểm tra có đổi cache/oem thành vendor hay không. Không trộn hai kiểu Fake Treble.
3. Đối chiếu SO-03J bằng partition/DTB/RAM và bộ blobs. Đích G8231 trong source không tự bảo đảm tương thích SO-03J.
4. Phân tích boot ramdisk, first-stage mount, fstab, dm-verity/AVB thực tế. Không tạo partition mới theo hướng dẫn điện thoại hiện đại.
5. Nếu cần đối chứng, dùng một system image cũ phù hợp nền đó để chứng minh chain kernel → mount → init. Chỉ cần tối thiểu để phân loại lỗi; không sửa camera/Wi-Fi cho ROM đối chứng.

Không lấy kernel TWRP làm nền Android 17 chỉ vì recovery boot được. Nếu chưa có nền phù hợp, có thể repack bộ keyaki có nguồn; build riêng kernel là phương án sau khi đã chỉ ra patch/config cần thiết.

**Đầu ra:** sơ đồ mount có bằng chứng, bộ nền được chọn, các điểm SO-03J còn chưa xác minh.

## P2 — Chọn và kiểm tra GSI Android 17 vanilla

- Xem tài liệu 04. Cân nhắc image không EROFS trước nếu kernel chưa chứng minh hỗ trợ EROFS. AOSP Google vẫn là ứng viên khi đáp ứng legacy compatibility.
- Ghim tag + asset, tải một ứng viên đầu tiên, so checksum do upstream công bố, rồi hash bản giải nén riêng. Giữ nguyên file gốc.
- Đọc định dạng thật, expanded size, kiến trúc, system-as-root; kiểm tra ARMv8 baseline, dependencies, filesystem, VINTF và linker/VNDK.
- Đối chiếu userspace/kernel thực: binder, mount namespace, APEX/loop/dm, SELinux, BPF/network startup, syscalls mà image sử dụng. Đây là danh sách cần điều tra khi liên quan, không phải tuyên bố tất cả đều thiếu.
- Không chuyển EROFS → ext4 bằng chép file thông thường rồi mất uid/gid, capabilities, xattrs/SELinux label và symlink. Nếu repack, ghi toolchain/metadata và kiểm chứng cấu trúc.
- Không xoá APEX, framework, matrix hoặc app tùy tiện để “nhẹ”. GApps/microG không cần cho boot đầu.

**Đầu ra:** `outputs/FEASIBILITY.md`, chọn duy nhất ứng viên đầu, nêu blocker và cách kiểm tra.

## P3 — Chuẩn bị bản thử cụ thể

Tạo `outputs/EXPERIMENT_PLAN.md` gồm:

- ID thử nghiệm, giả thuyết, artifact gốc/đã sửa và SHA-256.
- Map **image → partition thật**, kích thước trước/sau, phân vùng giữ nguyên.
- Lệnh được viết theo map đã xác minh, không lệnh mẫu Pixel; không gói chạy hàng loạt không kiểm soát.
- Cách lấy log ngay ở lần boot đầu và khi quay lại recovery; thời gian chờ hợp lý, điều kiện dừng khi reboot lặp.
- Bộ file và trình tự phục hồi boot/recovery/nền. Nếu `fastboot boot` được hỗ trợ thật, có thể cân nhắc boot tạm; không mặc định Sony hỗ trợ.

Đọc lại mọi script ghi máy, kể cả trong ZIP bên thứ ba. Không dùng gói thử ghi cả firmware/bootloader để chỉ thay system.

## P4 — Thử boot và xử lý lỗi đầu tiên

Sau khi điều kiện thử và phạm vi thao tác đã rõ, tiến hành từng lần thử có log. Không để máy reboot vô hạn hoặc chờ vô hạn mà không có quan sát.

| Triệu chứng | Điều tra trước |
| --- | --- |
| Không qua kernel hoặc reboot rất sớm | Boot header, DTB, cmdline, kernel, pstore; chưa đụng camera/RIL |
| Không mount system/vendor | Fstab/early mount, block path, SAR, filesystem, sparse, verity |
| init/linker lỗi | Libraries, namespace/VNDK, ELF, policy, service config |
| zygote/system_server chết | Log crash đầu, APEX, ART/framework, syscall/config thiếu |
| Có userspace nhưng màn hình đen | SurfaceFlinger, HWC/gralloc/EGL; software rendering chỉ nếu stack hỗ trợ |
| GUI lên, hardware lỗi | Ghi nhận M3 nếu đủ bằng chứng; chuyển lỗi không chặn boot sang backlog |

Không vô hiệu hóa hàng loạt dịch vụ. Nếu một HAL lỗi kéo system_server chết thì chỉ cô lập/đổi cấu hình có chủ đích, ghi rõ tác dụng phụ. Permissive chỉ là chẩn đoán tạm thời. Không áp dụng property đồ họa cũ chưa kiểm tra còn tác dụng trên Android 17.

## P5 — Bàn giao ngay khi đạt boot

Chốt artifact/hash, log, hình giao diện, bằng chứng phiên bản và đường phục hồi. Cập nhật `KNOWN_ISSUES.md`: có thể tất cả phần cứng ngoài hiển thị tối thiểu đều chưa kiểm tra. Tiếp tục sửa hardware ở giai đoạn sau, theo ưu tiên người dùng.

## Khi không thể tiến tới trong ràng buộc hiện tại

Không kết luận “PC yếu nên hết cách” khi chưa thử phân tích/repack. Nếu thiếu một khả năng kernel/HAL buộc phải biên dịch, chỉ rõ symbol/syscall/config/patch và khối lượng build riêng. Nếu không tìm được nền keyaki phù hợp hoặc chưa có máy để thử, tiếp tục phần offline và để lại blocker cụ thể, không công bố đã boot.

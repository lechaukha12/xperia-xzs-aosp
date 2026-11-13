# Nghiên cứu ban đầu — 12/11/2026

## Kết luận hiện tại

**Có đường nghiên cứu port dựa trên image có sẵn; chưa chứng minh Android 17 boot trên SO-03J.** Hướng đáng thử là nền kernel/vendor/Treble của keyaki + GSI Android 17 vanilla có hỗ trợ legacy phù hợp. Đây là giả thuyết kỹ thuật, không phải combo đã được thử thành công.

## Dữ kiện đã kiểm tra

1. **SO-03J là biến thể Nhật cần giữ danh tính riêng.** Sony ghi RAM 4 GB, bộ nhớ 32 GB, Android 7.1 lúc xuất xưởng và các tính năng riêng như Osaifu-Keitai. Người dùng xác nhận Snapdragon 820, bootloader đã mở, chỉ còn fastboot/TWRP. [Thông số Sony](https://www.sony.jp/xperia/xperia/docomo/so-03j/spec.html)

2. **SODP keyaki/tone có mã nguồn cũ, không phải Android 17 có sẵn.** GitHub API trả về các nhánh tới `q-mr1` ở hai repo Sony tại ngày kiểm tra. Đã lưu commit và cấu hình. BoardConfig keyaki nêu G8231/G8232, không nêu đích SO-03J. Kích thước trong đó không phải phép đo máy người dùng. [keyaki](https://github.com/sonyxperiadev/device-sony-keyaki) · [tone](https://github.com/sonyxperiadev/device-sony-tone)

3. **tone truyền thống không có vendor partition riêng theo cấu hình nguồn đã đọc:** `TARGET_COPY_OUT_VENDOR := system/vendor`. Fstab nguồn có `system`, `oem` → `/odm`, và `FOTAKernel` → `/recovery`. Đây là cấu hình upstream, chưa xác nhận chiếc SO-03J hiện tại còn dùng layout/mount này. [PlatformConfig ghim commit](https://github.com/sonyxperiadev/device-sony-tone/blob/959d560da6de7252dad4affae93cb529e5475c68/PlatformConfig.mk) · [fstab](https://github.com/sonyxperiadev/device-sony-tone/blob/959d560da6de7252dad4affae93cb529e5475c68/rootdir/vendor/etc/fstab.tone)

4. **Có nền Treble Android 10 cho Xperia XZs do Sjll được cộng đồng dẫn đến XDA.** Chưa đọc được bài XDA đầy đủ: web gặp timeout, curl nhận 403; chưa lấy gói ZIP, chưa xác minh checksum hoặc SO-03J. Không được biến link tồn tại thành tuyên bố gói còn tải được hay dùng được trên máy này. [Trang builds](https://opendevices.ix5.org/builds/)

5. **Có ít nhất hai kiểu ghép Treble khác nhau.** Tác giả ix5 mô tả phương án của mình dùng OEM làm vendor và ghép ODM bên trong; tác giả cũng phân biệt Sjll tái dùng cache. Bài Fake Treble là cho **XZ/kagura**, tham khảo kiến trúc tone, không sao chép lệnh flash sang XZs. [Bài tác giả](https://sx.ix5.org/mobile-projects/) · [Fake Treble](https://sx.ix5.org/info/fake-treble-for-xperia-xz/)

6. **Android 17 GSI đã có artifact công khai.** Đã kiểm tra trang Google, release RestlessOS và LineageOS 24 GSI của eyzner. Metadata release được lưu; **chưa tải image hoặc kiểm tra hash nội dung**. Xem bảng ứng viên để tránh nhầm GSI chung với ROM hỗ trợ SO-03J. [Google](https://developer.android.com/about/versions/17/gsi-release-notes) · [RestlessOS](https://github.com/cawilliamson/treble_restlessos/releases/tag/17.0.0-202611021750) · [LineageOS GSI](https://github.com/eyzner/LineageOS-GSI/releases/tag/lineage-24.0-20261029)

7. **EROFS cần được kiểm tra trước.** Bản LineageOS GSI 04/11 được maintainer mô tả là EROFS; release 29/10 có thêm asset không mang nhãn EROFS. RestlessOS cũng có hai biến thể tên file. Không suy ra định dạng chính xác chỉ từ tên: sau tải phải đọc magic/superblock. EROFS xuất hiện upstream Linux 4.19, nên không mặc định kernel 4.9 cũ mount được nếu chưa có backport. [Release 04/11](https://github.com/eyzner/LineageOS-GSI/releases/tag/lineage-24.0-20261104) · [AOSP EROFS](https://source.android.com/docs/core/architecture/kernel/erofs)

8. **xperable không phải công cụ dành cho nền này theo README công bố.** Dự án nhắm Yoshino/MSM8998 và Tama/SDM845; SO-03J là MSM8996. Người dùng đã unlock, nên loại bỏ hẳn công việc unlock/relock khỏi kế hoạch boot. [README tác giả](https://github.com/j4nn/xperable)

## Điều không được kết luận vội

- Có Treble Android 10 **không bảo đảm** chạy Android 17: còn FCM/HAL, linker/VNDK, syscall/kernel và đồ họa. FCM có vòng đời loại bỏ HAL cũ. [FCM](https://source.android.com/docs/core/architecture/vintf/fcm)
- Hướng dẫn GSI của Google dành cho thiết bị đáp ứng điều kiện của họ; SO-03J dùng nền cộng đồng là thử nghiệm ngoài luồng hỗ trợ chuẩn. [Điều kiện GSI](https://developer.android.com/topic/generic-system-image)
- `BOARD_KERNEL_PAGESIZE := 4096` trong cấu hình boot cũ không tự chứng minh runtime page size hoặc tương thích image Android 17.
- Hỗ trợ máy mới trong GSI không suy ra hỗ trợ Adreno 530/keyaki. Ghi chú “Sony camera fix” ở release không đồng nghĩa camera XZs chạy.
- Image nhỏ nhất chưa chắc boot dễ nhất. AOSP Google có thể ít bản vá legacy hơn GSI cộng đồng.
- Không có bằng chứng đã kiểm tra cho ROM Android 17 dành riêng **SO-03J**; đây là phạm vi tìm kiếm sơ bộ, không khẳng định trên Internet không tồn tại.

## Các câu hỏi agent phải tự giải quyết

| Vấn đề | Cách lấy bằng chứng |
| --- | --- |
| Thực tế còn boot/kernel/vendor nào? | Inventory TWRP + bản sao và giải nén image; không đoán từ lời “wipe” |
| TWRP nằm đâu và khởi động bằng cách nào? | Hỏi cách vào máy, đọc partition map và image; không ghi đè đường phục hồi |
| Dùng nền stock hay SODP? | Đối chiếu nguyên bộ kernel/DTB/blobs/fstab/manifest |
| Gói Treble XZs cũ còn lấy được? | Nguồn maintainer, hash, đọc script, đối chiếu SO-03J |
| GSI có VNDK/HAL compatibility cần thiết? | Manifest/matrix, libraries, linker config và log lúc boot |
| Kernel đáp ứng filesystem, binder, APEX và syscall? | Config/source/dmesg/log; xử lý lỗi đầu tiên có thực |
| Có đủ chỗ cho image? | Kích thước block thực + raw/sparse expanded image; không dựa vào ZIP/XZ |
| PC nào thực hiện? | OS/CPU/RAM/đĩa/USB/toolchain thực tế; không dùng cấu hình máy soạn tài liệu thay người dùng |

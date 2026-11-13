# Ứng viên và nguồn kiểm chứng

Kiểm tra ngày **12/11/2026**. Các checksum trong JSON là metadata do GitHub API công bố; **chưa tải file để đối chiếu nội dung**. Tag được ghim để tái tạo, không có nghĩa đây luôn là bản mới nhất khi agent bắt đầu.

## GSI Android 17

| Ứng viên | Artifact/nguồn | Đánh giá ban đầu |
| --- | --- | --- |
| LineageOS 24 GSI vanilla, 29/10/2026 | [Release maintainer](https://github.com/eyzner/LineageOS-GSI/releases/tag/lineage-24.0-20261029), `lineage-24.0-20261029-UNOFFICIAL-arm64_bvN.img.xz` | Ứng viên khảo sát đầu: có asset không nhãn EROFS, nền cộng đồng. Phải xác minh filesystem thật và legacy support; không có bằng chứng SO-03J |
| RestlessOS 17, 02/11/2026 | [Release maintainer](https://github.com/cawilliamson/treble_restlessos/releases/tag/17.0.0-202611021750), `RestlessOS-arm64-ab-17.0.0-202611021750.img.xz` | Ứng viên thay thế và nguồn patch: release nêu xử lý legacy kernel, VNDK 28/29. Đây là fork GSI, không phải AOSP thuần hay GrapheneOS chính thức; không suy ra tương thích XZs |
| Google AOSP Android 17 GSI không GMS | [Trang chính thức](https://developer.android.com/about/versions/17/gsi-release-notes) | Ưu tiên khi phù hợp nền thực. Dùng làm đối chứng AOSP thuần; chưa ghim/tải asset, chưa chứng minh vendor cũ đáp ứng điều kiện |
| LineageOS 24 vanilla, 04/11/2026 | [Release maintainer](https://github.com/eyzner/LineageOS-GSI/releases/tag/lineage-24.0-20261104), `LINEAGEOS24-VANILLA-EROFS.img.xz` | Không chọn đầu nếu kernel chưa hỗ trợ EROFS. Mới hơn không tự có lợi cho mục tiêu boot |

**Không bắt buộc chọn LineageOS.** Sau kiểm tra image và nền máy, agent được đổi thứ tự bằng lập luận cụ thể. Tên file không đủ chứng minh filesystem, CPU instruction requirements hoặc compatibility. Bản vanilla cũng có thể chứa ứng dụng/tuỳ biến riêng; ghi rõ khi bàn giao.

## Nền XZs và kiến trúc tone

- [Sjll Treble Android 10 cho XZs — XDA](https://xdaforums.com/t/10-0-project-treble-for-xperia-xzs-2020-03-18.3976367/): **chưa đọc được** nội dung đầy đủ, chưa lấy ZIP. [Trang builds cộng đồng](https://opendevices.ix5.org/builds/) xác nhận có dẫn mục XZs. Không tự tạo tên file/link tải hoặc checksum bị thiếu.
- [SODP keyaki](https://github.com/sonyxperiadev/device-sony-keyaki/tree/38d60836be9bb97e894dabe7f4f9d80803e264f2), `q-mr1` tại `38d60836be9bb97e894dabe7f4f9d80803e264f2`.
- [SODP tone](https://github.com/sonyxperiadev/device-sony-tone/tree/959d560da6de7252dad4affae93cb529e5475c68), `q-mr1` tại `959d560da6de7252dad4affae93cb529e5475c68`.
- [Sjll tone q-mr0-4.9](https://github.com/sjllls/device-sony-tone/tree/ee798ed0d2d397d8996d2e455439b90808e11634), commit `ee798ed0d2d397d8996d2e455439b90808e11634`: đã đọc PlatformConfig/fstab. Đây là source lịch sử; không khẳng định nó chính là source của ZIP XDA.
- [Sjll keyaki](https://github.com/sjllls/device-sony-keyaki/tree/2ede8454add6bac8abea30eb6b876de9835ec1bb), master tại `2ede8454add6bac8abea30eb6b876de9835ec1bb`: đã đọc BoardConfig.
- [Fake Treble cho XZ/kagura](https://sx.ix5.org/info/fake-treble-for-xperia-xz/): tham khảo bố trí vendor/OEM, không phải hướng dẫn flash SO-03J.
- [Giải thích của tác giả ix5](https://sx.ix5.org/mobile-projects/): phân biệt thiết kế ix5 với Sjll.

## Tài liệu nền cần đối chiếu với artifact

- [GSI: điều kiện thiết bị](https://developer.android.com/topic/generic-system-image).
- [VINTF/FCM và vòng đời HAL](https://source.android.com/docs/core/architecture/vintf/fcm).
- [VNDK](https://source.android.com/docs/core/architecture/vndk).
- [EROFS](https://source.android.com/docs/core/architecture/kernel/erofs).
- [Boot partition qua các thế hệ Android](https://source.android.com/docs/core/architecture/partitions/generic-boot).
- [Thông số SO-03J chính thức](https://www.sony.jp/xperia/xperia/docomo/so-03j/spec.html).
- [xperable — phạm vi Yoshino/Tama](https://github.com/j4nn/xperable): chỉ để loại trừ áp dụng nhầm; máy đã unlock.

## Quy trình ghi nhận nguồn mới

Ghi URL trang release và URL asset, ngày kiểm tra, tag/commit, maintainer, license/phạm vi phân phối nếu định phát hành, compressed size, expected digest và local digest. Ghi riêng hash file nén, hash raw image và hash sau sửa. Hash tải từ cùng nguồn không tự chứng minh an toàn hay tương thích. Không chạy script trong README/ZIP chỉ vì vừa tải được.

`research/evidence/` chứa một số metadata/cấu hình nguồn nhỏ và danh mục có URL. Không có image ROM trong hồ sơ này. File lỗi/response rỗng không được dùng làm bằng chứng artifact hợp lệ.

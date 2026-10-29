# Tri Thức Miền Ngành Hàng Áo Mưa & E-Commerce (Domain Knowledge)

Tài liệu này hệ thống hóa các đặc trưng kinh doanh, thói quen ngôn ngữ phản hồi của khách hàng và các mẫu xử lý thực tế trên Shopee và TikTok Shop cho ngành hàng **Áo mưa**.

---

## 1. Bản Đồ 8 Khía Cạnh Cốt Lõi (ABSA Aspect Mapping)

| Khía Cạnh | Định Nghĩa Trong Ngành Áo Mưa | Từ Khóa Nhận Diện Phổ Biến | Lỗi / Khen Thường Gặp |
| :--- | :--- | :--- | :--- |
| `WATERPROOF` | Khả năng cản nước, độ kín đường may, chống tràn nẹp | Thấm, ướt, nước vào, dột, rỉ, đường ép, chống nước | Thấm qua đường chỉ may không dán băng nhiệt, nước tạt vào cổ áo |
| `MATERIAL_DURABILITY` | Chất lượng vải (PVC, dù tổ ong, EVA), độ bền cơ học | Vải mỏng, rách nách, toác đáy, rách chỉ, bền, dày dặn | Kéo căng bị rách ở đáy quần/nách áo, khóa kéo rít/gãy |
| `FIT_SIZE` | Chiều dài vạt áo, độ rộng khi ngồi lái xe hoặc đeo balo | Ngắn, dài quét đất, chật, rộng thùng thình, cỡ, size | Mặc vừa nhưng đeo balo 15 inch thì vạt sau bị kéo hở lưng |
| `COMFORT_USABILITY` | Trọng lượng, độ thoáng khí, kính chắn gió, xỏ gương | Hầm bí, mùi nhựa, kính mờ, gương xe, gấp gọn, nhẹ | Đi mưa mùa hè bị bí mồ hôi bên trong; kính chắn mờ không thấy đường |
| `PRICE_VALUE` | Mức độ tương xứng giữa giá bán và chất lượng sản phẩm | Đáng tiền, giá rẻ, đắt, tiền nào của nấy, hời, săn sale | 150k mà vải mỏng như áo mưa dùng 1 lần $\rightarrow$ thất vọng |
| `PACKAGING_SHIPPING` | Đóng gói túi bọc, hộp carton, thời gian vận chuyển | Giao nhanh, đóng gói kỹ, rách túi, ship lâu, shipper | Túi zip tiện lợi; giao chậm 5 ngày hết đợt bão |
| `CUSTOMER_SERVICE` | Thái độ phản hồi tin nhắn của shop, hỗ trợ đổi trả | Shop tư vấn nhiệt tình, shop chảnh, đổi hàng, bảo hành | Nhắn tin shop không rep; shop chủ động gửi áo mới khi báo lỗi |
| `ACCESSIBILITY_DESIGN` | Màu sắc, hoa văn, thẩm mỹ, thiết kế phản quang an toàn | Màu đẹp, phản quang, xấu, xỉn màu, nam tính, thời trang | Dải phản quang ban đêm an toàn; màu thực tế khác trên livestream |

---

## 2. Từ Điển Teencode & Viết Tắt Đặc Trưng Trên Sàn TMĐT Việt Nam

```json
{
  "ko": "không", "k": "không", "kh": "không", "hok": "không",
  "dc": "được", "đc": "được",
  "sp": "sản_phẩm",
  "chât": "chất", "chat": "chất", "ntn": "như_thế_này",
  "r": "rồi", "cx": "cũng", "mk": "mình",
  "dầy": "dày", "thung": "thủng",
  "bthg": "bình_thường", "tam_on": "tạm_ổn",
  "ship": "vận_chuyển", "giao_h": "giao_hàng",
  "rat": "rất", "wa": "quá", "qúa": "quá",
  "ok": "tốt", "oke": "tốt", "oki": "tốt", "okiela": "tốt",
  "shop": "cửa_hàng", "rep": "phản_hồi", "inbox": "nhắn_tin",
  "tiền_nào_của_nấy": "chất_lượng_tương_xứng_giá_rẻ"
}
```

---

## 3. Playbook 12 Hành Động Mẫu Cho Shop Áo Mưa (`playbook_aomua.yaml`)

1. **`pb_waterproof_video` (Listing Update):** Khi `WATERPROOF` bị chê $\ge 15\%$ $\rightarrow$ Bổ sung video test xịt nước áp lực vào đường ép nhiệt lên ảnh bìa sản phẩm.
2. **`pb_size_chart_backpack` (Listing Update):** Khi `FIT_SIZE` có nhiều thắc mắc $\rightarrow$ Thêm bảng size chi tiết kèm khuyến cáo: "Nếu đeo balo đi học/đi làm, nên tăng lên 1 size".
3. **`pb_breathable_content` (Content Marketing):** Khi `COMFORT_USABILITY` bị kêu hầm bí $\rightarrow$ Sản xuất video giải thích vật lý: vải chống nước tuyệt đối sẽ không thoát khí như cotton, hướng dẫn mở hé khóa nẹp cổ áo khi trời mưa nhỏ.
4. **`pb_fold_short_video` (Content Marketing):** Khi `COMFORT_USABILITY` được khen nhỏ gọn $\rightarrow$ Sản xuất video TikTok 15s "Thử thách gấp áo mưa bỏ vừa cốp xe Vision trong 10 giây".
5. **`pb_rainy_season_bundle` (Promotion):** Khi `PRICE_VALUE` là thế mạnh $\rightarrow$ Thiết lập Flash Sale combo Mua Áo Mưa tặng kèm Bọc Giày Đi Mưa vào mùa bão.
6. **`pb_negative_reply_template` (Review Reply / CSKH):** Khi khách đánh giá 1 sao do lỗi rách $\rightarrow$ Phản hồi xin lỗi công khai, cam kết đổi mới trong 48h không mất phí, chủ động inbox khách. *(Quy tắc: Không gạ khách đổi đánh giá 1 sao thành 5 sao)*.
7. **`pb_color_real_photo` (Listing Update):** Khi `ACCESSIBILITY_DESIGN` bị chê khác màu thực tế $\rightarrow$ Bổ sung ảnh chụp thật dưới ánh sáng tự nhiên không qua filter chỉnh màu.
8. **`pb_zipper_guide` (Packaging / Content):** Khi khách phàn nàn khóa kéo bị kẹt $\rightarrow$ Đính kèm tờ hướng dẫn nhỏ trong túi áo: cách kéo khóa thẳng hàng và bôi nhẹ nến/sáp nếu rít.
9. **`pb_seam_tape_qc` (Product Fix / Ops):** Khi `WATERPROOF` có tỷ lệ rò rỉ $\ge 20\%$ $\rightarrow$ Yêu cầu xưởng may nâng nhiệt độ máy ép dán băng keo chống thấm (seam tape) từ 180°C lên 200°C.
10. **`pb_packaging_upgrade` (Ops):** Khi túi nilon bị rách trong vận chuyển $\rightarrow$ Đổi sang túi zip mờ cao cấp có lỗ thoát khí.
11. **`pb_review_request_rainy_day` (Customer Care):** Tự động gửi tin nhắn hỏi thăm trải nghiệm khách hàng sau cơn mưa lớn đầu tiên tại khu vực của họ.
12. **`pb_livestream_rain_test` (Content / Sales):** Tổ chức phiên Livestream trực tiếp xối nước tại chỗ để chốt đơn vào những khung giờ dự báo thời tiết có bão.

<!-- CreBy: MenBoyBMN -->


# Tri Thức Miền Vận Hành Thương Mại Điện Tử & Ngành Hàng Áo Mưa (Production Domain Knowledge)

Tài liệu này hệ thống hóa các quy tắc nghiệp vụ thực tế, đặc trưng ngôn ngữ phản hồi của người mua hàng Việt Nam, bộ kịch bản hành động chuẩn (`playbook_aomua.yaml`) và rào chắn an toàn CSKH trên **Shopee** và **TikTok Shop**.

---

## 1. Bản Đồ 8 Khía Cạnh Vận Hành Cốt Lõi (ABSA Aspect Taxonomy)

| Mã Khía Cạnh | Ý Nghĩa Nghiệp Vụ Thực Tế | Từ Khóa Nhận Diện Phổ Biến (`vn_social_lexicon.yaml`) | Điểm Đau (Pain Points) & Điểm Cộng Thường Gặp |
| :--- | :--- | :--- | :--- |
| `WATERPROOF` | Khả năng chống thấm nước, độ kín đường ép nhiệt, chống tràn nẹp cổ/khóa | Thấm, ướt, nước vào, dột, rỉ nước, đường ép, băng keo nhiệt, chống nước | Nước ngấm qua đường chỉ may chưa ép kỹ; nước tạt qua khe khóa kéo khi đi mưa to |
| `MATERIAL_DURABILITY` | Chất lượng vải (PVC, dù tổ ong, EVA, tráng PU), độ bền cơ học, phụ kiện | Vải mỏng, rách nách, toác đáy, bung chỉ, dày dặn, khóa kéo, cúc bấm | Căng chân khi lên xe bị toác đáy quần; khóa kéo bị rít hoặc gãy đầu khóa |
| `FIT_SIZE` | Kích cỡ chiều dài/chiều rộng, độ che phủ khi lái xe hoặc đeo balo | Ngắn, dài quét đất, chật, rộng, form, size, đeo balo, hở lưng | Mặc bình thường thì vừa nhưng khi đeo balo 15 inch bị kéo hớt vạt áo sau |
| `COMFORT_USABILITY` | Trải nghiệm sử dụng, độ thoáng khí, mùi nhựa, kính chắn mưa, tai gương | Hầm bí, mùi nhựa nồng, kính mờ, bọc gương, gấp gọn, nhẹ, vướng víu | Mặc mùa hè bị hấp hơi nóng bên trong; kính chắn nước mưa bị mờ khó quan sát |
| `PRICE_VALUE` | Tương quan giữa giá tiền bỏ ra và chất lượng thực nhận, ưu đãi | Đáng tiền, giá rẻ, đắt, tiền nào của nấy, hời, săn sale, voucher | Mua phân khúc cao cấp nhưng trải nghiệm không vượt trội so với áo mưa thường |
| `PACKAGING_SHIPPING` | Quy cách đóng gói túi/hộp, tốc độ giao hàng, tình trạng ngoại quan | Giao nhanh, đóng gói kỹ, rách túi, ship lâu, hộp móp, túi zip | Túi đựng đi kèm bị rách đường hàn; giao hàng chậm làm lỡ đợt mưa bão |
| `CUSTOMER_SERVICE` | Tốc độ và thái độ tư vấn của shop, chính sách bảo hành & đổi trả | Shop nhiệt tình, không rep, tư vấn chuẩn, đổi trả nhanh, bảo hành | Khách báo lỗi rách nhưng shop phản hồi chậm; shop chủ động gửi bù sản phẩm mới |
| `ACCESSIBILITY_DESIGN` | Màu sắc thực tế, kiểu dáng thời trang, dải phản quang ban đêm | Màu đẹp, lệch màu, phản quang, thời trang, xỉn màu, mẫu mã | Màu thực tế tối hơn ảnh studio/livestream; có dải phản quang đi đêm an toàn |

---

## 2. Chuẩn Hóa Ngôn Ngữ Mạng Xã Hội & Teencode TMĐT (`normalize.py`)

Khách hàng trên Shopee và TikTok Shop thường sử dụng từ viết tắt, không dấu, hoặc tiếng lóng. Bộ tiền xử lý thực hiện chuẩn hóa xác định trước khi đưa vào phân tích:

```json
{
  "ko": "không", "k": "không", "kh": "không", "hok": "không", "hong": "không",
  "dc": "được", "đc": "được",
  "sp": "sản_phẩm", "hang": "hàng",
  "chât": "chất", "ntn": "như_thế_này",
  "r": "rồi", "cx": "cũng", "mk": "mình", "nv": "nhân_viên",
  "dầy": "dày", "thung": "thủng",
  "bthg": "bình_thường", "tam_on": "tạm_ổn",
  "ship": "vận_chuyển", "giao_h": "giao_hàng",
  "rat": "rất", "wa": "quá", "qúa": "quá",
  "ok": "tốt", "oke": "tốt", "oki": "tốt", "okiela": "tốt",
  "shop": "cửa_hàng", "rep": "phản_hồi", "ib": "nhắn_tin", "inbox": "nhắn_tin",
  "tiền_nào_của_nấy": "chất_lượng_tương_xứng_giá_rẻ"
}
```

---

## 3. Playbook 12 Kịch Bản Hành Động Thực Chiến (`knowledge/playbook_aomua.yaml`)

Hệ thống kết hợp dữ liệu thống kê thực tế với Playbook ngành hàng để sinh các đề xuất hành động cụ thể cho đội ngũ Marketing và Vận hành:

1. **`pb_waterproof_video` (`LISTING_UPDATE` - Marketing):** Khi `WATERPROOF` có tỷ lệ phàn nàn $\ge 15\%$ $\rightarrow$ Quay và ghim video thực tế thử nghiệm xịt vòi nước áp lực cao trực tiếp vào đường ép nhiệt và nẹp khóa kéo lên vị trí đầu tiên của trang sản phẩm.
2. **`pb_size_chart_backpack` (`LISTING_UPDATE` - Marketing):** Khi `FIT_SIZE` phát sinh nhiều phản hồi chật/ngắn $\rightarrow$ Cập nhật ảnh bảng quy đổi kích cỡ theo chiều cao + cân nặng, bổ sung lưu ý nổi bật: *"Khách hàng thường xuyên đeo balo đi làm/đi học nên chọn tăng 1 size"*.
3. **`pb_breathable_content` (`CONTENT` - Marketing):** Khi `COMFORT_USABILITY` bị phản ánh hầm bí $\rightarrow$ Đăng tải nội dung hướng dẫn sử dụng đúng cách và giải thích đặc tính vật lý của vải chống nước tuyệt đối, kèm mẹo thông gió khi mưa nhỏ.
4. **`pb_fold_short_video` (`CONTENT` - Marketing):** Khi `COMFORT_USABILITY` được khen ngợi về độ gọn nhẹ $\rightarrow$ Chuyển hóa thành video ngắn (TikTok/Shopee Video 15s) hướng dẫn gấp gọn áo mưa bỏ vừa cốp xe tay ga trong 10 giây để tăng tỷ lệ chuyển đổi.
5. **`pb_rainy_season_bundle` (`PROMOTION` - Marketing):** Khi `PRICE_VALUE` có phản hồi tích cực cao $\rightarrow$ Thiết lập chương trình Mua Kèm Deal Sốc (Combo Áo mưa + Bọc giày đi mưa chống trượt) vào các đợt dự báo áp thấp nhiệt đới.
6. **`pb_negative_reply_template` (`REVIEW_REPLY` - Marketing/CSKH):** Khi xuất hiện đánh giá 1–2 sao về lỗi sản phẩm $\rightarrow$ Kích hoạt quy trình phản hồi công khai xin lỗi chuyên nghiệp trong vòng 24h, hướng dẫn khách nhắn tin qua kênh Chat chính thức của sàn để được bảo hành đổi mới 1-1 miễn phí.
7. **`pb_color_real_photo` (`LISTING_UPDATE` - Marketing):** Khi `ACCESSIBILITY_DESIGN` bị phàn nàn lệch màu $\rightarrow$ Bổ sung ảnh chụp thực tế bằng điện thoại dưới ánh sáng tự nhiên ngoài trời cho từng phân loại màu sắc.
8. **`pb_zipper_guide` (`OPS` - Vận hành):** Khi khách hàng gặp tình trạng kẹt khóa kéo hoặc mùi nhựa mới $\rightarrow$ Bổ sung thẻ hướng dẫn sử dụng & bảo quản (cách treo ráo nước, xử lý khóa kéo và bay mùi nhựa lần đầu) vào trong mỗi túi sản phẩm xuất kho.
9. **`pb_seam_tape_qc` (`PRODUCT_FIX` - Sản xuất/Vận hành):** Khi lỗi thấm nước qua đường may (`WATERPROOF`) vượt ngưỡng cảnh báo $\ge 20\%$ $\rightarrow$ Làm việc trực tiếp với xưởng gia công để kiểm tra lại nhiệt độ/áp lực máy ép băng keo chống thấm (seam tape) và nâng tỷ lệ kiểm tra QC ngẫu nhiên trước khi nhập kho.
10. **`pb_packaging_upgrade` (`OPS` - Vận hành):** Khi `PACKAGING_SHIPPING` ghi nhận lỗi rách túi đựng $\rightarrow$ Thay thế bao bì mỏng bằng túi zip nhựa dẻo dày hơn có khóa kéo bền để khách tái sử dụng lâu dài.
11. **`pb_review_request_rainy_day` (`CUSTOMER_CARE` - Marketing/CSKH):** Tối ưu tin nhắn chăm sóc tự động sau nhận hàng 3–5 ngày để hỏi thăm trải nghiệm sử dụng thực tế và kịp thời xử lý nếu có lỗi phát sinh trước khi khách để lại đánh giá tiêu cực.
12. **`pb_livestream_rain_test` (`CONTENT` - Marketing/Sales):** Tổ chức phiên Livestream thực chiến test độ bền kéo giãn và xối nước trực tiếp tại kho vào các khung giờ cao điểm mùa mưa để giải tỏa nghi ngại của người mua.

---

## 4. Sáu Quy Tắc Bảo Vệ Tự Động Khi Phản Hồi Khách Hàng (`ReplyAssistant` G1–G6)

Khi sử dụng tính năng soạn thảo câu trả lời tự động cho bộ phận CSKH (`POST /api/v1/reviews/{id}/reply-draft`), mọi văn bản đều được kiểm tra qua 6 chốt chặn xác định:
- **G1 (Chống cam kết tuyệt đối sai sự thật):** Cấm sử dụng các cụm từ phóng đại dễ gây tranh chấp như *"chống thấm 100% vĩnh viễn"*, *"không bao giờ rách"*.
- **G2 (Tuân thủ chính sách sàn TMĐT):** Tuyệt đối cấm hành vi gạ gẫm/ép khách sửa đánh giá 1 sao thành 5 sao để đổi lấy tiền/quà, cấm điều hướng giao dịch ra ngoài sàn (Zalo, Facebook, chuyển khoản riêng).
- **G3 (Bảo mật thông tin & Chống gắn link lạ):** Cấm chèn số điện thoại cá nhân, địa chỉ email hoặc đường dẫn URL bên ngoài vào nội dung phản hồi công khai.
- **G4 (Kiểm soát độ dài chuẩn mực):** Độ dài phản hồi nằm trong ngưỡng tiêu chuẩn từ **40 đến 600 ký tự** (đủ lịch sự, đầy đủ thông tin nhưng không dài dòng).
- **G5 (Giải quyết trúng điểm đau của khách):** Nếu đánh giá có các khía cạnh tiêu cực (ví dụ: `WATERPROOF`, `FIT_SIZE`), câu trả lời bắt buộc phải đề cập trực tiếp đến hướng xử lý cho đúng vấn đề đó, không trả lời rập khuôn vô cảm.
- **G6 (Chống tự ý hứa hẹn bồi thường tiền mặt):** Không để AI tự ý đưa ra các con số hoàn tiền hoặc tặng tiền cụ thể (`50k`, `100.000đ`, `hoàn 50%`) khi chưa có phê duyệt của quản lý.

<!-- CreBy: MenBoyBMN -->

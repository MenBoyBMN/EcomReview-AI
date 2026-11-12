---
name: academic-report-helper
description: Thiết kế và xuất Báo cáo Điều hành Doanh nghiệp (Excel 6-sheet, HTML/PDF), tài liệu kiến trúc Production, OpenAPI/Swagger và ghi chú phát hành sản phẩm.
---

# Executive Business Reporting & Production Documentation Skill

Kỹ năng này định hướng việc xây dựng hệ thống xuất báo cáo quản trị tự động (`src/ecomreview/reporting.py`, endpoint `GET /api/v1/reports/export`), biên soạn tài liệu kỹ thuật hệ thống Production và quản lý kho tư liệu nền tảng.

## 1. Chuẩn Mực Báo Cáo Điều Hành Doanh Nghiệp (`reporting.py`)
Hệ thống cung cấp tính năng xuất báo cáo quản trị trực tiếp cho chủ doanh nghiệp/quản lý vận hành dưới 2 định dạng:
- **Báo Cáo Excel Chuyên Sâu 6-Sheet (`.xlsx`):**
  1. `Executive_Summary`: Tổng quan KPI, điểm sao trung bình, tỷ lệ hài lòng/phàn nàn và cấu hình hệ thống.
  2. `Aspect_Health_CI`: Bảng sức khỏe 8 khía cạnh kèm khoảng tin cậy bất đối xứng **Wilson 95% CI**.
  3. `Early_Warning_Alerts`: Danh sách cảnh báo sớm các khía cạnh có tỷ lệ phàn nàn tăng đột biến (kiểm định Z-test).
  4. `Action_Plans`: Kế hoạch hành động Marketing & Vận hành đã qua kiểm duyệt `R1–R7`, kèm điểm ưu tiên `priority_score` và trạng thái phê duyệt.
  5. `Validated_Insights`: Các nhận định chuyên sâu đã được kiểm thực số học 100%.
  6. `Negative_Evidence`: Danh sách các đánh giá tiêu cực tiêu biểu nhất cần bộ phận CSKH ưu tiên xử lý.
- **Báo Cáo Điều Hành HTML / In Ấn PDF (`.html`):**
  - Thiết kế trình bày chuyên nghiệp, hỗ trợ in ấn trực tiếp ra PDF từ trình duyệt phục vụ họp giao ban tuần/tháng.

## 2. Tài Liệu Kỹ Thuật Sản Phẩm (Product & API Documentation)
- **Tài liệu API (`OpenAPI 3.1 / Swagger UI`):** Mọi endpoint trong `src/ecomreview/api/main.py` phải có docstring, mô tả tham số và kiểu trả về rõ ràng để hiển thị trực quan tại `/docs`.
- **Tài liệu Vận hành (`README.md`):** Hướng dẫn khởi chạy nhanh bằng Docker Compose 1-click, cấu hình biến môi trường `.env`, xác thực `X-API-Key` và kết nối Frontend.
- **Kho Lưu Trữ Tư Liệu Gốc (`Abount_System/`):** Khi người dùng cần tra cứu hoặc cập nhật các tài liệu nghiên cứu nền tảng ban đầu, truy xuất trực tiếp trong thư mục lưu trữ `Abount_System/`.

<!-- CreBy: MenBoyBMN -->

# EcomReview AI — Standalone Modern SaaS Executive Frontend

Giao diện điều hành trực quan (SPA) dành cho chủ shop và đội ngũ Marketing SME, được xây dựng bằng **React 18 + Vite 6 + Tailwind CSS + Recharts + Lucide Icons**.

Thư mục `frontend/` được thiết kế **hoàn toàn độc lập (Self-Contained & Standalone-Ready)**: bạn có thể copy nguyên thư mục `frontend/` này ra bất kỳ đâu để chạy độc lập ngay trên trình duyệt **mà không bắt buộc phải bật Backend Python**, hoặc kết nối linh hoạt tới bất kỳ máy chủ FastAPI Backend nào.

---

## 3 Chế Độ Vận Hành Linh Hoạt

Bạn có thể chuyển đổi trực tiếp trên giao diện tại menu **Thêm $\rightarrow$ Cài đặt người duyệt & kết nối**:

1. **Tự động (`auto` — Mặc định):**
   - Ưu tiên kết nối tới FastAPI Backend (qua Vite proxy hoặc `VITE_API_BASE_URL`).
   - Nếu Backend chưa bật hoặc không kết nối được, giao diện **tự động chuyển sang Chế độ Độc lập** sử dụng bộ dữ liệu xác thực nội bộ (`/standalone-seed.json`) và lưu mọi thao tác (duyệt kế hoạch, soạn CSKH, nạp đánh giá mới) vào `localStorage`.
2. **Chạy Độc lập hoàn toàn (`standalone`):**
   - Vận hành 100% trên trình duyệt bằng động cơ `standaloneEngine.js`, không gửi bất kỳ request nào tới máy chủ Backend.
3. **Chỉ kết nối máy chủ Backend (`remote`):**
   - Luôn kết nối tới địa chỉ máy chủ Backend đã cấu hình (`API Base URL`).

---

## Hướng Dẫn Khởi Chạy Nhanh (Không Cần Backend)

### Cách 1: Click đúp file `start.bat` (Windows)
Mở thư mục `frontend/` và chạy trực tiếp `start.bat`.

### Cách 2: Chạy bằng dòng lệnh tại thư mục `frontend/`
```powershell
npm install
npm run dev
```
Sau đó mở trình duyệt tại: **`http://localhost:5173/overview`**

### Cách 3: Đóng gói Docker độc lập từ thư mục `frontend/`
```powershell
docker build -t ecomreview-frontend .
docker run -p 5173:80 ecomreview-frontend
```

<!-- CreBy: MenBoyBMN -->

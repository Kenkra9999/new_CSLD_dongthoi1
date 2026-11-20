# Website mô phỏng Đồ án 19 – Đấu giá trực tuyến

Website chạy trên máy, kết nối **PostgreSQL thật** (database riêng `daugia_web`). Mọi thao tác trên web
đều gửi SQL thật vào database. Bảng SQL bên phải trang hiện đúng chuỗi câu lệnh đã gửi, kết quả, lỗi,
mã nguồn hàm (số dòng thật trong `queries.sql`) và giải thích.

## Chạy

Bấm đúp `chay_website.bat`. Lần đầu sẽ tự tạo môi trường Python và cài `flask`, `psycopg`.
Sau đó mở http://127.0.0.1:5019.

Yêu cầu: PostgreSQL chạy ở `localhost`, user `postgres`, mật khẩu đã lưu trong
`%APPDATA%\postgresql\pgpass.conf`. Website tự tạo database `daugia_web` nếu chưa có;
không đụng tới các database khác như `DauGia_check`.

## Các trang

| Trang | Làm gì | SQL |
|---|---|---|
| ① Khởi tạo CSDL | Chạy `DDL_HeThongDauGia.sql` → `seed_data.sql` → `queries.sql`; chạy từng câu của `test_cases.sql` | Nguyên văn từ file của đồ án |
| ② Sàn đấu giá | Xem phiên có ảnh, lọc, trả giá (PA1/PA2), gửi lại cùng UUID, đăng ký, duyệt, đóng phiên, mở phiên mới | Gọi `fn_BaoCaoPhienDauGiaDong`, `fn_TraGia`, `fn_TraGia_Serializable`, `fn_DongPhienDauGia`; INSERT/UPDATE theo DDL cho đăng ký, duyệt, mở phiên |
| ③ Thử nghiệm 2 tab | Hai kết nối thật giữ giao dịch mở: tái hiện lỗi mất cập nhật của phương án 2, có bảng soi khóa trực tiếp | `pg_stat_activity`, `pg_blocking_pids`, `pg_locks` |
| ④ Truy vấn & thống kê | 12 truy vấn khối II của `queries.sql` | Nguyên văn theo khoảng dòng |
| ⑤ Cơ chế vận hành | Giải thích kiến trúc, bảng, luồng trả giá, kiểm soát đồng thời | — |

## Tệp

- `app.py` – máy chủ Flask, toàn bộ API.
- `sqlfile.py` – đọc và tách file `.sql` của đồ án (hiểu thân hàm `$$…$$`), giữ số dòng gốc.
- `explain.py` – lời giải thích và các dòng quan trọng của từng hàm.
- `static/` – giao diện (`index.html`, `app.js`, `style.css`) và ảnh tài sản `img/assets/` kèm `credits.json` (nguồn, tác giả, giấy phép).

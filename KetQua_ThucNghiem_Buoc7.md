# Kết quả thực nghiệm Bước 7 – Bảng so sánh hai giải pháp kiểm soát đồng thời (Minh chứng 5)

Đề bài yêu cầu: *“Đo số yêu cầu thành công, bị từ chối, phải thử lại và thời gian phản hồi”* và *“Có bảng so sánh hai giải pháp kiểm soát đồng thời trên cùng dữ liệu và cấu hình”*. Tài liệu này ghi lại số liệu **đo thật** bằng `thuc_nghiem_buoc7.py`.

## 1. Cùng dữ liệu và cấu hình cho cả hai giải pháp

| Hạng mục | Giá trị |
|---|---|
| Dữ liệu | Nạp mới `DDL_HeThongDauGia.sql` → `seed_data.sql` → `queries.sql`; đo trên **Phiên 1** (giá khởi điểm 5.000.000, bước giá 250.000, giá hiện tại 5.500.000) |
| Đặt lại trước mỗi lượt đo | Xóa lượt thử nghiệm của Phiên 1, đưa giá về 5.500.000 → mọi phương án bắt đầu từ **cùng một trạng thái** |
| Tải | **14 người trả giá đồng thời** (mỗi người 1 kết nối riêng, xuất phát cùng lúc qua barrier), **mỗi người 5 lần** → 70 yêu cầu / phương án |
| Hành vi mỗi người | Đọc giá hiện tại rồi trả thêm đúng 1 bước giá; gửi lại cùng mức giá và cùng mã yêu cầu khi gặp lỗi 40001 (tối đa 10 lần) |
| Số lần lặp | 5 lần chạy độc lập, lấy trung bình |
| Môi trường | PostgreSQL 18.6; Intel Core i7-13620H (16 luồng), RAM 15,7 GB; Windows 11 |

Cách chạy lại: `pip install "psycopg[binary]"` rồi `python thuc_nghiem_buoc7.py` (thêm `--chi-tiet` để xem từng lượt trả giá). Script tự khôi phục dữ liệu sau khi đo.

## 2. Bảng so sánh (trung bình 5 lần chạy)

| Chỉ số | PA1 FOR UPDATE | PA2 READ COMMITTED | PA2 SERIALIZABLE |
|---|---:|---:|---:|
| Số yêu cầu | 70 | 70 | 70 |
| Thành công | 6.6 | 27.2 | 18.6 |
| Bị từ chối | 63.4 | 42.8 | 51.4 |
| Thất bại | 0 | 0 | 0 |
| Số lần thử lại | 0 | 0 | 47.6 |
| TB (ms) | 14.2 | 22.1 | 13.9 |
| p50 (ms) | 8.9 | 28.8 | 14.3 |
| p95 (ms) | 38.2 | 47.9 | 29 |
| Yêu cầu/giây | 313.4 | 195 | 268.2 |
| Đối soát `GiaHienTai` = giá cao nhất lịch sử | NHAT_QUAN 5/5 | NHAT_QUAN 5/5 | NHAT_QUAN 5/5 |

Khoảng dao động giữa 5 lần chạy (nhỏ nhất – lớn nhất):

| Chỉ số | PA1 FOR UPDATE | PA2 READ COMMITTED | PA2 SERIALIZABLE |
|---|---:|---:|---:|
| Thành công | 6 – 8 | 26 – 28 | 15 – 21 |
| Số lần thử lại | 0 – 0 | 0 – 0 | 46 – 52 |
| TB (ms) | 12.2 – 15.9 | 21.3 – 23.3 | 12.5 – 15.7 |
| p95 (ms) | 33.1 – 46 | 45.2 – 50.7 | 25.2 – 31.1 |
| Yêu cầu/giây | 257.5 – 390.8 | 179.7 – 206.4 | 198.4 – 362.3 |

## 3. Số liệu từng lần chạy

| Lần | Phương án | Thành công | Bị từ chối | Thử lại | TB (ms) | p50 (ms) | p95 (ms) | Yêu cầu/giây | Đối soát |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | PA1 FOR UPDATE | 6 | 64 | 0 | 15.9 | 9.5 | 46.0 | 294.5 | NHAT_QUAN |
| 1 | PA2 READ COMMITTED | 27 | 43 | 0 | 23.3 | 29.6 | 50.7 | 200.2 | NHAT_QUAN |
| 1 | PA2 SERIALIZABLE | 15 | 55 | 52 | 15.7 | 15.8 | 31.1 | 278.1 | NHAT_QUAN |
| 2 | PA1 FOR UPDATE | 8 | 62 | 0 | 14.1 | 12.5 | 33.1 | 257.5 | NHAT_QUAN |
| 2 | PA2 READ COMMITTED | 26 | 44 | 0 | 21.8 | 28.7 | 45.2 | 200.4 | NHAT_QUAN |
| 2 | PA2 SERIALIZABLE | 21 | 49 | 46 | 13.6 | 14.7 | 29.0 | 362.3 | NHAT_QUAN |
| 3 | PA1 FOR UPDATE | 6 | 64 | 0 | 15.3 | 7.3 | 43.0 | 390.8 | NHAT_QUAN |
| 3 | PA2 READ COMMITTED | 28 | 42 | 0 | 21.3 | 29.5 | 46.7 | 179.7 | NHAT_QUAN |
| 3 | PA2 SERIALIZABLE | 19 | 51 | 47 | 13.7 | 14.5 | 29.5 | 267.3 | NHAT_QUAN |
| 4 | PA1 FOR UPDATE | 6 | 64 | 0 | 13.3 | 7.7 | 35.7 | 302.4 | NHAT_QUAN |
| 4 | PA2 READ COMMITTED | 28 | 42 | 0 | 21.9 | 26.2 | 49.5 | 206.4 | NHAT_QUAN |
| 4 | PA2 SERIALIZABLE | 20 | 50 | 47 | 13.9 | 13.9 | 30.4 | 234.8 | NHAT_QUAN |
| 5 | PA1 FOR UPDATE | 7 | 63 | 0 | 12.2 | 7.3 | 33.4 | 322.0 | NHAT_QUAN |
| 5 | PA2 READ COMMITTED | 27 | 43 | 0 | 22.3 | 30.0 | 47.3 | 188.1 | NHAT_QUAN |
| 5 | PA2 SERIALIZABLE | 18 | 52 | 46 | 12.5 | 12.8 | 25.2 | 198.4 | NHAT_QUAN |

## 4. Nhận xét (rút ra từ số liệu trên)

1. **Tính đúng:** cả 15/15 lượt đo đều `NHAT_QUAN`: giá lưu trong `PHIENDAUGIA` luôn bằng giá cao nhất trong lịch sử và số lượt được ghi đúng bằng số yêu cầu thành công → không có mất cập nhật ở cả hai giải pháp.
2. **Thử lại:** PA1 không bao giờ phải thử lại (người đến sau xếp hàng chờ khóa dòng rồi đọc giá mới). PA2 ở SERIALIZABLE phải thử lại trung bình 47.6 lần / 70 yêu cầu do lỗi 40001. PA2 ở READ COMMITTED cũng thử lại nhưng **bên trong hàm** (kiểm tra `PhienBan`), nên không đếm được từ phía ứng dụng.
3. **Thành công / bị từ chối:** khi cùng thấy một mức giá và cùng trả thêm 1 bước, mỗi vòng chỉ một người được nhận. PA1 nhận 6.6 / 70 vì mọi người bị xếp hàng ngay từ lúc đọc; PA2 nhận nhiều hơn (27.2 và 18.6) vì không bị chặn ngay lúc đọc: người xong sớm đọc giá mới và đẩy giá lên tiếp trong khi người khác còn đang chờ (thấy rõ khi chạy `--chi-tiet`). Vì vậy cột này phản ánh số mức giá được đẩy lên, **không** phải tỷ lệ đúng/sai. Bị từ chối ở đây là **đúng nghiệp vụ** (giá đã bị người khác vượt).
4. **Thời gian phản hồi:** p95 của PA1 là 38.2 ms (thời gian chờ khóa dồn vào người xếp cuối); PA2 READ COMMITTED có p50 cao nhất (28.8 ms) do phải chờ khóa ở câu UPDATE rồi còn thử lại; PA2 SERIALIZABLE có p95 thấp nhất (29 ms) vì xung đột được báo ngay bằng lỗi 40001 thay vì chờ.
5. **Giới hạn của phép đo:** chạy trên một máy cá nhân, 14 người (toàn bộ người dùng trừ người bán Phiên 1), số liệu dao động giữa các lần (xem bảng khoảng dao động); không đại diện cho tải của hệ thống thật.

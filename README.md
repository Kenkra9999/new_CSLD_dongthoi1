# Đồ án: Thiết kế CSDL Hệ thống Đấu giá Trực tuyến và Kiểm soát Trả giá Đồng thời

> **Môn học:** Cơ sở dữ liệu Nâng cao (Advanced Database Systems)  
> **Đề tài số:** 19  
> **Hệ quản trị CSDL:** PostgreSQL (khuyến nghị phiên bản 15.x trở lên)  
> **Tài liệu tham khảo chính:** Giáo trình *Database System Concepts* (A. Silberschatz, H. F. Korth, S. Sudarshan) & Chuẩn quốc tế ODMG 3.0.

---

## 📌 Giới thiệu & Mục tiêu Đề tài

### 1. Mục tiêu
Xây dựng một hệ thống cơ sở dữ liệu quan hệ hoàn chỉnh quản lý toàn bộ vòng đời đấu giá trực tuyến: người dùng, danh mục đa cấp, tài sản, phiên đấu giá, đăng ký tham gia, lịch sử trả giá và kết quả chốt phiên.

### 2. Câu hỏi nghiên cứu then chốt
> *Làm thế nào để bảo đảm mỗi lượt trả giá được kiểm tra trên trạng thái hợp lệ, không làm mất cập nhật (Lost Update), chống gian lận và không bao giờ tạo ra hai kết quả thắng cho cùng một phiên đấu giá khi có nhiều giao dịch cạnh tranh đồng thời hoặc khi phiên đang trong quá trình đóng?*

---

## 📁 Cấu trúc Thư mục Dự án

```text
Project-CSDL-Nangcao/
├── .gitignore                          # Quy tắc loại trừ file rác và file tạm Office/hệ thống
├── README.md                           # Tài liệu tổng quan và hướng dẫn vận hành chi tiết
├── business_rules.md                   # BƯỚC 1: Đặc tả 6 quy tắc nghiệp vụ đấu giá
├── DDL_HeThongDauGia.sql               # BƯỚC 2: Mã nguồn DDL tạo cấu trúc 11 bảng CSDL
├── seed_data.sql                       # BƯỚC 2 & 4: Bộ dữ liệu giả lập mẫu đầy đủ tính toàn vẹn
├── queries.sql                         # BƯỚC 4 & 5: Định nghĩa 4 Hàm nghiệp vụ & Bộ truy vấn SQL nâng cao
├── test_cases.sql                      # BƯỚC 7: Trọn bộ kịch bản kiểm thử & Thu thập 5 ảnh minh chứng
├── thuc_nghiem_buoc7.py                # BƯỚC 7: Đo định lượng nhiều người trả giá cùng lúc (Minh chứng 5)
├── Chuong5_SoSanh_Transaction.docx     # BƯỚC 5: Báo cáo so sánh chuyên sâu 2 cơ chế Concurrency
└── Chuong6_MoHinhDoiTuong_OQL.docx     # BƯỚC 6: Báo cáo Thiết kế Mô hình Đối tượng (ODL & OQL)
```

---

## ⚙️ Các Điểm Nhấn Kỹ thuật Nổi bật trong CSDL

1. **Chuẩn hóa dữ liệu & phi chuẩn hóa có chủ đích:**
   - Bảng `PHIENDAUGIA` lưu dư `GiaHienTai` và `MaLuotDanDau` để đọc trạng thái và kiểm tra bước giá nhanh. Đây là phi chuẩn hóa có chủ đích: tồn tại phụ thuộc bắc cầu `MaPhien → MaLuotDanDau → GiaHienTai`, nên bảng này **không đạt 3NF**.
   - Cơ chế giữ nhất quán với lịch sử: `GiaHienTai`/`MaLuotDanDau` chỉ được cập nhật trong **cùng giao dịch** với lệnh INSERT lượt trả giá (khóa dòng `FOR UPDATE` ở phương án 1, kiểm tra `PhienBan` ở phương án 2); khóa ngoại trì hoãn `(MaLuotDanDau, MaPhien)`; câu đối soát ở Test Case 6.
2. **Khóa ngoại kép tham chiếu chéo có trì hoãn (`DEFERRABLE INITIALLY DEFERRED`):**
   - Ràng buộc `fk_phiendaugia_luotdandau` ghép cặp `(MaLuotDanDau, MaPhien)` tham chiếu ngược về `LUOTTRAGIA` đảm bảo lượt dẫn đầu bắt buộc phải thuộc về chính phiên đó, loại bỏ hoàn toàn lỗi gán chéo dữ liệu giữa các phiên.
   - Thuộc tính `DEFERRED` giải quyết triệt để phụ thuộc vòng (Circular Dependency) khi ghi nhận lượt trả giá mới trong cùng một transaction.
3. **Cơ chế Idempotency & Unique Constraints:**
   - Cột `MaYeuCau` (`UUID`) độc nhất ngăn chặn người dùng bị trừ tiền hoặc đặt giá trùng lặp do gửi lại request (Network retry).
   - Ràng buộc `UNIQUE (MaPhien, SoTien)` đảm bảo trong cùng một phiên không bao giờ có 2 lượt trả giá ở cùng một mức tiền.
4. **Truy vấn SQL nâng cao & Đệ quy (`WITH RECURSIVE`):**
   - Duyệt và tổng hợp dữ liệu cây danh mục đa cấp (Roll-up dồn tài sản và phiên đấu giá từ danh mục con lên danh mục cha).
   - Hàm báo cáo động (`Dynamic SQL`) với bộ lọc tham số linh hoạt chống SQL Injection.
5. **Kiểm soát đồng thời chuyên sâu (Concurrency Control):**
   - **Phương án 1 (Khóa bi quan):** Sử dụng `SELECT ... FOR UPDATE` trên dòng phiên để tuần tự hóa các yêu cầu trả giá cạnh tranh.
   - **Phương án 2 (Mức cô lập Tuần tự hóa):** Sử dụng mức cô lập `SERIALIZABLE` (Serializable Snapshot Isolation - SSI) kết hợp vòng lặp Retry loop tự động bắt mã lỗi `40001 (serialization_failure)`.
   - Phối hợp nguyên tử giữa giao dịch trả giá và thủ tục đóng phiên `fn_DongPhienDauGia`.

---

## 🚀 Hướng dẫn Cài đặt & Vận hành từ Đầu (Theo đúng thứ tự)

Để đảm bảo CSDL sạch sẽ, đúng ràng buộc khóa ngoại và không bị lỗi transaction, bạn thực hiện lần lượt theo 4 bước sau trong pgAdmin hoặc DBeaver:

### Bước 1: Khởi tạo Cấu trúc Bảng CSDL
* **File thực thi:** [`DDL_HeThongDauGia.sql`](DDL_HeThongDauGia.sql)
* **Thao tác:** Mở file và nhấn **F5 (Execute All)**.
* **Kết quả:** Xóa sạch các bảng cũ (CASCADE) và tạo mới 11 bảng chuẩn, khóa chính, khóa ngoại kép, các ràng buộc `CHECK` (chỉ mục được PostgreSQL tạo ngầm theo `PRIMARY KEY` / `UNIQUE`).

### Bước 2: Nạp Dữ liệu Mẫu (Seed Data)
* **File thực thi:** [`seed_data.sql`](seed_data.sql)
* **Thao tác:** Mở file và nhấn **F5 (Execute All)**.
* **Kết quả:** Nạp dữ liệu hoàn chỉnh cho 11 bảng (15 người dùng, 21 danh mục 3 cấp, 18 tài sản, 20 phiên đấu giá, 50 đăng ký, 45 lượt trả giá lịch sử và kết quả chốt phiên).

### Bước 3: Cài đặt Hàm Nghiệp vụ & Khảo sát Truy vấn Nâng cao
* **File thực thi:** [`queries.sql`](queries.sql)
* **Cấu trúc file chia làm 2 khối rõ ràng:**
  * **Khối I (Ở trên): Cài đặt 4 Hàm & Thủ tục nghiệp vụ:**
    1. `fn_BaoCaoPhienDauGiaDong` (Dynamic SQL lọc phiên đa tiêu chí)
    2. `fn_TraGia` (Khóa bi quan `SELECT ... FOR UPDATE`)
    3. `fn_DongPhienDauGia` (Chốt phiên và xác định người thắng an toàn)
    4. `fn_TraGia_Serializable` (Kiểm soát lạc quan: đọc không khóa, kiểm tra `PhienBan` khi UPDATE; ở READ COMMITTED tự thử lại trong hàm, ở SERIALIZABLE trả mã `40001` để ứng dụng thử lại bằng giao dịch mới)
  * **Khối II (Ở dưới): Bộ truy vấn SQL nâng cao:**
    * Đệ quy cây danh mục (WITH RECURSIVE roll-up).
    * Theo dõi phiên sắp kết thúc trong 1 giờ, người dẫn đầu phiên.
    * Lịch sử giá và mức tăng (Window function `LAG`).
    * Thống kê tỷ lệ thành công toàn hệ thống và theo từng nhánh gốc (`ROLLUP`).
    * Xếp hạng người mua tích cực nhất (`DENSE_RANK`).
    * Kiểm tra toàn vẹn dữ liệu tự động (Data Integrity Audit).
* **Thao tác:**
  * Nhấn **F5 (Execute All)** để cài đặt toàn bộ 4 hàm ở Khối I vào CSDL.
  * Khi muốn xem kết quả câu truy vấn nào ở Khối II, chỉ cần **bôi đen riêng câu lệnh đó và nhấn F5**.

---

## 🧪 Hướng dẫn Chạy Kiểm thử & Lấy Minh chứng (Bước 7)

Toàn bộ các kịch bản kiểm thử độc lập đã được gom vào file **[`test_cases.sql`](test_cases.sql)**. Bạn mở file này trong pgAdmin/DBeaver, bôi đen từng mục và bấm **F5** để lấy 5 ảnh minh chứng bắt buộc cho bài báo cáo:

### 1. Chuẩn bị trước khi test (Bước 0 trong file test)
Chạy lệnh làm mới thời gian để Phiên 1 và Phiên 4 mở thêm 2 giờ:
```sql
UPDATE PHIENDAUGIA 
SET TrangThaiPhien = 'DANG_DIEN_RA',
    ThoiDiemMo = LEAST(ThoiDiemMo, CURRENT_TIMESTAMP - INTERVAL '1 hour'),
    ThoiDiemDong = CURRENT_TIMESTAMP + INTERVAL '2 hours' 
WHERE MaPhien IN (1, 4);
```

### 2. Checklist 5 Minh chứng Báo cáo (Đối chiếu đề cương của Thầy):

| STT | Tên Minh chứng theo Đề cương | Câu lệnh thực thi trong `test_cases.sql` | Kết quả kỳ vọng để chụp ảnh |
| :---: | :--- | :--- | :--- |
| **MC 1** | Mỗi phiên kết thúc có **tối đa một kết quả thắng** theo quy tắc đã công bố. | Mục **5.1 & 5.2** (đóng Phiên 2) và **5.4** (đóng Phiên 4 khi đang có người trả giá, 2 tab). | `KETQUADAUGIA` chỉ có **duy nhất 1 dòng** cho mỗi phiên; ở 5.4 đóng phiên chờ lượt dở dang commit rồi chốt đúng lượt đó, lượt đến sau bị từ chối. |
| **MC 2** | Giá cao nhất lưu riêng (`GiaHienTai`) **luôn khớp với lịch sử trả giá**. | Mục **4.3, 4.4** (đối soát sau tranh chấp 2 tab) và **Test Case 6**. | Bảng đối soát trả về trạng thái **`NHAT_QUAN`** cho tất cả các phiên, không có dòng nào bị lệch. |
| **MC 3** | Yêu cầu gửi lại cùng mã UUID **không tạo lượt trả giá trùng** (Idempotency). | Chạy mục **2.1 rồi chạy lại 2.2** với cùng một mã UUID: `'19000000-0000-4000-8000-000000000101'::uuid`. | Cả 2 lần đều trả về cùng một mã lượt `46`. Bảng `LUOTTRAGIA` đếm được đúng **1 dòng duy nhất**. |
| **MC 4** | Lỗi giữa giao dịch **không để lại dữ liệu dở dang** (Tính nguyên tử Atomicity / Rollback). | Mục **3.4**: INSERT lượt trả giá rồi gây lỗi `SELECT 1/0` trước khi cập nhật giá, sau đó `ROLLBACK`. | Số lượt trả giá trước và sau bằng nhau, `SoLuotDoDang = 0`, `GiaHienTai` không đổi. |
| **MC 5** | Có **bảng so sánh định lượng** hai giải pháp kiểm soát đồng thời trên cùng dữ liệu. | Chạy `python thuc_nghiem_buoc7.py` (mục **7.3**; xem cách chạy bên dưới). | Bảng so sánh PA1 / PA2 (READ COMMITTED) / PA2 (SERIALIZABLE + thử lại): số yêu cầu thành công, bị từ chối, số lần thử lại, thời gian phản hồi TB/p50/p95, đối soát `NHAT_QUAN`. |

### 3. Đo định lượng nhiều người trả giá cùng lúc (Minh chứng 5)
```bash
pip install "psycopg[binary]"          # cài 1 lần
python thuc_nghiem_buoc7.py --chi-tiet   # chạy chậm, in từng lượt trả giá, nhấn Enter qua từng bước
python thuc_nghiem_buoc7.py              # đo thật (14 người x 5 lần) và in bảng so sánh
```
* Mặc định kết nối `host=localhost user=postgres dbname=DauGia_check`; có thể truyền chuỗi kết nối khác làm tham số.
* Script đặt lại Phiên 1 trước mỗi lượt đo (cùng dữ liệu, cùng cấu hình cho cả 2 phương án) và khôi phục dữ liệu khi kết thúc.

---

## 🛠 Xử lý Sự cố Thường gặp (Troubleshooting)

### Lỗi: `ERROR: current transaction is aborted, commands ignored until end of transaction block (SQL state: 25P02)`
* **Nguyên nhân:** Một câu lệnh trước đó bị lỗi hoặc vi phạm điều kiện nghiệp vụ (`RAISE EXCEPTION`), khiến session giao dịch hiện tại bị treo dở.
* **Cách khắc phục:** 
  1. Gõ `ROLLBACK;` rồi bấm **F5** để giải phóng kết nối.
  2. Hoặc đóng tab Query Tool hiện tại và mở một tab Query Tool mới toanh.

### Lỗi: `ERROR: Thời điểm trả giá nằm ngoài khung giờ nhận lượt`
* **Nguyên nhân:** Dữ liệu mẫu nạp từ trước đó đã quá thời điểm đóng của phiên.
* **Cách khắc phục:** Chạy đoạn lệnh **Bước 0** trong file `test_cases.sql` để gia hạn thêm giờ mở cho phiên.

---

## 📚 Tóm tắt 7 Bước Đề tài theo Đề cương

1. **Bước 1 - Đặc tả quy tắc đấu giá:** Hoàn thiện 6 quy tắc nghiệp vụ tại [`business_rules.md`](business_rules.md).
2. **Bước 2 - Thiết kế mô hình EER:** Sơ đồ thực thể liên kết mở rộng tổng quát hóa/chuyên biệt hóa và chuyển dịch thành [`DDL_HeThongDauGia.sql`](DDL_HeThongDauGia.sql).
3. **Bước 3 - Phân tích phụ thuộc hàm & Chuẩn hóa:** Xác định 16 FD, tìm phủ tối tiểu $F_{min}$ và chứng minh chuẩn 3NF/BCNF.
4. **Bước 4 - Xây dựng truy vấn SQL nâng cao:** Đệ quy cây phân cấp, Dynamic SQL, xếp hạng phân tích số liệu tại [`queries.sql`](queries.sql).
5. **Bước 5 - Thiết kế và so sánh Transaction:** Hoàn thành 2 giải pháp kiểm soát đồng thời tại [`queries.sql`](queries.sql) và biên soạn tài liệu lý thuyết tại [`Chuong5_SoSanh_Transaction.docx`](Chuong5_SoSanh_Transaction.docx).
6. **Bước 6 - Thiết kế mô hình đối tượng và OQL:** Đặc tả ODL 5 lớp và 3 truy vấn OQL chuẩn ODMG 3.0 tại [`Chuong6_MoHinhDoiTuong_OQL.docx`](Chuong6_MoHinhDoiTuong_OQL.docx).
7. **Bước 7 - Thực nghiệm và phân tích kết quả:** Bộ kịch bản kiểm thử độc lập tại [`test_cases.sql`](test_cases.sql) (kịch bản 2 tab cho tranh chấp đồng thời) và [`thuc_nghiem_buoc7.py`](thuc_nghiem_buoc7.py) (đo định lượng), thu thập trọn bộ 5 minh chứng.

---
*Dự án phục vụ học tập và nghiên cứu môn Cơ sở dữ liệu Nâng cao.*

-- ĐỒ ÁN 19: HỆ THỐNG ĐẤU GIÁ TRỰC TUYẾN VÀ KIỂM SOÁT TRẢ GIÁ ĐỒNG THỜI
-- TÀI LIỆU KỊCH BẢN KIỂM THỬ TOÀN DIỆN (TEST CASES & SCRIPTS - BƯỚC 7)

-- Hướng dẫn:
-- 1. Đảm bảo đã chạy lần lượt: DDL_HeThongDauGia.sql -> seed_data.sql -> queries.sql.
-- 2. Mở file này trong pgAdmin/DBeaver, bôi đen và nhấn F5 từng kịch bản để quan sát kết quả.

-- =============================================================================
-- BƯỚC 0: CHUẨN BỊ MÔI TRƯỜNG & GIA HẠN THỜI GIAN ĐÓNG PHIÊN ĐẤU GIÁ
-- Mục đích: Đảm bảo Phiên 1 và Phiên 4 luôn ở trạng thái 'DANG_DIEN_RA' 
-- và thời gian đóng kéo dài thêm 2 giờ kể từ thời điểm test hiện tại.
-- Lưu ý: Giữ nguyên ThoiDiemMo gốc bằng LEAST(...) để các lượt trả giá lịch sử 
-- trong seed_data không bị rơi ra ngoài khung giờ mở phiên.
-- =============================================================================

UPDATE PHIENDAUGIA 
SET TrangThaiPhien = 'DANG_DIEN_RA',
    ThoiDiemMo = LEAST(ThoiDiemMo, CURRENT_TIMESTAMP - INTERVAL '1 hour'),
    ThoiDiemDong = CURRENT_TIMESTAMP + INTERVAL '2 hours' 
WHERE MaPhien IN (1, 4);

-- Kiểm tra trạng thái các phiên đang mở:
SELECT MaPhien, GiaKhoiDiem, BuocGia, GiaHienTai, MaLuotDanDau, PhienBan, ThoiDiemMo, ThoiDiemDong, TrangThaiPhien
FROM PHIENDAUGIA
WHERE TrangThaiPhien = 'DANG_DIEN_RA'
ORDER BY MaPhien;


-- =============================================================================
-- TEST CASE 1: KIỂM THỬ HÀM BÁO CÁO CÓ BỘ LỌC ĐỘNG (Dynamic SQL)
-- =============================================================================
-- 1.1. Gọi báo cáo mặc định (không truyền tham số -> trả về tất cả các phiên)
SELECT * FROM fn_BaoCaoPhienDauGiaDong();

-- 1.2. Lọc tất cả phiên thuộc nhánh Danh mục 1 ("Thiết bị công nghệ & Điện tử" và các cấp con)
SELECT * FROM fn_BaoCaoPhienDauGiaDong(p_MaDanhMucGoc => 1);

-- 1.3. Lọc theo loại tài sản 'DOSUUTAM' và khoảng giá từ 1,000,000 đến 50,000,000
SELECT * FROM fn_BaoCaoPhienDauGiaDong(
    p_LoaiTaiSan => 'DOSUUTAM',
    p_GiaTu      => 1000000,
    p_GiaDen     => 50000000
);

-- 1.4. Lọc tìm kiếm gần đúng theo từ khóa tên tài sản
SELECT * FROM fn_BaoCaoPhienDauGiaDong(p_TuKhoa => 'macbook');


-- =============================================================================
-- TEST CASE 2: KIỂM THỬ HÀM TRẢ GIÁ KHÓA BI QUAN & YÊU CẦU GỬI LẠI (MINH CHỨNG 3)
-- Kịch bản đề bài: "Yêu cầu được gửi lại -> Yêu cầu gửi lại không tạo lượt trả giá trùng"
-- =============================================================================
-- 2.1. Trả giá hợp lệ cho Phiên 1 (Người dùng 8 đã duyệt đăng ký, giá khởi điểm 5tr, bước 250k, giá hiện tại 5.5tr)
-- Giá trả hợp lệ tiếp theo: 5,750,000
SELECT fn_TraGia(
    1, 
    8, 
    5750000, 
    '19000000-0000-4000-8000-000000000101'::uuid
);

-- 2.1.1. Xem chi tiết lượt trả giá vừa tạo:
SELECT * FROM LUOTTRAGIA WHERE MaYeuCau = '19000000-0000-4000-8000-000000000101'::uuid;

-- 2.2. Kiểm thử tính Idempotency (Gửi lại y hệt cùng mã UUID -> Không tạo lượt mới, trả về đúng mã lượt cũ = 46)
SELECT fn_TraGia(
    1, 
    8, 
    5750000, 
    '19000000-0000-4000-8000-000000000101'::uuid
);

-- Đếm số lượng bản ghi theo MaYeuCau để chứng minh không bị nhân đôi (Kết quả = 1):
SELECT COUNT(*) AS SoLuongBanGhi, MIN(MaLuotTraGia) AS MaLuotDuyNhat
FROM LUOTTRAGIA 
WHERE MaYeuCau = '19000000-0000-4000-8000-000000000101'::uuid;

-- 2.3. Kiểm tra nhật ký và giá hiện tại của Phiên 1 sau khi trả giá:
SELECT MaPhien, GiaHienTai, MaLuotDanDau, PhienBan 
FROM PHIENDAUGIA 
WHERE MaPhien = 1;

SELECT * FROM NHATKYTHAYDOI 
WHERE MaPhien = 1 
ORDER BY ThoiDiemGhi DESC LIMIT 3;


-- =============================================================================
-- TEST CASE 3: KIỂM THỬ RÀNG BUỘC NGHIỆP VỤ & LỖI GIỮA GIAO DỊCH (MINH CHỨNG 4)
-- Kịch bản đề bài: "Lỗi xảy ra sau khi ghi lượt trả nhưng trước khi cập nhật giá hiện tại.
--                   Lỗi giữa giao dịch không để lại dữ liệu dở dang."
-- =============================================================================
-- 3.1. Ca vi phạm 1: Người bán tự trả giá cho tài sản của mình (Phiên 1 do Người dùng 1 bán)
-- Kỳ vọng: Bị chặn với thông báo lỗi 'Người bán không được trả giá tài sản của mình'
SELECT fn_TraGia(1, 1, 6000000, gen_random_uuid());

-- 3.2. Ca vi phạm 2: Người dùng chưa có đăng ký được duyệt (Người dùng 12 đang ở trạng thái 'CHO_DUYET')
-- Kỳ vọng: Bị chặn với thông báo lỗi 'Người trả giá chưa có đăng ký được duyệt cho phiên này'
SELECT fn_TraGia(1, 12, 6000000, gen_random_uuid());

-- 3.3. Ca vi phạm 3: Trả giá sai lưới bước giá (Bước giá phiên 1 là 250,000 nhưng trả 5,800,000)
-- Kỳ vọng: Bị chặn do vi phạm điều kiện bước giá
SELECT fn_TraGia(1, 8, 5800000, gen_random_uuid());

-- -----------------------------------------------------------------------------
-- 3.4. MINH CHỨNG 4 (CHUẨN ĐỀ BÀI): LỖI XẢY RA SAU KHI GHI LƯỢT TRẢ NHƯNG TRƯỚC KHI CẬP NHẬT GIÁ HIỆN TẠI
-- Cách 1 (Chạy từng lệnh để quan sát Rollback trực tiếp):
--   Bước A: Xem số lượt trả giá hiện tại của Phiên 1 trước khi xảy ra sự cố
SELECT COUNT(*) AS SoLuotTruocSuCo, MAX(SoTien) AS GiaCaoNhatTruocSuCo
FROM LUOTTRAGIA WHERE MaPhien = 1;

--   Bước B: Mở giao dịch, INSERT thành công vào LUOTTRAGIA nhưng gặp sự cố trước khi UPDATE PHIENDAUGIA
BEGIN;
INSERT INTO LUOTTRAGIA (MaPhien, MaNguoiTraGia, SoTien, MaYeuCau, ThoiDiemChapNhan)
VALUES (1, 7, 9500000, '19000000-0000-4000-8000-000000000999'::uuid, clock_timestamp());

-- Giả lập sự cố nghiêm trọng xảy ra NGAY SAU KHI ghi LUOTTRAGIA nhưng TRƯỚC KHI cập nhật GiaHienTai:
SELECT 1 / 0;
-- (Sau khi pgAdmin báo lỗi division by zero, bôi đen dòng ROLLBACK; bên dưới và nhấn F5)
ROLLBACK;

--   Bước C: Kiểm tra lại sau sự cố -> Lượt trả giá 9,500,000 đã bị hủy hoàn toàn, không còn dữ liệu dở dang!
SELECT COUNT(*) AS SoLuotSauRollback,
       COUNT(*) FILTER (WHERE MaYeuCau = '19000000-0000-4000-8000-000000000999'::uuid) AS SoLuotDoDang,
       (SELECT GiaHienTai FROM PHIENDAUGIA WHERE MaPhien = 1) AS GiaHienTaiPhien1
FROM LUOTTRAGIA WHERE MaPhien = 1;


-- =============================================================================
-- TEST CASE 4: KIỂM THỬ PHƯƠNG ÁN 2 (SERIALIZABLE / OCC RETRY) & NHIỀU NGƯỜI TRẢ GIÁ CÙNG LÚC
-- Kịch bản đề bài: "Nhiều người trả giá cùng lúc" (Concurrent Bidding)
-- =============================================================================
-- 4.1. Trả giá mức hợp lệ tiếp theo cho Phiên 1 (6,000,000) bằng fn_TraGia_Serializable
SELECT fn_TraGia_Serializable(
    1, 
    7,                          -- Người dùng 7 (đã được duyệt đăng ký phiên 1)
    6000000,                    -- Giá trả hợp lệ tiếp theo (5,750,000 + 250,000)
    '19000000-0000-4000-8000-000000000102'::uuid
);

-- Kiểm tra lại thông tin Phiên 1 sau giao dịch (GiaHienTai = 6,000,000, PhienBan = 5):
SELECT MaPhien, GiaHienTai, MaLuotDanDau, PhienBan 
FROM PHIENDAUGIA 
WHERE MaPhien = 1;

-- -----------------------------------------------------------------------------
-- 4.2. MINH HỌA QUY TẮC CÙNG MỨC GIÁ (CHẠY TUẦN TỰ TRONG 1 GIAO DỊCH – KHÔNG PHẢI ĐỒNG THỜI)
-- Người dùng 8 và Người dùng 7 cùng đặt 6,250,000 (giá hiện tại 6,000,000). Hai lời gọi chạy
-- LẦN LƯỢT trong cùng một giao dịch nên người thứ hai bị từ chối ở bước kiểm tra giá tối thiểu.
-- Kịch bản tranh chấp ĐỒNG THỜI thật xem mục 4.3 và 4.4 (2 tab).
-- Cách chạy: Bôi đen từ BEGIN đến ROLLBACK bên dưới và nhấn F5 (không làm thay đổi dữ liệu).
-- -----------------------------------------------------------------------------
BEGIN;

CREATE TEMP TABLE kq_cung_muc_gia (
    ThuTuXuLy INT,
    NguoiThamGia TEXT,
    MucGiaDat NUMERIC(16,2),
    TrangThaiKetQua TEXT,
    MaLuotHoacThongBao TEXT,
    GiaHienTaiSauXuLy NUMERIC(16,2),
    PhienBanSauXuLy INT
) ON COMMIT DROP;

DO $$
DECLARE
    v_ma_luot BIGINT;
    v_gia NUMERIC;
    v_pb INT;
BEGIN
    -- Lời gọi 1 (Người dùng 8 đặt mức 6,250,000)
    v_ma_luot := fn_TraGia_Serializable(1, 8, 6250000, gen_random_uuid());
    SELECT GiaHienTai, PhienBan INTO v_gia, v_pb FROM PHIENDAUGIA WHERE MaPhien = 1;
    INSERT INTO kq_cung_muc_gia VALUES (
        1, 'Người dùng 8 (Bùi Quốc Nam)', 6250000, 'THANH_CONG',
        'Chấp nhận lượt trả giá #' || v_ma_luot, v_gia, v_pb
    );

    -- Lời gọi 2 (Người dùng 7 cũng đặt 6,250,000) -> bị từ chối vì giá tối thiểu lúc này là 6,500,000
    BEGIN
        v_ma_luot := fn_TraGia_Serializable(1, 7, 6250000, gen_random_uuid());
    EXCEPTION WHEN OTHERS THEN
        SELECT GiaHienTai, PhienBan INTO v_gia, v_pb FROM PHIENDAUGIA WHERE MaPhien = 1;
        INSERT INTO kq_cung_muc_gia VALUES (
            2, 'Người dùng 7 (Đỗ Mỹ Linh)', 6250000, 'BI_TU_CHOI',
            SQLERRM, v_gia, v_pb
        );
    END;
END $$;

SELECT * FROM kq_cung_muc_gia ORDER BY ThuTuXuLy;

ROLLBACK;

-- -----------------------------------------------------------------------------
-- 4.3. NHIỀU NGƯỜI TRẢ GIÁ CÙNG LÚC – PHƯƠNG ÁN 2 Ở READ COMMITTED (MẶC ĐỊNH) – CHẠY 2 TAB
-- Mở 2 tab Query Tool cùng CSDL: TAB A và TAB B. Bôi đen TỪNG bước rồi F5. (Giá hiện tại: 6,000,000)
-- -----------------------------------------------------------------------------
-- Bước A (TAB A): Người dùng 8 đặt 6,500,000 nhưng CHƯA COMMIT
BEGIN;
SELECT fn_TraGia_Serializable(1, 8, 6500000, gen_random_uuid()) AS luot_A;

-- Bước B (TAB B): Người dùng 7 vẫn thấy giá cũ 6,000,000, đặt 6,250,000 -> TAB B ĐỨNG CHỜ ở câu UPDATE
SELECT fn_TraGia_Serializable(1, 7, 6250000, gen_random_uuid()) AS luot_B;

-- Bước C (TAB A): COMMIT
COMMIT;
-- Kỳ vọng ở TAB B: UPDATE ... WHERE PhienBan = (phiên bản lúc đọc) không khớp -> hàm tự thử lại,
-- đọc giá mới 6,500,000 và TỪ CHỐI: "Giá trả phải từ 6750000.00 và đúng lưới bước giá 250000.00".

-- Bước D: Đối soát Phiên 1 -> NHAT_QUAN (giá lưu = giá cao nhất trong lịch sử = 6,500,000)
SELECT p.GiaHienTai, p.MaLuotDanDau,
       (SELECT MAX(SoTien) FROM LUOTTRAGIA WHERE MaPhien = 1) AS GiaCaoNhatLichSu,
       CASE WHEN p.GiaHienTai = (SELECT MAX(SoTien) FROM LUOTTRAGIA WHERE MaPhien = 1)
            THEN 'NHAT_QUAN' ELSE 'SAI_LECH' END AS DoiSoat
FROM PHIENDAUGIA p WHERE p.MaPhien = 1;

-- -----------------------------------------------------------------------------
-- 4.4. PHƯƠNG ÁN 2 Ở MỨC CÔ LẬP SERIALIZABLE CÓ XỬ LÝ THỬ LẠI (ỨNG DỤNG THỬ LẠI GIAO DỊCH MỚI) – 2 TAB
-- Ở SERIALIZABLE, hàm ném mã 40001 ra ngoài; người gọi phải ROLLBACK và chạy lại bằng GIAO DỊCH MỚI
-- (thử lại trong cùng giao dịch vẫn dùng ảnh dữ liệu cũ nên sẽ lỗi lại). (Giá hiện tại: 6,500,000)
-- -----------------------------------------------------------------------------
-- Bước A (TAB A): Người dùng 8 đặt 6,750,000 trong giao dịch SERIALIZABLE, CHƯA COMMIT
BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT current_setting('transaction_isolation') AS muc_co_lap,
       fn_TraGia_Serializable(1, 8, 6750000, gen_random_uuid()) AS luot_A;

-- Bước B (TAB B): Người dùng 7 đặt 7,000,000 (vẫn hợp lệ sau khi A thắng) -> TAB B ĐỨNG CHỜ
BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT current_setting('transaction_isolation') AS muc_co_lap,
       fn_TraGia_Serializable(1, 7, 7000000, gen_random_uuid()) AS luot_B;

-- Bước C (TAB A): COMMIT
COMMIT;
-- Kỳ vọng ở TAB B: ERROR ... SQL state: 40001 (xung đột tuần tự hóa) -> giao dịch của B đã hỏng.

-- Bước D (TAB B): Ứng dụng xử lý thử lại = hủy giao dịch hỏng ...
ROLLBACK;

-- Bước E (TAB B): ... rồi chạy lại bằng GIAO DỊCH MỚI (ảnh dữ liệu mới thấy giá 6,750,000) -> THÀNH CÔNG
BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT fn_TraGia_Serializable(1, 7, 7000000, gen_random_uuid()) AS luot_B_thu_lai;
COMMIT;

-- Bước F: Đối soát Phiên 1 -> NHAT_QUAN (giá lưu = giá cao nhất trong lịch sử = 7,000,000)
SELECT p.GiaHienTai, p.MaLuotDanDau,
       (SELECT MAX(SoTien) FROM LUOTTRAGIA WHERE MaPhien = 1) AS GiaCaoNhatLichSu,
       CASE WHEN p.GiaHienTai = (SELECT MAX(SoTien) FROM LUOTTRAGIA WHERE MaPhien = 1)
            THEN 'NHAT_QUAN' ELSE 'SAI_LECH' END AS DoiSoat
FROM PHIENDAUGIA p WHERE p.MaPhien = 1;
-- Thử lại tự động nhiều người cùng lúc ở mức SERIALIZABLE: xem thuc_nghiem_buoc7.py (mục 7.3).


-- =============================================================================
-- TEST CASE 5: KIỂM THỬ ĐÓNG PHIÊN & TRẢ GIÁ CẠNH TRANH VỚI ĐÓNG PHIÊN (MINH CHỨNG 1)
-- Kịch bản đề bài: "Trả giá cạnh tranh với đóng phiên; 
--                   Mỗi phiên kết thúc có tối đa một kết quả thắng theo quy tắc đã công bố."
-- =============================================================================
-- 5.1. Đóng Phiên 2 (Phiên này đã hết thời gian và có 2 lượt trả giá: 2,000,000 và 2,100,000)
SELECT fn_DongPhienDauGia(2);

-- 5.2. Kiểm tra kết quả chốt phiên trong KETQUADAUGIA (Chốt duy nhất 1 dòng, MaLuotThang = 5, GiaThang = 2,100,000):
SELECT k.MaPhien, k.MaLuotThang, k.ThoiDiemChot, l.SoTien AS GiaThang, nd.HoTen AS NguoiThang
FROM KETQUADAUGIA k
LEFT JOIN LUOTTRAGIA l ON k.MaLuotThang = l.MaLuotTraGia AND k.MaPhien = l.MaPhien
LEFT JOIN NGUOIDUNG nd ON l.MaNguoiTraGia = nd.MaNguoiDung
WHERE k.MaPhien = 2;

-- 5.3. Kiểm tra trạng thái Phiên 2 sau khi đóng:
SELECT MaPhien, TrangThaiPhien, GiaHienTai, MaLuotDanDau, PhienBan
FROM PHIENDAUGIA 
WHERE MaPhien = 2;

-- -----------------------------------------------------------------------------
-- 5.4. KỊCH BẢN THỰC NGHIỆM: TRẢ GIÁ CẠNH TRANH VỚI ĐÓNG PHIÊN (TRÊN PHIÊN 4) – CHẠY 2 TAB
-- Mục đích: Chứng minh giao dịch đóng phiên phối hợp với giao dịch trả giá: đóng phiên phải
--           CHỜ lượt trả giá đang dở dang commit xong rồi mới chốt (lượt đó được tính),
--           và mọi lượt trả giá đến sau khi phiên đã đóng đều bị từ chối.
-- Mở 2 tab Query Tool cùng CSDL: TAB A và TAB B. Bôi đen TỪNG bước rồi F5.
--
-- Bước A (TAB A): Cho Phiên 4 hết giờ sau 30 giây (giá khởi điểm 3,000,000)
UPDATE PHIENDAUGIA SET ThoiDiemDong = clock_timestamp() + INTERVAL '30 seconds' WHERE MaPhien = 4;

-- Bước B (TAB A, NGAY sau bước A): Người dùng 7 trả giá hợp lệ nhưng CHƯA COMMIT (đang giữ khóa dòng Phiên 4)
BEGIN;
SELECT fn_TraGia(4, 7, 3000000, '19000000-0000-4000-8000-000000000104'::uuid) AS luot_A;

-- Bước C (TAB B, sau khi ĐÃ QUA 30 GIÂY): tiến trình đóng phiên kích hoạt -> TAB B ĐỨNG CHỜ khóa của TAB A
SELECT fn_DongPhienDauGia(4) AS luot_thang;

-- Bước D (TAB A): COMMIT -> TAB B chạy tiếp và trả về đúng mã lượt luot_A (lượt của người dùng 7 được tính)
COMMIT;

-- Bước E (TAB A): Người dùng 8 trả giá cạnh tranh (3,200,000) sau khi phiên đã đóng
-- Kỳ vọng: Bị chặn với lỗi "ERROR: Phiên không nhận trả giá" (phiên đã chuyển sang DA_DONG)
SELECT fn_TraGia(4, 8, 3200000, gen_random_uuid());

-- Bước F: Phiên 4 chỉ có duy nhất 1 kết quả thắng của Người dùng 7 (3,000,000)
SELECT k.MaPhien, p.TrangThaiPhien, k.MaLuotThang, l.SoTien AS GiaThang, nd.HoTen AS NguoiThang
FROM KETQUADAUGIA k
JOIN PHIENDAUGIA p ON p.MaPhien = k.MaPhien
LEFT JOIN LUOTTRAGIA l ON l.MaLuotTraGia = k.MaLuotThang AND l.MaPhien = k.MaPhien
LEFT JOIN NGUOIDUNG nd ON nd.MaNguoiDung = l.MaNguoiTraGia
WHERE k.MaPhien = 4;
-- (Nếu chỉ dùng 1 tab: chạy A -> B -> D -> đợi 30 giây -> C -> E -> F; kết quả giống nhưng không thấy bước chờ khóa.)


-- =============================================================================
-- TEST CASE 6: KIỂM TRA TÍNH NHẤT QUÁN TOÀN BỘ CƠ SỞ DỮ LIỆU (MINH CHỨNG 2)
-- Kịch bản đề bài: "Giá cao nhất lưu riêng luôn khớp với lịch sử trả giá được chấp nhận."
-- =============================================================================
-- 6.1. Truy vấn đối soát: Hiển thị trạng thái so khớp của toàn bộ 20 phiên đấu giá (Tất cả đều NHAT_QUAN)
SELECT p.MaPhien, p.TrangThaiPhien, p.GiaHienTai, MAX(l.SoTien) AS GiaCaoNhatTrongLichSu,
       CASE 
           WHEN p.GiaHienTai IS NOT DISTINCT FROM MAX(l.SoTien) THEN 'NHAT_QUAN'
           ELSE 'SAI_LECH'
       END AS KetQuaDoiSoat
FROM PHIENDAUGIA p
LEFT JOIN LUOTTRAGIA l ON p.MaPhien = l.MaPhien
GROUP BY p.MaPhien, p.TrangThaiPhien, p.GiaHienTai
ORDER BY p.MaPhien;


-- =============================================================================
-- TEST CASE 7: ĐO LƯỜNG VÀ SO SÁNH ĐỊNH LƯỢNG 2 PHƯƠNG ÁN TRÊN CÙNG DỮ LIỆU (MINH CHỨNG 5)
-- Kịch bản đề bài: "Đo số yêu cầu thành công, bị từ chối, phải thử lại và thời gian phản hồi.
--                  Có bảng so sánh hai giải pháp kiểm soát đồng thời trên cùng dữ liệu và cấu hình."
-- =============================================================================

-- 7.1. Thời gian MỘT lần gọi riêng lẻ (không có tranh chấp) của Phương án 1.
--      Bọc BEGIN ... ROLLBACK để KHÔNG ghi dữ liệu; giá trả = giá hiện tại + 1 bước giá nên luôn hợp lệ.
BEGIN;
EXPLAIN ANALYZE
SELECT fn_TraGia(1, 8, (SELECT GiaHienTai + BuocGia FROM PHIENDAUGIA WHERE MaPhien = 1), gen_random_uuid());
ROLLBACK;

-- 7.2. Thời gian MỘT lần gọi riêng lẻ của Phương án 2 (cùng trạng thái dữ liệu với 7.1):
BEGIN;
EXPLAIN ANALYZE
SELECT fn_TraGia_Serializable(1, 8, (SELECT GiaHienTai + BuocGia FROM PHIENDAUGIA WHERE MaPhien = 1), gen_random_uuid());
ROLLBACK;

-- -----------------------------------------------------------------------------
-- 7.3. BẢNG SO SÁNH ĐỊNH LƯỢNG KHI NHIỀU NGƯỜI TRẢ GIÁ CÙNG LÚC (MINH CHỨNG 5)
-- Một phiên làm việc SQL chỉ chạy được 1 giao dịch tại một thời điểm, nên KHÔNG đo được
-- tranh chấp thật bằng một khối lệnh trong file này. Số liệu lấy từ script đi kèm
-- thuc_nghiem_buoc7.py: N người trả giá CÙNG LÚC (mỗi người 1 kết nối riêng) vào Phiên 1,
-- chạy lần lượt PA1, PA2 (READ COMMITTED), PA2 (SERIALIZABLE + ứng dụng thử lại khi gặp 40001),
-- mỗi lượt đo đều đặt lại Phiên 1 về cùng trạng thái, rồi KHÔI PHỤC dữ liệu khi xong.
--
--   pip install "psycopg[binary]"                 (cài 1 lần)
--   python thuc_nghiem_buoc7.py --chi-tiet        (xem từng lượt trả giá, nhấn Enter qua từng bước)
--   python thuc_nghiem_buoc7.py                   (đo thật: 14 người x 5 lần -> in BẢNG SO SÁNH)
--   Chuỗi kết nối khác: python thuc_nghiem_buoc7.py "host=localhost user=postgres password=... dbname=..."
--
-- Bảng in ra gồm: Số yêu cầu, Thành công, Bị từ chối, Thất bại, Số lần thử lại, TB/p50/p95 (ms),
-- Yêu cầu/giây và Đối soát (NHAT_QUAN/SAI_LECH). Nên chạy 3-5 lần và lấy trung bình cho báo cáo.
-- -----------------------------------------------------------------------------

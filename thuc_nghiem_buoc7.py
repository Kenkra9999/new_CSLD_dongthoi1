# THỰC NGHIỆM BƯỚC 7 – NHIỀU NGƯỜI TRẢ GIÁ CÙNG LÚC, SO SÁNH 2 PHƯƠNG ÁN
# Cài 1 lần:  pip install "psycopg[binary]"
# Chạy:
#   python thuc_nghiem_buoc7.py --chi-tiet     -> chạy CHẬM, in từng lượt trả giá, dừng chờ Enter sau mỗi bước
#                                                (mặc định 4 người x 2 lần, dễ đọc)
#   python thuc_nghiem_buoc7.py                -> đo THẬT để lấy số liệu báo cáo (mặc định 14 người x 5 lần)
# Tùy chọn thêm (không bắt buộc):
#   - số người, số lần:   python thuc_nghiem_buoc7.py 14 10
#   - chuỗi kết nối khác: python thuc_nghiem_buoc7.py "host=localhost user=postgres password=MAT_KHAU dbname=DauGia_check"
# Script tự đặt lại phiên 1 trước mỗi lượt đo và KHÔI PHỤC dữ liệu khi kết thúc.
import sys, time, uuid, random, threading, statistics
import psycopg
from psycopg import errors

ARGS = sys.argv[1:]
CHI_TIET = "--chi-tiet" in ARGS
DSN = next((a for a in ARGS if "=" in a), "host=localhost user=postgres dbname=DauGia_check")
SO = [int(a) for a in ARGS if a.isdigit()]
SO_LUONG = SO[0] if len(SO) > 0 else (4 if CHI_TIET else 20)   # số người trả giá đồng thời
SO_LAN = SO[1] if len(SO) > 1 else (2 if CHI_TIET else 5)      # mỗi người trả mấy lần
PHIEN, MAX_THU_LAI = 1, 10
KHOA_IN = threading.Lock()

RESET = """
DELETE FROM NHATKYTHAYDOI WHERE MaPhien = 1 AND HanhDong = 'CHAP_NHAN_TRA_GIA' AND (ChiTiet->>'MaLuotTraGia')::BIGINT > 45;
DELETE FROM LUOTTRAGIA WHERE MaPhien = 1 AND MaLuotTraGia > 45;
UPDATE PHIENDAUGIA SET TrangThaiPhien = 'DANG_DIEN_RA',
       ThoiDiemMo = LEAST(ThoiDiemMo, now() - interval '1 hour'), ThoiDiemDong = now() + interval '2 hours',
       (GiaHienTai, MaLuotDanDau) = (SELECT SoTien, MaLuotTraGia FROM LUOTTRAGIA WHERE MaPhien = 1
                                     ORDER BY SoTien DESC, MaLuotTraGia LIMIT 1)
WHERE MaPhien = 1;
SELECT setval(pg_get_serial_sequence('luottragia', 'maluottragia'), (SELECT MAX(MaLuotTraGia) FROM LUOTTRAGIA));
"""
DOI_SOAT = """
SELECT p.GiaHienTai, (SELECT MAX(SoTien) FROM LUOTTRAGIA WHERE MaPhien = 1),
       p.GiaHienTai = (SELECT MAX(SoTien) FROM LUOTTRAGIA WHERE MaPhien = 1)
   AND p.GiaHienTai = (SELECT SoTien FROM LUOTTRAGIA WHERE MaLuotTraGia = p.MaLuotDanDau),
       (SELECT COUNT(*) FROM LUOTTRAGIA WHERE MaPhien = 1 AND MaLuotTraGia > 45)
FROM PHIENDAUGIA p WHERE p.MaPhien = 1"""
TRANG_THAI = """
SELECT p.GiaHienTai, p.BuocGia,
       (SELECT string_agg(MaNguoiDung || ':' || TrangThaiDangKy, ', ' ORDER BY MaNguoiDung) FROM DANGKY WHERE MaPhien = 1),
       (SELECT COUNT(*) FROM LUOTTRAGIA WHERE MaPhien = 1 AND MaLuotTraGia > 45)
FROM PHIENDAUGIA p WHERE p.MaPhien = 1"""

def tien(x): return f"{int(x):,}".replace(",", ".")
def in_(*a):
    with KHOA_IN: print(*a, flush=True)
def tieu_de(s): print(f"\n{'=' * 78}\n {s}\n{'=' * 78}", flush=True)
def dung_lai():
    if CHI_TIET: input("\n   >>> Nhấn Enter để sang bước tiếp theo... ")
def in_trang_thai(c, nhan):
    gia, buoc, dk, luot = c.execute(TRANG_THAI).fetchone()
    print(f"   {nhan}: phiên 1 giá hiện tại = {tien(gia)} | bước giá = {tien(buoc)}")
    print(f"   {' ' * len(nhan)}  đăng ký phiên 1 = {dk}")
    print(f"   {' ' * len(nhan)}  số lượt thử nghiệm còn lại = {luot}")

def nguoi_tra_gia(ham, serializable, ma_nguoi, rao, kq, t_bat_dau):
    conn = psycopg.connect(DSN, autocommit=True)
    rao.wait()                                              # mọi người bắt đầu cùng lúc
    for _ in range(SO_LAN):
        thay, gia = conn.execute("SELECT GiaHienTai, COALESCE(GiaHienTai + BuocGia, GiaKhoiDiem) FROM PHIENDAUGIA "
                                 "WHERE MaPhien = %s", (PHIEN,)).fetchone()   # giá người dùng thấy trên màn hình
        ma_yc, thu_lai, t0 = uuid.uuid4(), 0, time.perf_counter()
        dau = f"Người {ma_nguoi:>2}: thấy {tien(thay)} -> trả {tien(gia)}"
        while True:
            try:
                with conn.transaction():                     # mỗi lần thử = 1 giao dịch mới
                    if serializable:
                        conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                    luot = conn.execute(f"SELECT {ham}(%s, %s, %s, %s)", (PHIEN, ma_nguoi, gia, ma_yc)).fetchone()[0]
                ket_qua, ghi_chu = "thanh_cong", f"THÀNH CÔNG, được lượt {luot}"; break
            except (errors.SerializationFailure, errors.DeadlockDetected):
                thu_lai += 1
                if CHI_TIET:
                    in_(f"   [{time.perf_counter() - t_bat_dau:6.3f}s] {dau}   XUNG ĐỘT 40001 -> ROLLBACK, thử lại lần {thu_lai}")
                if thu_lai > MAX_THU_LAI:
                    ket_qua, ghi_chu = "that_bai_sau_thu_lai", "THẤT BẠI sau quá nhiều lần thử lại"; break
                time.sleep(0.005 * thu_lai + random.random() * 0.01)
            except psycopg.Error as e:
                ket_qua, ghi_chu = "bi_tu_choi", "BỊ TỪ CHỐI: " + (e.diag.message_primary or "").split(" và ")[0]; break
        ms = (time.perf_counter() - t0) * 1000
        if CHI_TIET:
            in_(f"   [{time.perf_counter() - t_bat_dau:6.3f}s] {dau}   {ghi_chu}  ({ms:.0f} ms)")
        kq.append((ket_qua, thu_lai, ms))
    conn.close()

GIAI_THICH = {
    "PA1": ["Cơ chế: SELECT ... FOR UPDATE khóa dòng phiên 1 ngay lúc đọc.",
            "Người đến sau phải XẾP HÀNG chờ, rồi đọc giá MỚI NHẤT mới kiểm tra -> không bao giờ phải thử lại."],
    "PA2_RC": ["Cơ chế: đọc phiên KHÔNG khóa; lúc UPDATE kiểm tra PhienBan.",
               "Nếu người khác vừa đổi giá -> PhienBan lệch -> hàm TỰ THỬ LẠI BÊN TRONG (bên ngoài không thấy, nên cột thử lại = 0)."],
    "PA2_SR": ["Cơ chế: ứng dụng mở BEGIN ISOLATION LEVEL SERIALIZABLE.",
               "Gặp xung đột, PostgreSQL báo lỗi 40001 -> ứng dụng ROLLBACK và chạy lại bằng giao dịch MỚI (dòng 'XUNG ĐỘT' bên dưới)."],
}

def do(buoc, ma, ten, ham, serializable):
    if CHI_TIET:
        tieu_de(f"BƯỚC {buoc}/5: ĐO {ten}")
        for dong in GIAI_THICH[ma]: print("   " + dong)
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(RESET)
        gia0 = c.execute("SELECT GiaHienTai FROM PHIENDAUGIA WHERE MaPhien = 1").fetchone()[0]
    nguoi = NGUOI[:SO_LUONG]
    if CHI_TIET:
        print(f"\n   Đặt lại phiên 1 về giá {tien(gia0)}.")
        print(f"   {len(nguoi)} người ({', '.join(map(str, nguoi))}) xuất phát CÙNG LÚC, mỗi người trả {SO_LAN} lần.")
        print("   Mỗi người: nhìn giá hiện tại -> trả thêm 1 bước giá. Ai bị người khác vượt trước thì bị từ chối.\n")
    kq, rao = [], threading.Barrier(len(nguoi))
    t0 = time.perf_counter()
    ts = [threading.Thread(target=nguoi_tra_gia, args=(ham, serializable, n, rao, kq, t0)) for n in nguoi]
    for t in ts: t.start()
    for t in ts: t.join()
    tong_tg = time.perf_counter() - t0
    with psycopg.connect(DSN, autocommit=True) as c:
        gia_luu, gia_max, dung, so_luot = c.execute(DOI_SOAT).fetchone()
    tre = sorted(x[2] for x in kq)
    dem = lambda k: sum(1 for x in kq if x[0] == k)
    doi_soat = "NHAT_QUAN" if dung and so_luot == dem("thanh_cong") else "SAI_LECH"
    if CHI_TIET:
        print(f"\n   Tổng kết: {len(kq)} yêu cầu -> {dem('thanh_cong')} thành công, {dem('bi_tu_choi')} bị từ chối, "
              f"{sum(x[1] for x in kq)} lần phải thử lại.")
        print(f"   Đối soát: giá lưu trong phiên = {tien(gia_luu)} | giá cao nhất trong lịch sử = {tien(gia_max)}"
              f" | số lượt ghi = {so_luot}  ->  {doi_soat}")
        dung_lai()
    return [ten, len(kq), dem("thanh_cong"), dem("bi_tu_choi"), dem("that_bai_sau_thu_lai"),
            sum(x[1] for x in kq), round(statistics.mean(tre), 1), round(tre[len(tre) // 2], 1),
            round(tre[max(int(len(tre) * 0.95) - 1, 0)], 1), round(len(kq) / tong_tg, 1), doi_soat]

# ---- BƯỚC 1: chuẩn bị – tạm duyệt thêm người dùng cho phiên 1 (trừ người bán), nhớ trạng thái cũ để khôi phục ----
if CHI_TIET:
    tieu_de("BƯỚC 1/5: CHUẨN BỊ")
    print(f"   Kết nối: {DSN}")
with psycopg.connect(DSN, autocommit=True) as c:
    if CHI_TIET: in_trang_thai(c, "TRƯỚC KHI CHẠY")
    ban = c.execute("SELECT t.MaNguoiBan FROM PHIENDAUGIA p JOIN TAISAN t USING (MaTaiSan) WHERE p.MaPhien = 1").fetchone()[0]
    cu = c.execute("SELECT MaNguoiDung, TrangThaiDangKy FROM DANGKY WHERE MaPhien = 1").fetchall()
    NGUOI = [r[0] for r in c.execute("SELECT MaNguoiDung FROM NGUOIDUNG WHERE MaNguoiDung <> %s ORDER BY 1", (ban,))]
    SO_LUONG = min(SO_LUONG, len(NGUOI))
    NGUOI = NGUOI[:SO_LUONG]
    c.execute("""INSERT INTO DANGKY (MaPhien, MaNguoiDung, TrangThaiDangKy) SELECT 1, x, 'DA_DUYET' FROM unnest(%s::bigint[]) x
                 ON CONFLICT (MaPhien, MaNguoiDung) DO UPDATE SET TrangThaiDangKy = 'DA_DUYET'""", (NGUOI,))
    if CHI_TIET:
        print(f"\n   Người bán của phiên 1 là người {ban} -> không được trả giá, loại khỏi danh sách.")
        print(f"   Tạm duyệt đăng ký cho {SO_LUONG} người: {', '.join(map(str, NGUOI))} (sẽ khôi phục khi xong).")
        dung_lai()
try:
    bang = [do(2, "PA1", "PA1 fn_TraGia (FOR UPDATE)", "fn_TraGia", False),
            do(3, "PA2_RC", "PA2 fn_TraGia_Serializable (READ COMMITTED)", "fn_TraGia_Serializable", False),
            do(4, "PA2_SR", "PA2 fn_TraGia_Serializable (SERIALIZABLE + thử lại)", "fn_TraGia_Serializable", True)]
finally:
    with psycopg.connect(DSN, autocommit=True) as c:          # BƯỚC 5: khôi phục dữ liệu như trước khi đo
        c.execute(RESET)
        c.execute("DELETE FROM DANGKY WHERE MaPhien = 1 AND NOT (MaNguoiDung = ANY(%s::bigint[]))", ([r[0] for r in cu],))
        for ma, tt in cu:
            c.execute("UPDATE DANGKY SET TrangThaiDangKy = %s WHERE MaPhien = 1 AND MaNguoiDung = %s", (tt, ma))
        if CHI_TIET:
            tieu_de("BƯỚC 5/5: KHÔI PHỤC DỮ LIỆU")
            in_trang_thai(c, "SAU KHI CHẠY")

# ---- BẢNG SO SÁNH (đưa vào báo cáo) ----
cot = ["Số yêu cầu", "Thành công", "Bị từ chối", "Thất bại", "Số lần thử lại",
       "TB (ms)", "p50 (ms)", "p95 (ms)", "Yêu cầu/giây", "Đối soát"]
ten_ngan = ["PA1 FOR UPDATE", "PA2 READ COMMITTED", "PA2 SERIALIZABLE"]
tieu_de(f"BẢNG SO SÁNH: {SO_LUONG} người trả giá đồng thời x {SO_LAN} lần, cùng phiên 1, cùng dữ liệu")
print(f"   {'Chỉ số':<16}" + "".join(f"| {t:<20}" for t in ten_ngan))
print("   " + "-" * 16 + ("+" + "-" * 21) * 3)
for i, k in enumerate(cot):
    print(f"   {k:<16}" + "".join(f"| {str(row[i + 1]):<20}" for row in bang))
print("""
   Cách đọc:
   - Thành công / Bị từ chối: bị từ chối là ĐÚNG khi người khác đã trả cao hơn trước (giá mình thấy đã cũ).
   - Số lần thử lại: số lần gặp lỗi 40001 phải ROLLBACK và chạy lại (PA1 luôn = 0 vì xếp hàng chờ khóa).
   - TB = thời gian phản hồi trung bình; p50 / p95 = 50% / 95% yêu cầu nhanh hơn mức này.
   - Đối soát NHAT_QUAN = giá lưu trong phiên khớp giá cao nhất trong lịch sử (không mất cập nhật).
""")

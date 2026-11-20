"""Website mô phỏng Đồ án 19 – Hệ thống đấu giá trực tuyến.

Mọi thao tác trên web đều chạy SQL THẬT trên PostgreSQL (database riêng `daugia_web`):
  * gọi đúng các hàm trong queries.sql (fn_TraGia, fn_TraGia_Serializable, fn_DongPhienDauGia,
    fn_BaoCaoPhienDauGiaDong),
  * chạy nguyên văn các câu trong DDL/seed/queries/test_cases,
  * hoặc sinh câu lệnh theo đúng cấu trúc bảng trong DDL (đăng ký, duyệt, tạo phiên).
Mỗi phản hồi trả kèm chính xác chuỗi SQL đã gửi, kết quả, lỗi và giải thích.
"""
import datetime as dt
import decimal
import re
import threading
import time
import uuid

import psycopg
from psycopg import ClientCursor
from flask import Flask, jsonify, request, send_from_directory

import sqlfile
from explain import EXPLAIN, KEY_LINES, QUERY_LIST

DB = "daugia_web"
CONNINFO = f"host=localhost user=postgres dbname={DB}"
app = Flask(__name__, static_folder="static", static_url_path="/static")
FUNCS = sqlfile.function_index()


# ----------------------------------------------------------------- tiện ích DB
def ensure_db():
    with psycopg.connect("host=localhost user=postgres dbname=postgres", autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB,)).fetchone():
            c.execute(f'CREATE DATABASE "{DB}"')


def connect():
    conn = psycopg.connect(CONNINFO, autocommit=True, cursor_factory=ClientCursor,
                           application_name="web_demo")
    conn.notices = []
    conn.add_notice_handler(lambda d: conn.notices.append(f"{d.severity}: {d.message_primary}"))
    return conn


def jsval(v):
    if isinstance(v, decimal.Decimal):
        return format(v, "f")
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return str(v)
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (list, tuple)):
        return [jsval(x) for x in v]
    return v


PLPG_LINE = re.compile(r"PL/pgSQL function (\w+)\([^)]*\) line (\d+)")


def map_error_line(context):
    """'PL/pgSQL function fn_tragia(...) line 39 at RAISE' -> dòng 154 trong queries.sql."""
    if not context:
        return None
    m = PLPG_LINE.search(context)
    if not m:
        return None
    f = FUNCS.get(m.group(1).lower())
    if not f:
        return None
    return {"func": f["name"], "func_line": int(m.group(2)), "file_line": f["dollar"] + int(m.group(2)) - 1}


def run(conn, sql, params=None, title=None, max_rows=300):
    """Chạy 1 câu lệnh, trả về đúng chuỗi SQL đã gửi + kết quả/lỗi."""
    cur = conn.cursor()
    shown = cur.mogrify(sql, params) if params is not None else sql
    conn.notices.clear()
    t0 = time.perf_counter()
    step = {"title": title, "sql": shown}
    try:
        cur.execute(shown)
        step["ms"] = round((time.perf_counter() - t0) * 1000, 1)
        step["status"] = cur.statusmessage
        step["rowcount"] = cur.rowcount
        if cur.description:
            step["columns"] = [d.name for d in cur.description]
            rows = cur.fetchmany(max_rows)
            step["rows"] = [[jsval(v) for v in r] for r in rows]
            step["truncated"] = cur.rowcount > max_rows
    except psycopg.Error as e:
        step["ms"] = round((time.perf_counter() - t0) * 1000, 1)
        d = e.diag
        step["error"] = {"message": d.message_primary or str(e), "sqlstate": d.sqlstate,
                         "detail": d.message_detail, "context": d.context,
                         "where": map_error_line(d.context)}
    step["notices"] = list(conn.notices)
    step["tx"] = conn.info.transaction_status.name
    return step


def first_value(step):
    return step["rows"][0][0] if step.get("rows") else None


def payload(kind, title, steps, **extra):
    """kind: 'func' (gọi hàm có sẵn), 'file' (nguyên văn từ file), 'gen' (website sinh), 'helper'."""
    d = {"kind": kind, "title": title, "steps": steps, "at": dt.datetime.now().strftime("%H:%M:%S")}
    d.update(extra)
    return jsonify(d)


def func_source(name, highlight=(), error_line=None):
    f = FUNCS[name.lower()]
    return {"name": f["name"], "file": "queries.sql",
            "lines": sqlfile.file_lines("queries", f["create"], f["end"]),
            "highlight": list(highlight), "error_line": error_line}


GENERAL = None  # kết nối dùng chung cho thao tác thường (autocommit)
GEN_LOCK = threading.Lock()


def gconn():
    global GENERAL
    if GENERAL is None or GENERAL.closed:
        GENERAL = connect()
    elif GENERAL.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        GENERAL.execute("ROLLBACK")
    return GENERAL


def db_ready():
    with GEN_LOCK:
        r = gconn().execute("SELECT to_regclass('phiendaugia') IS NOT NULL, "
                            "EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'fn_tragia')").fetchone()
        n = gconn().execute("SELECT count(*) FROM phiendaugia").fetchone()[0] if r[0] else 0
        return {"tables": r[0], "functions": r[1], "sessions": n}


# ----------------------------------------------------------------- trang & file
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/status")
def api_status():
    try:
        return jsonify({"ok": True, "db": DB, **db_ready()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.get("/api/files")
def api_files():
    out = {}
    for k, name in sqlfile.FILES.items():
        text = sqlfile.read_file(k)
        st = sqlfile.split_sql(text)
        out[k] = {"name": name, "lines": text.count("\n") + 1,
                  "statements": [{"line_start": s["line_start"], "line_end": s["line_end"], "sql": s["sql"]} for s in st]}
    out["test"]["sections"] = [{"title": s["title"], "items": [
        {"index": i["index"], "line_start": i["line_start"], "line_end": i["line_end"], "sql": i["sql"]}
        for i in s["items"]]} for s in sqlfile.test_sections()]
    out["explain"] = {k: EXPLAIN.get("file_" + k) for k in sqlfile.FILES}
    return jsonify(out)


def stop_lab():
    for t in LAB.values():
        t.reset_conn()


@app.post("/api/run_file")
def api_run_file():
    key = request.json["file"]
    stmts = sqlfile.split_sql(sqlfile.read_file(key))
    if key in ("ddl", "seed"):
        stop_lab()  # 2 tab thử nghiệm không được giữ khóa khi xóa/tạo bảng
    steps = []
    with GEN_LOCK:
        c = gconn()
        for s in stmts:
            st = run(c, s["sql"], title=f"Dòng {s['line_start']}–{s['line_end']}")
            st["line_start"], st["line_end"] = s["line_start"], s["line_end"]
            steps.append(st)
            if "error" in st:
                if c.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                    steps.append(run(c, "ROLLBACK", title="Tự động ROLLBACK vì có lỗi"))
                break
    ok = all("error" not in s for s in steps)
    return payload("file", f"Chạy cả file {sqlfile.FILES[key]} ({len(steps)}/{len(stmts)} câu lệnh)",
                   steps, explain=EXPLAIN.get("file_" + key), ok=ok)


@app.post("/api/run_stmt")
def api_run_stmt():
    key, idx = request.json["file"], int(request.json["index"])
    s = sqlfile.split_sql(sqlfile.read_file(key))[idx]
    with GEN_LOCK:
        st = run(gconn(), s["sql"], title=f"{sqlfile.FILES[key]} · dòng {s['line_start']}–{s['line_end']}")
    st["line_start"], st["line_end"] = s["line_start"], s["line_end"]
    extra = {}
    w = (st.get("error") or {}).get("where")
    called = re.findall(r"(fn_\w+)\s*\(", s["sql"])
    if called and called[0].lower() in FUNCS:
        extra["source"] = func_source(called[0], KEY_LINES.get(called[0].lower(), []), w and w["file_line"])
    return payload("file", f"Chạy câu lệnh trong {sqlfile.FILES[key]}", [st],
                   explain=EXPLAIN.get(f"test_{s['line_start']}") or EXPLAIN.get("file_" + key), **extra)


# ----------------------------------------------------------------- dữ liệu nền
@app.get("/api/meta")
def api_meta():
    with GEN_LOCK:
        c = gconn()
        users = run(c, "SELECT MaNguoiDung, HoTen, ThuDienTu FROM NGUOIDUNG ORDER BY MaNguoiDung")
        cats = run(c, "SELECT MaDanhMuc, TenDanhMuc, MaDanhMucCha FROM DANHMUC ORDER BY MaDanhMuc")
        assets = run(c, """SELECT ts.MaTaiSan, ts.TenTaiSan, ts.LoaiTaiSan, ts.MaNguoiBan, nd.HoTen,
                                  EXISTS (SELECT 1 FROM PHIENDAUGIA p WHERE p.MaTaiSan = ts.MaTaiSan
                                          AND p.TrangThaiPhien IN ('DANG_DIEN_RA','CHUA_MO')) AS dang_co_phien
                           FROM TAISAN ts JOIN NGUOIDUNG nd ON nd.MaNguoiDung = ts.MaNguoiBan ORDER BY ts.MaTaiSan""")
    return jsonify({"users": users.get("rows", []), "cats": cats.get("rows", []), "assets": assets.get("rows", [])})


@app.get("/api/sessions")
def api_sessions():
    a = request.args
    named, params = [], []
    for name, cast, key in (("p_MaDanhMucGoc", "bigint", "dm"), ("p_TrangThai", "varchar", "tt"),
                            ("p_LoaiTaiSan", "varchar", "loai"), ("p_GiaTu", "numeric", "giatu"),
                            ("p_GiaDen", "numeric", "giaden"), ("p_TuKhoa", "varchar", "tukhoa")):
        v = a.get(key)
        if v not in (None, ""):
            named.append(f"{name} => %s::{cast}")
            params.append(v)
    call = "fn_BaoCaoPhienDauGiaDong(" + (",\n       ".join(named)) + ")"
    sql = f"""SELECT r.*, p.MaTaiSan, p.BuocGia, p.PhienBan
FROM {call} AS r
JOIN PHIENDAUGIA p ON p.MaPhien = r.MaPhien
ORDER BY CASE r.TrangThaiPhien WHEN 'DANG_DIEN_RA' THEN 0 WHEN 'CHUA_MO' THEN 1 ELSE 2 END,
         r.ThoiDiemDong, r.MaPhien"""
    with GEN_LOCK:
        st = run(gconn(), sql, params, title="Danh sách phiên qua hàm báo cáo động")
    return payload("func", "Tải danh sách phiên đấu giá (bộ lọc động)", [st],
                   explain=EXPLAIN["sessions"], source=func_source("fn_BaoCaoPhienDauGiaDong",
                                                                   KEY_LINES["fn_baocaophiendaugiadong"]))


@app.get("/api/session/<int:pid>")
def api_session(pid):
    with GEN_LOCK:
        c = gconn()
        steps = [
            run(c, """SELECT p.*, ts.TenTaiSan, ts.MoTa, ts.LoaiTaiSan, ts.MaNguoiBan, nb.HoTen AS NguoiBan,
       dm.TenDanhMuc,
       tp.TacGia, tp.ChatLieu, tp.NamSangTac,                       -- lớp con: Tác phẩm nghệ thuật
       ds.NguonGoc, ds.DoHiem, ds.NamSanXuat,                       -- lớp con: Đồ sưu tầm
       tb.ThuongHieu, tb.MauThietBi, tb.SoSeRi, tb.TinhTrang,       -- lớp con: Thiết bị điện tử
       now() AS BayGio
FROM PHIENDAUGIA p
JOIN TAISAN ts      ON ts.MaTaiSan = p.MaTaiSan
JOIN NGUOIDUNG nb   ON nb.MaNguoiDung = ts.MaNguoiBan
JOIN DANHMUC dm     ON dm.MaDanhMuc = ts.MaDanhMuc
LEFT JOIN TACPHAMNGHETHUAT tp ON tp.MaTaiSan = ts.MaTaiSan
LEFT JOIN DOSUUTAM ds         ON ds.MaTaiSan = ts.MaTaiSan
LEFT JOIN THIETBIDIENTU tb    ON tb.MaTaiSan = ts.MaTaiSan
WHERE p.MaPhien = %s""", (pid,), title="1. Thông tin phiên + tài sản + lớp con (EER)"),
            run(c, """-- Lấy từ queries.sql (Lịch sử giá và mức tăng), thêm điều kiện lọc 1 phiên
SELECT l.MaPhien, l.MaLuotTraGia, l.MaNguoiTraGia, nd.HoTen AS NguoiTraGia,
       l.ThoiDiemChapNhan, l.SoTien,
       l.SoTien - LAG(l.SoTien) OVER (
           PARTITION BY l.MaPhien ORDER BY l.ThoiDiemChapNhan, l.MaLuotTraGia
       ) AS MucTang,
       l.MaYeuCau
FROM LUOTTRAGIA l
JOIN NGUOIDUNG nd ON nd.MaNguoiDung = l.MaNguoiTraGia
WHERE l.MaPhien = %s
ORDER BY l.ThoiDiemChapNhan DESC, l.MaLuotTraGia DESC""", (pid,), title="2. Lịch sử trả giá (hàm cửa sổ LAG)"),
            run(c, """SELECT dk.MaNguoiDung, nd.HoTen, dk.TrangThaiDangKy, dk.ThoiDiemDangKy
FROM DANGKY dk JOIN NGUOIDUNG nd ON nd.MaNguoiDung = dk.MaNguoiDung
WHERE dk.MaPhien = %s ORDER BY dk.ThoiDiemDangKy, dk.MaNguoiDung""", (pid,), title="3. Danh sách đăng ký tham gia"),
            run(c, """SELECT k.MaPhien, k.MaLuotThang, l.SoTien AS GiaThang, nd.HoTen AS NguoiThang, k.ThoiDiemChot
FROM KETQUADAUGIA k
LEFT JOIN LUOTTRAGIA l ON l.MaLuotTraGia = k.MaLuotThang AND l.MaPhien = k.MaPhien
LEFT JOIN NGUOIDUNG nd ON nd.MaNguoiDung = l.MaNguoiTraGia
WHERE k.MaPhien = %s""", (pid,), title="4. Kết quả đấu giá (nếu đã chốt)"),
            run(c, """SELECT MaNhatKy, HanhDong, MaTacNhan, ChiTiet, ThoiDiemGhi, MaGiaoDich
FROM NHATKYTHAYDOI WHERE MaPhien = %s ORDER BY MaNhatKy DESC LIMIT 15""", (pid,), title="5. Nhật ký thay đổi"),
        ]
    return payload("gen", f"Mở chi tiết phiên #{pid}", steps, explain=EXPLAIN["session_detail"])


# ----------------------------------------------------------------- thao tác nghiệp vụ
BID_FUNCS = {"fn_TraGia": "fn_tragia", "fn_TraGia_Serializable": "fn_tragia_serializable"}


@app.post("/api/bid")
def api_bid():
    j = request.json
    fn = j.get("method", "fn_TraGia")
    if fn not in BID_FUNCS:
        return jsonify({"error": "phương án không hợp lệ"}), 400
    req_id = j.get("uuid") or str(uuid.uuid4())
    with GEN_LOCK:
        c = gconn()
        before = run(c, "SELECT GiaHienTai, MaLuotDanDau, PhienBan FROM PHIENDAUGIA WHERE MaPhien = %s",
                     (j["phien"],), title="Trước: trạng thái phiên")
        call = run(c, f"SELECT {fn}(%s, %s, %s, %s::uuid) AS ma_luot_tra_gia",
                   (int(j["phien"]), int(j["user"]), decimal.Decimal(str(j["amount"])), req_id),
                   title=f"Gọi hàm {fn} (auto-commit: hàm chạy trong 1 giao dịch riêng)")
        steps = [before, call]
        if "error" not in call:
            steps.append(run(c, """SELECT p.GiaHienTai, p.MaLuotDanDau, p.PhienBan, l.SoTien, l.MaNguoiTraGia,
       l.MaYeuCau, l.ThoiDiemChapNhan
FROM PHIENDAUGIA p JOIN LUOTTRAGIA l ON l.MaLuotTraGia = %s
WHERE p.MaPhien = %s""", (first_value(call), j["phien"]), title="Sau: phiên + lượt vừa ghi"))
    w = (call.get("error") or {}).get("where")
    return payload("func", f"Trả giá {int(j['amount']):,} đ – người dùng #{j['user']} – phiên #{j['phien']}".replace(",", "."),
                   steps, explain=EXPLAIN[BID_FUNCS[fn]], uuid=req_id,
                   source=func_source(fn, KEY_LINES[BID_FUNCS[fn]], w and w["file_line"]),
                   ok="error" not in call, result=first_value(call))


@app.post("/api/register")
def api_register():
    j = request.json
    with GEN_LOCK:
        st = run(gconn(), "INSERT INTO DANGKY (MaPhien, MaNguoiDung, TrangThaiDangKy)\nVALUES (%s, %s, 'CHO_DUYET')\nRETURNING *",
                 (int(j["phien"]), int(j["user"])), title="Website sinh câu INSERT theo cấu trúc bảng DANGKY (DDL dòng 98–107)")
    return payload("gen", f"Người dùng #{j['user']} đăng ký tham gia phiên #{j['phien']}", [st],
                   explain=EXPLAIN["register"], ddl=sqlfile.file_lines("ddl", 97, 107), ok="error" not in st)


@app.post("/api/approve")
def api_approve():
    j = request.json
    status = j["status"] if j["status"] in ("DA_DUYET", "TU_CHOI", "CHO_DUYET") else "DA_DUYET"
    with GEN_LOCK:
        st = run(gconn(), "UPDATE DANGKY\nSET TrangThaiDangKy = %s\nWHERE MaPhien = %s AND MaNguoiDung = %s\nRETURNING *",
                 (status, int(j["phien"]), int(j["user"])), title="Website sinh câu UPDATE trên bảng DANGKY")
    return payload("gen", f"Đổi trạng thái đăng ký của #{j['user']} ở phiên #{j['phien']} → {status}", [st],
                   explain=EXPLAIN["approve"], ok="error" not in st)


@app.post("/api/close")
def api_close():
    pid = int(request.json["phien"])
    with GEN_LOCK:
        c = gconn()
        call = run(c, "SELECT fn_DongPhienDauGia(%s) AS ma_luot_thang", (pid,), title="Gọi hàm fn_DongPhienDauGia")
        steps = [call]
        if "error" not in call:
            steps.append(run(c, """SELECT p.TrangThaiPhien, p.GiaHienTai, k.MaLuotThang, k.ThoiDiemChot,
       (SELECT count(*) FROM KETQUADAUGIA k2 WHERE k2.MaPhien = p.MaPhien) AS so_dong_ket_qua
FROM PHIENDAUGIA p LEFT JOIN KETQUADAUGIA k ON k.MaPhien = p.MaPhien
WHERE p.MaPhien = %s""", (pid,), title="Sau khi đóng: trạng thái + số dòng kết quả"))
    w = (call.get("error") or {}).get("where")
    return payload("func", f"Đóng phiên #{pid}", steps, explain=EXPLAIN["fn_dongphiendaugia"],
                   source=func_source("fn_DongPhienDauGia", KEY_LINES["fn_dongphiendaugia"], w and w["file_line"]),
                   ok="error" not in call)


@app.post("/api/time")
def api_time():
    """Công cụ hỗ trợ: gia hạn phiên (giống Bước 0 test_cases) hoặc tua tới giờ đóng."""
    j = request.json
    pid, mode = int(j["phien"]), j["mode"]
    with GEN_LOCK:
        c = gconn()
        if mode == "extend":
            st = run(c, """-- Giống BƯỚC 0 trong test_cases.sql (dòng 12–16), áp dụng cho 1 phiên
UPDATE PHIENDAUGIA
SET TrangThaiPhien = 'DANG_DIEN_RA',
    ThoiDiemMo = CURRENT_TIMESTAMP - INTERVAL '1 hour',
    ThoiDiemDong = CURRENT_TIMESTAMP + INTERVAL '2 hours'
WHERE MaPhien = %s
  AND NOT EXISTS (SELECT 1 FROM KETQUADAUGIA k WHERE k.MaPhien = %s)  -- website chặn mở lại phiên đã chốt
RETURNING MaPhien, TrangThaiPhien, ThoiDiemMo, ThoiDiemDong""", (pid, pid), title="Gia hạn phiên thêm 2 giờ")
        else:
            st = run(c, """-- Công cụ demo: kéo giờ đóng về 'ngay bây giờ' để thử đóng phiên
UPDATE PHIENDAUGIA
SET ThoiDiemDong = GREATEST(CURRENT_TIMESTAMP, ThoiDiemMo + INTERVAL '1 second')
WHERE MaPhien = %s AND TrangThaiPhien IN ('DANG_DIEN_RA', 'CHUA_MO')
RETURNING MaPhien, ThoiDiemMo, ThoiDiemDong""", (pid,), title="Tua nhanh tới giờ đóng")
    return payload("helper", "Công cụ thời gian: " + ("gia hạn phiên" if mode == "extend" else "tua tới giờ đóng"),
                   [st], explain=EXPLAIN["time_" + mode], ok="error" not in st)


@app.post("/api/create_session")
def api_create_session():
    j = request.json
    with GEN_LOCK:
        st = run(gconn(), """INSERT INTO PHIENDAUGIA (MaTaiSan, GiaKhoiDiem, BuocGia, ThoiDiemMo, ThoiDiemDong, TrangThaiPhien)
VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + %s::interval, 'DANG_DIEN_RA')
RETURNING MaPhien, GiaHienTai, MaLuotDanDau, PhienBan""",
                 (int(j["asset"]), decimal.Decimal(str(j["start"])), decimal.Decimal(str(j["step"])), f"{int(j['hours'])} hours"),
                 title="Website sinh câu INSERT theo cấu trúc bảng PHIENDAUGIA (DDL dòng 76–95)")
    return payload("gen", f"Mở phiên mới cho tài sản #{j['asset']}", [st], explain=EXPLAIN["create_session"],
                   ddl=sqlfile.file_lines("ddl", 75, 95), ok="error" not in st, result=first_value(st))


# ----------------------------------------------------------------- thống kê
@app.get("/api/queries")
def api_queries():
    return jsonify([{**q, "sql": "\n".join(l["text"] for l in sqlfile.file_lines("queries", q["a"], q["b"]))}
                    for q in QUERY_LIST])


@app.post("/api/queries/<key>")
def api_query_run(key):
    q = next(q for q in QUERY_LIST if q["key"] == key)
    sql = "\n".join(l["text"] for l in sqlfile.file_lines("queries", q["a"], q["b"]))
    with GEN_LOCK:
        st = run(gconn(), sql, title=f"queries.sql · dòng {q['a']}–{q['b']}")
    return payload("file", q["title"], [st], explain=q["explain"])


# ----------------------------------------------------------------- phòng thí nghiệm 2 tab
class LabTab:
    def __init__(self, name):
        self.name, self.conn, self.pid = name, None, None
        self.busy, self.job, self.history, self.lock = False, None, [], threading.Lock()

    def ensure(self):
        if self.conn is None or self.conn.closed:
            self.conn = connect()
            self.conn.execute(f"SET application_name = 'web_lab_tab_{self.name}'")
            self.pid = self.conn.info.backend_pid

    def reset_conn(self):
        if self.busy and self.conn is not None:
            try:
                self.conn.cancel()
            except Exception:
                pass
            for _ in range(50):
                if not self.busy:
                    break
                time.sleep(0.1)
        if self.conn is not None and not self.conn.closed:
            try:
                if self.conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                    self.conn.execute("ROLLBACK")
            except Exception:
                self.conn.close()

    def submit(self, sql, label):
        with self.lock:
            if self.busy:
                return False
            self.ensure()
            self.busy = True
            self.job = {"label": label, "sql": sql, "started": time.time(), "steps": [], "done": False}
        threading.Thread(target=self._run, args=(self.job,), daemon=True).start()
        return True

    def _run(self, job):
        try:
            for s in sqlfile.split_sql(job["sql"]):
                st = run(self.conn, s["sql"])
                job["steps"].append(st)
                if "error" in st:
                    break
        finally:
            job["done"], job["ended"] = True, time.time()
            self.history.insert(0, job)
            del self.history[30:]
            self.busy = False

    def state(self):
        tx = self.conn.info.transaction_status.name if self.conn and not self.conn.closed else "CHƯA KẾT NỐI"
        return {"name": self.name, "pid": self.pid, "busy": self.busy, "tx": tx,
                "job": _job_view(self.job), "history": [_job_view(h) for h in self.history[:8]]}


def _job_view(job):
    if not job:
        return None
    end = job.get("ended") or time.time()
    return {"label": job["label"], "sql": job["sql"], "steps": job["steps"], "done": job["done"],
            "seconds": round(end - job["started"], 1)}


LAB = {"A": LabTab("A"), "B": LabTab("B")}
MON = {"conn": None}
MON_LOCK = threading.Lock()


def mon_conn():
    if MON["conn"] is None or MON["conn"].closed:
        MON["conn"] = connect()
    return MON["conn"]


@app.post("/api/lab/<t>/exec")
def api_lab_exec(t):
    j = request.json
    ok = LAB[t].submit(j["sql"], j.get("label") or "Lệnh tự gõ")
    if not ok:
        return jsonify({"error": f"Tab {t} đang bận (lệnh trước chưa xong, có thể đang chờ khóa)."}), 409
    time.sleep(0.35)  # đợi một chút để lệnh nhanh kịp xong
    return jsonify({"ok": True})


@app.post("/api/lab/<t>/cancel")
def api_lab_cancel(t):
    tab = LAB[t]
    if tab.busy and tab.conn:
        tab.conn.cancel()
    return jsonify({"ok": True})


MONITOR_SQL = """SELECT a.pid,
       a.application_name,
       a.state,
       a.wait_event_type,
       a.wait_event,
       pg_blocking_pids(a.pid)                  AS bi_chan_boi,
       EXISTS (SELECT 1 FROM pg_locks l JOIN pg_class c ON c.oid = l.relation
               WHERE l.pid = a.pid AND c.relname = 'luottragia'
                 AND l.mode = 'RowExclusiveLock')  AS da_insert_luottragia,
       EXISTS (SELECT 1 FROM pg_locks l JOIN pg_class c ON c.oid = l.relation
               WHERE l.pid = a.pid AND c.relname = 'phiendaugia'
                 AND l.mode IN ('RowShareLock','RowExclusiveLock')) AS dang_dung_phiendaugia,
       round(extract(epoch FROM now() - a.xact_start)::numeric, 1) AS giay_trong_giao_dich
FROM pg_stat_activity a
WHERE a.pid = ANY(%s)
ORDER BY a.application_name"""


@app.get("/api/lab/state")
def api_lab_state():
    pid = int(request.args.get("phien", 1))
    pids = [t.pid for t in LAB.values() if t.pid]
    out = {"tabs": {k: t.state() for k, t in LAB.items()}}
    with MON_LOCK:
        c = mon_conn()
        out["monitor"] = run(c, MONITOR_SQL, (pids or [0],), title="Soi khóa (pg_stat_activity + pg_locks)")
        out["check"] = run(c, """SELECT p.MaPhien,
       p.GiaHienTai   AS gia_luu_trong_phien,
       p.MaLuotDanDau AS luot_dan_dau_luu,
       (SELECT MAX(SoTien) FROM LUOTTRAGIA WHERE MaPhien = p.MaPhien) AS gia_cao_nhat_lich_su,
       CASE WHEN p.GiaHienTai IS NOT DISTINCT FROM (SELECT MAX(SoTien) FROM LUOTTRAGIA WHERE MaPhien = p.MaPhien)
            THEN 'NHAT_QUAN' ELSE 'SAI_LECH' END AS doi_soat
FROM PHIENDAUGIA p WHERE p.MaPhien = %s""", (pid,), title="Đối soát (chỉ thấy dữ liệu đã COMMIT)")
        out["bids"] = run(c, """SELECT l.MaLuotTraGia, l.MaNguoiTraGia, nd.HoTen, l.SoTien, l.ThoiDiemChapNhan
FROM LUOTTRAGIA l JOIN NGUOIDUNG nd ON nd.MaNguoiDung = l.MaNguoiTraGia
WHERE l.MaPhien = %s ORDER BY l.MaLuotTraGia DESC LIMIT 6""", (pid,), title="Lượt trả giá đã COMMIT")
    return jsonify(out)


@app.post("/api/lab/reset")
def api_lab_reset():
    pid = int(request.json.get("phien", 1))
    for t in LAB.values():
        t.reset_conn()
    sql = """BEGIN;
-- 1) xóa các lượt trả giá phát sinh khi thử nghiệm (dữ liệu mẫu chỉ có lượt 1–45)
DELETE FROM LUOTTRAGIA WHERE MaPhien = %(p)s AND MaLuotTraGia > 45;
-- 2) mở lại phiên 2 giờ và tính lại người dẫn đầu từ lịch sử còn lại
UPDATE PHIENDAUGIA
SET TrangThaiPhien = 'DANG_DIEN_RA',
    ThoiDiemMo  = LEAST(ThoiDiemMo, CURRENT_TIMESTAMP - INTERVAL '1 hour'),  -- không dời giờ mở về sau các lượt cũ
    ThoiDiemDong = CURRENT_TIMESTAMP + INTERVAL '2 hours',
    (GiaHienTai, MaLuotDanDau) = (SELECT SoTien, MaLuotTraGia FROM LUOTTRAGIA
                                  WHERE MaPhien = %(p)s ORDER BY SoTien DESC, MaLuotTraGia LIMIT 1)
WHERE MaPhien = %(p)s AND NOT EXISTS (SELECT 1 FROM KETQUADAUGIA k WHERE k.MaPhien = %(p)s);
-- 3) cho mã lượt mới chạy tiếp từ mã lớn nhất hiện có
SELECT setval(pg_get_serial_sequence('luottragia', 'maluottragia'),
              (SELECT MAX(MaLuotTraGia) FROM LUOTTRAGIA));
COMMIT;"""
    steps = []
    with GEN_LOCK:
        c = gconn()
        for s in sqlfile.split_sql(sql):
            st = run(c, s["sql"], {"p": pid} if "%(p)s" in s["sql"] else None)
            steps.append(st)
            if "error" in st:
                run(c, "ROLLBACK")
                break
    return payload("helper", f"Đặt lại phiên #{pid} cho thử nghiệm 2 tab", steps, explain=EXPLAIN["lab_reset"])


@app.get("/api/source/<name>")
def api_source(name):
    return jsonify(func_source(name, KEY_LINES.get(name.lower(), [])))


@app.get("/api/explain")
def api_explain():
    return jsonify({"funcs": FUNCS, "key_lines": KEY_LINES})


if __name__ == "__main__":
    ensure_db()
    print(f"Website: http://127.0.0.1:5019  (database: {DB})")
    app.run(host="127.0.0.1", port=5019, debug=False, threaded=True)

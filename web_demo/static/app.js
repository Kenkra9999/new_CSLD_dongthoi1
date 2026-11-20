/* Đấu Giá 19 – giao diện mô phỏng. Mọi thao tác gọi API Flask, API chạy SQL thật trên PostgreSQL. */
"use strict";

// ------------------------------------------------------------------ tiện ích
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (v) => (v === null || v === undefined || v === "") ? "—" : Number(v).toLocaleString("vi-VN") + " đ";
const fmtTime = (iso) => { if (!iso) return "—"; const d = new Date(iso); return d.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit", day: "2-digit", month: "2-digit" }); };
const uuid4 = () => (crypto.randomUUID ? crypto.randomUUID() : "xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx".replace(/x/g, () => (Math.random() * 16 | 0).toString(16)));
const obj = (cols, row) => Object.fromEntries(cols.map((c, i) => [c, row[i]]));
const rowsOf = (step) => (step && step.rows ? step.rows.map((r) => obj(step.columns, r)) : []);
const STATUS_VI = { DANG_DIEN_RA: "Đang diễn ra", CHUA_MO: "Chưa mở", DA_DONG: "Đã chốt", THAT_BAI: "Thất bại", DA_DUYET: "Đã duyệt", CHO_DUYET: "Chờ duyệt", TU_CHOI: "Từ chối" };
const TYPE_VI = { TACPHAMNGHETHUAT: "Tác phẩm nghệ thuật", DOSUUTAM: "Đồ sưu tầm", THIETBIDIENTU: "Thiết bị điện tử" };

async function api(method, path, body) {
  const r = await fetch(path, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  let d; try { d = await r.json(); } catch { d = { error: "Máy chủ trả về dữ liệu không đọc được (HTTP " + r.status + ")" }; }
  if (!r.ok && !d.steps) throw new Error(d.error || ("HTTP " + r.status));
  return d;
}
function toast(msg, kind = "") {
  const el = document.createElement("div"); el.className = kind; el.textContent = msg;
  $("#toast").appendChild(el); setTimeout(() => el.remove(), 4200);
}

// ------------------------------------------------------------------ tô màu SQL
const KW = new Set(("SELECT FROM WHERE AND OR NOT IN IS NULL AS JOIN LEFT RIGHT INNER OUTER ON INSERT INTO VALUES UPDATE SET DELETE RETURNING " +
  "BEGIN COMMIT ROLLBACK CREATE OR REPLACE FUNCTION RETURNS TABLE LANGUAGE DECLARE IF THEN ELSE ELSIF END LOOP FOR EXCEPTION WHEN RAISE " +
  "RETURN PERFORM FOUND WITH RECURSIVE UNION ALL GROUP BY ORDER ASC DESC LIMIT OFFSET CASE DISTINCT EXISTS COALESCE COUNT MAX MIN SUM ROUND " +
  "OVER PARTITION WINDOW LAG LEAD ROW_NUMBER DENSE_RANK ROLLUP GROUPING FILTER DROP CASCADE PRIMARY KEY FOREIGN REFERENCES CONSTRAINT CHECK " +
  "UNIQUE DEFAULT GENERATED ALWAYS IDENTITY ALTER ADD DEFERRABLE INITIALLY DEFERRED TABLE EXISTS SHARE ISOLATION LEVEL SERIALIZABLE INTERVAL " +
  "CURRENT_TIMESTAMP EXECUTE USING QUERY LATERAL CROSS BETWEEN ILIKE LIKE OVERRIDING SYSTEM VALUE EXPLAIN ANALYZE DISTINCT ON TRUE FALSE " +
  "BIGINT INTEGER INT NUMERIC VARCHAR TEXT UUID TIMESTAMPTZ JSONB BOOLEAN TYPE ROWTYPE NAN SETVAL").split(/\s+/));
function hl(sql) {
  const re = /(--[^\n]*)|('(?:[^']|'')*')|(\$\$)|(\b\d+(?:\.\d+)?\b)|(\b(?:fn|pg)_\w+\b)|([A-Za-z_][A-Za-z_0-9]*)/g;
  let out = "", last = 0, m;
  while ((m = re.exec(sql))) {
    out += esc(sql.slice(last, m.index));
    const t = m[0];
    if (m[1]) out += `<span class="c">${esc(t)}</span>`;
    else if (m[2]) out += `<span class="s">${esc(t)}</span>`;
    else if (m[3]) out += `<span class="k">${t}</span>`;
    else if (m[4]) out += `<span class="n">${t}</span>`;
    else if (m[5]) out += `<span class="f">${esc(t)}</span>`;
    else out += KW.has(t.toUpperCase()) ? `<span class="k">${esc(t)}</span>` : esc(t);
    last = re.lastIndex;
  }
  return out + esc(sql.slice(last));
}

// ------------------------------------------------------------------ bảng SQL (console)
let entrySeq = 0;
function tableHTML(cols, rows, max = 60) {
  if (!cols) return "";
  if (!rows.length) return `<div class="muted small">(0 dòng)</div>`;
  const shown = rows.slice(0, max);
  return `<div class="tablewrap"><table class="grid"><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
    shown.map((r) => `<tr>${r.map((v) => `<td class="${typeof v === "number" ? "num" : ""}">${fmtCell(v)}</td>`).join("")}</tr>`).join("") +
    `</tbody></table></div>${rows.length > max ? `<div class="muted small">… còn ${rows.length - max} dòng</div>` : ""}`;
}
function fmtCell(v) {
  if (v === null || v === undefined) return '<span class="muted">NULL</span>';
  if (typeof v === "object") return esc(JSON.stringify(v));
  if (typeof v === "boolean") return v ? "true" : "false";
  return esc(v);
}
function stepHTML(s, eid) {
  const where = s.error && s.error.where;
  return `<div class="step">
    ${s.title ? `<div class="step-title">${esc(s.title)}</div>` : ""}
    <pre class="code">${hl(s.sql)}</pre>
    <div class="meta">${s.status ? `<span>Kết quả: <b>${esc(s.status)}</b></span>` : ""}
      ${s.ms !== undefined ? `<span>Thời gian: <b>${s.ms} ms</b></span>` : ""}
      ${s.tx ? `<span>Trạng thái giao dịch sau lệnh: <b>${esc(s.tx)}</b></span>` : ""}</div>
    ${(s.notices || []).map((n) => `<div class="notice">${esc(n)}</div>`).join("")}
    ${s.error ? `<div class="err"><b>LỖI ${esc(s.error.sqlstate || "")}:</b> ${esc(s.error.message)}
        ${s.error.detail ? `<div>Chi tiết: ${esc(s.error.detail)}</div>` : ""}
        ${s.error.context ? `<div class="small">Ngữ cảnh: ${esc(s.error.context)}</div>` : ""}
        ${where ? `<div class="where" onclick="jumpLine(${eid}, ${where.file_line})">→ Lỗi phát sinh ở dòng ${where.func_line} của hàm ${esc(where.func)} = dòng ${where.file_line} trong queries.sql (bấm để xem)</div>` : ""}
      </div>` : ""}
    ${s.columns ? tableHTML(s.columns, s.rows || []) : ""}
  </div>`;
}
function explainHTML(e) {
  if (!e) return "";
  return `<div class="explain"><b>${esc(e.what)}</b>${e.how && e.how.length ? `<ul>${e.how.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}${e.note ? `<div class="note">💡 ${esc(e.note)}</div>` : ""}</div>`;
}
function sourceHTML(src, eid, waitLine) {
  if (!src) return "";
  const notes = {}, hls = new Set();
  (src.highlight || []).forEach((h) => { for (let i = h.a; i <= h.b; i++) hls.add(i); notes[h.b] = h.note; });
  return `<details ${src.error_line || waitLine ? "open" : ""}><summary>📄 Mã nguồn hàm ${esc(src.name)} – ${esc(src.file)} (dòng thật, tô vàng = dòng quan trọng${src.error_line ? ", tô đỏ = dòng gây lỗi" : ""})</summary>
    <div class="src">${src.lines.map((l) => {
      const cls = l.no === src.error_line ? "err" : (l.no === waitLine ? "wait" : (hls.has(l.no) ? "hl" : ""));
      let html = `<div class="ln ${cls}" id="src-${eid}-${l.no}"><span>${l.no}</span><span>${hl(l.text)}</span></div>`;
      if (l.no === src.error_line) html += `<div class="note err">⛔ Dòng này đã RAISE EXCEPTION → cả giao dịch bị hủy, không có dữ liệu dở dang nào được lưu.</div>`;
      else if (notes[l.no]) html += `<div class="note">${esc(notes[l.no])}</div>`;
      return html;
    }).join("")}</div></details>`;
}
function ddlHTML(lines) {
  if (!lines) return "";
  return `<details><summary>📄 Cấu trúc bảng trong DDL_HeThongDauGia.sql (dòng ${lines[0].no}–${lines[lines.length - 1].no})</summary>
    <div class="src">${lines.map((l) => `<div class="ln"><span>${l.no}</span><span>${hl(l.text)}</span></div>`).join("")}</div></details>`;
}
const KIND_VI = { func: "Gọi hàm có sẵn trong queries.sql", file: "Chạy nguyên văn từ file .sql", gen: "SQL do website sinh theo cấu trúc DDL", helper: "Công cụ hỗ trợ demo", lab: "Thử nghiệm 2 tab" };
function addEntry(d, waitLine) {
  const eid = ++entrySeq;
  const el = document.createElement("div");
  const bad = d.steps && d.steps.some((s) => s.error);
  el.className = "entry new";
  el.innerHTML = `<div class="entry-head"><span class="kind ${d.kind}">${KIND_VI[d.kind] || d.kind}</span><span class="t">${esc(d.title)}</span>
      ${d.steps ? `<span class="pill ${bad ? "bad" : "ok"}">${bad ? "Có lỗi" : "Thành công"}</span>` : ""}<time>${esc(d.at || new Date().toLocaleTimeString("vi-VN"))}</time></div>
    <div class="entry-body">${explainHTML(d.explain)}${(d.steps || []).map((s) => stepHTML(s, eid)).join("")}${sourceHTML(d.source, eid, waitLine)}${ddlHTML(d.ddl)}</div>`;
  const list = $("#consoleList");
  const empty = $(".empty", list); if (empty) empty.remove();
  list.prepend(el);
  $("#console").scrollTop = 0;
  while (list.children.length > 60) list.lastChild.remove();
  return el;
}
window.jumpLine = (eid, line) => {
  const el = document.getElementById(`src-${eid}-${line}`);
  if (el) { el.closest("details").open = true; el.scrollIntoView({ behavior: "smooth", block: "center" }); }
};

// ------------------------------------------------------------------ khung chung
const S = { users: [], cats: [], assets: [], credits: {}, who: Number(localStorage.getItem("who") || 8), page: "setup", session: null, offset: 0 };

function go(page) {
  S.page = page;
  $$("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  $$(".page").forEach((p) => p.classList.toggle("active", p.id === "page-" + page));
  if (page === "market") loadSessions();
  if (page === "lab") labStart(); else labStop();
  if (page === "queries" && !$("#page-queries").dataset.ready) initQueries();
  if (page === "docs") initDocs();
  location.hash = page;
}
async function refreshStatus() {
  try {
    const s = await api("GET", "/api/status");
    const p = $("#dbpill");
    if (!s.ok) { p.className = "pill bad"; p.textContent = "Lỗi kết nối DB"; return s; }
    if (!s.tables) { p.className = "pill warn"; p.textContent = `${s.db}: chưa có bảng`; }
    else if (!s.sessions) { p.className = "pill warn"; p.textContent = `${s.db}: chưa có dữ liệu (chạy seed)`; }
    else if (!s.functions) { p.className = "pill warn"; p.textContent = `${s.db}: chưa có hàm`; }
    else { p.className = "pill ok"; p.textContent = `${s.db}: ${s.sessions} phiên · sẵn sàng`; }
    S.status = s; return s;
  } catch (e) { $("#dbpill").textContent = "Mất kết nối máy chủ"; }
}
async function loadMeta() {
  try {
    const m = await api("GET", "/api/meta");
    S.users = m.users; S.cats = m.cats; S.assets = m.assets;
  } catch { S.users = []; }
  const sel = $("#whoami");
  sel.innerHTML = S.users.length ? S.users.map((u) => `<option value="${u[0]}">#${u[0]} ${esc(u[1])}</option>`).join("") : `<option>(chưa có dữ liệu)</option>`;
  sel.value = S.who;
}
const userName = (id) => { const u = S.users.find((x) => x[0] === Number(id)); return u ? u[1] : "#" + id; };
function imgURL(aid) { return `/static/img/assets/${aid}.jpg`; }
function imgStyle(aid) { return `background-image:url('${imgURL(aid)}')`; }

// ------------------------------------------------------------------ ① KHỞI TẠO
async function initSetup() {
  const f = await api("GET", "/api/files");
  S.files = f;
  const card = (key, no) => {
    const x = f[key], e = f.explain[key];
    return `<div class="card file-card"><div class="row"><span class="num">${no}</span><div class="grow"><h3>${esc(x.name)}</h3>
      <div class="muted small">${x.lines} dòng · ${x.statements.length} câu lệnh</div></div>
      <button class="btn brand" onclick="runFile('${key}')">▶ Chạy cả file (như F5)</button></div>
      <p class="small">${esc(e.what)}</p>
      <details><summary>Xem ${x.statements.length} câu lệnh của file</summary>
        ${x.statements.map((s) => `<div class="stmt"><div class="lines">Dòng ${s.line_start}–${s.line_end}</div><pre class="code">${hl(s.sql)}</pre></div>`).join("")}
      </details></div>`;
  };
  $("#page-setup").innerHTML = `<h1>① Khởi tạo cơ sở dữ liệu</h1>
    <p class="lead">Chạy đúng thứ tự như đồ án quy định: <b>DDL → seed → queries → test_cases</b>. Mỗi nút chạy <b>nguyên văn</b> nội dung file trong thư mục đồ án vào database
    <code>daugia_web</code>, từng câu một, và hiện kết quả từng câu ở <b>Bảng SQL</b> bên phải. File <code>test_cases.sql</code> được chạy <b>từng câu</b> như hướng dẫn ở đầu file.</p>
    <div class="files">${card("ddl", "1")}${card("seed", "2")}${card("queries", "3")}</div>
    <h2>4 · test_cases.sql – chạy từng câu</h2>
    <div class="hint">Không chạy cả file một lần: file có các ca <b>cố tình gây lỗi</b> (test 3.x). Khi gọi cả file, PostgreSQL coi là một giao dịch ngầm nên lỗi đầu tiên sẽ hủy hết.
    Câu nào gọi hàm thì Bảng SQL hiện luôn mã nguồn hàm; nếu lỗi, <b>dòng RAISE gây lỗi được tô đỏ</b>.</div>
    <div class="card">${f.test.sections.map((sec) => `<div class="section-title">${esc(sec.title)}</div>` +
      sec.items.map((s) => `<div class="stmt"><div class="lines">Dòng ${s.line_start}–${s.line_end}<br><button class="btn sm brand" style="margin-top:6px" onclick="runStmt('test', ${s.index})">▶ Chạy</button></div><pre class="code">${hl(s.sql)}</pre></div>`).join("")).join("")}</div>`;
}
window.runFile = async (key) => {
  toast("Đang chạy " + S.files[key].name + " …");
  const d = await api("POST", "/api/run_file", { file: key });
  addEntry(d);
  toast(d.ok ? `✔ ${S.files[key].name}: chạy xong ${d.steps.length} câu` : `✖ ${S.files[key].name}: có lỗi, xem Bảng SQL`, d.ok ? "ok" : "bad");
  await refreshStatus(); await loadMeta();
};
window.runStmt = async (key, idx) => {
  const d = await api("POST", "/api/run_stmt", { file: key, index: idx });
  addEntry(d);
  const bad = d.steps.some((s) => s.error);
  toast(bad ? "✖ " + d.steps[0].error.message : "✔ " + (d.steps[0].status || "Xong"), bad ? "bad" : "ok");
};

// ------------------------------------------------------------------ ② SÀN ĐẤU GIÁ
function catOptions() {
  const kids = (pid) => S.cats.filter((c) => c[2] === pid);
  const walk = (pid, lv) => kids(pid).map((c) => `<option value="${c[0]}">${"— ".repeat(lv)}${esc(c[1])}</option>` + walk(c[0], lv + 1)).join("");
  return walk(null, 0);
}
function marketShell() {
  $("#page-market").innerHTML = `<div id="marketList"><div class="row"><div class="grow"><h1>② Sàn đấu giá</h1>
      <p class="lead">Danh sách lấy bằng hàm có sẵn <code>fn_BaoCaoPhienDauGiaDong</code>. Mỗi ô lọc trở thành một tham số của hàm (SQL động).</p></div>
      <button class="btn brand" onclick="openCreate()">＋ Mở phiên mới</button></div>
    <div class="filters card">
      <label class="field">Nhánh danh mục (đệ quy)<select id="fDm"><option value="">Tất cả</option>${catOptions()}</select></label>
      <label class="field">Trạng thái<select id="fTt"><option value="">Tất cả</option>${Object.keys(STATUS_VI).slice(0, 4).map((k) => `<option value="${k}">${STATUS_VI[k]}</option>`).join("")}</select></label>
      <label class="field">Loại tài sản<select id="fLoai"><option value="">Tất cả</option>${Object.entries(TYPE_VI).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></label>
      <label class="field">Giá từ<input id="fGiaTu" type="number" placeholder="vd 1000000"></label>
      <label class="field">Giá đến<input id="fGiaDen" type="number"></label>
      <label class="field">Từ khóa tên<input id="fKw" placeholder="vd: leica"></label>
      <button class="btn" onclick="loadSessions()">Lọc</button><button class="btn light" onclick="clearFilters()">Xóa lọc</button>
    </div><div id="lots" class="cards"></div></div><div id="marketDetail"></div>`;
}
window.clearFilters = () => { ["fDm", "fTt", "fLoai", "fGiaTu", "fGiaDen", "fKw"].forEach((i) => $("#" + i).value = ""); loadSessions(); };
async function loadSessions() {
  if (!S.status || !S.status.functions) {
    $("#page-market").innerHTML = `<h1>② Sàn đấu giá</h1><div class="hint bad">Database chưa sẵn sàng. Hãy vào <b>① Khởi tạo CSDL</b> và chạy lần lượt 3 file DDL → seed → queries.</div>`;
    return;
  }
  if (!$("#lots")) marketShell();
  $("#marketList").style.display = ""; $("#marketDetail").innerHTML = "";
  const q = new URLSearchParams({ dm: $("#fDm").value, tt: $("#fTt").value, loai: $("#fLoai").value, giatu: $("#fGiaTu").value, giaden: $("#fGiaDen").value, tukhoa: $("#fKw").value });
  const d = await api("GET", "/api/sessions?" + q);
  addEntry(d);
  const rows = rowsOf(d.steps[0]);
  $("#lots").innerHTML = rows.length ? rows.map(lotCard).join("") : `<div class="muted">Không có phiên nào khớp bộ lọc.</div>`;
  tickCountdowns();
}
function lotCard(r) {
  const price = r.giahientai ?? r.giakhoidiem;
  return `<div class="lot" onclick="openSession(${r.maphien})">
    <div class="img" style="${imgStyle(r.mataisan)}"><span class="badge ${r.trangthaiphien}">${STATUS_VI[r.trangthaiphien] || r.trangthaiphien}</span><span class="no">Phiên #${r.maphien}</span></div>
    <div class="body"><div class="name">${esc(r.tentaisan)}</div><div class="cat">${esc(TYPE_VI[r.loaitaisan] || r.loaitaisan)} · ${esc(r.tendanhmuc)}</div>
      <div class="price">${money(price)}</div>
      <div class="small muted">${r.giahientai ? "Giá hiện tại · " + r.soluottragia + " lượt · dẫn đầu: " + esc(r.nguoidandau || "—") : "Giá khởi điểm · chưa có lượt"}</div>
      <div class="foot"><span>Người bán: ${esc(r.nguoiban)}</span><span class="countdown" data-start="${r.thoidiemmo}" data-end="${r.thoidiemdong}" data-st="${r.trangthaiphien}"></span></div></div></div>`;
}
function tickCountdowns() {
  const now = Date.now() + S.offset;
  $$(".countdown").forEach((el) => {
    const st = el.dataset.st, start = new Date(el.dataset.start).getTime(), end = new Date(el.dataset.end).getTime();
    if (st === "DA_DONG" || st === "THAT_BAI") { el.textContent = "Kết thúc " + fmtTime(el.dataset.end); return; }
    if (now < start) { el.textContent = "Mở sau " + dur(start - now); return; }
    el.textContent = now < end ? "⏱ Còn " + dur(end - now) : "⌛ Đã quá giờ đóng – chờ chốt";
    el.style.color = now < end && end - now < 5 * 60e3 ? "var(--bad)" : "";
  });
}
const dur = (ms) => { const s = Math.floor(ms / 1000), d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60), x = s % 60; return (d ? d + " ngày " : "") + String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + ":" + String(x).padStart(2, "0"); };
setInterval(tickCountdowns, 1000);

window.openSession = async (id, quiet = false) => {
  const d = await api("GET", "/api/session/" + id);
  if (!quiet) addEntry(d);
  const s = rowsOf(d.steps[0])[0];
  if (!s) { toast("Không tìm thấy phiên", "bad"); return; }
  S.session = id;
  S.offset = new Date(s.baygio).getTime() - Date.now();
  const hist = rowsOf(d.steps[1]), regs = rowsOf(d.steps[2]), res = rowsOf(d.steps[3]), logs = rowsOf(d.steps[4]);
  const minNext = s.giahientai ? Number(s.giahientai) + Number(s.buocgia) : Number(s.giakhoidiem);
  const cr = S.credits[s.mataisan];
  const attrs = s.loaitaisan === "TACPHAMNGHETHUAT" ? [["Tác giả", s.tacgia], ["Chất liệu", s.chatlieu], ["Năm sáng tác", s.namsangtac]]
    : s.loaitaisan === "DOSUUTAM" ? [["Nguồn gốc", s.nguongoc], ["Độ hiếm", s.dohiem], ["Năm sản xuất", s.namsanxuat]]
    : [["Thương hiệu", s.thuonghieu], ["Màu", s.mauthietbi], ["Số sê-ri", s.soseri], ["Tình trạng", s.tinhtrang]];
  const sub = { TACPHAMNGHETHUAT: "TACPHAMNGHETHUAT", DOSUUTAM: "DOSUUTAM", THIETBIDIENTU: "THIETBIDIENTU" }[s.loaitaisan];
  const me = S.who, myReg = regs.find((r) => r.manguoidung === me);
  $("#marketList").style.display = "none";
  $("#marketDetail").innerHTML = `<button class="btn light" onclick="loadSessions()">← Về danh sách</button>
   <h1 style="margin-top:12px">${esc(s.tentaisan)} <span class="badge ${s.trangthaiphien}">${STATUS_VI[s.trangthaiphien]}</span></h1>
   <div class="muted">Phiên #${s.maphien} · Tài sản #${s.mataisan} · ${esc(TYPE_VI[s.loaitaisan])} · ${esc(s.tendanhmuc)} · Người bán: <b>${esc(s.nguoiban)}</b> (#${s.manguoiban})</div>
   <div class="detail" style="margin-top:14px">
    <div>
      <div class="gallery" style="${imgStyle(s.mataisan)}"></div>
      <div class="credit">${cr ? `Ảnh minh họa: <a href="${esc(cr.page)}" target="_blank" rel="noopener">${esc(cr.title)}</a> · ${esc(cr.author || "?")} · ${esc(cr.license)} · nguồn ${esc(new URL(cr.page).hostname)}` : "Ảnh minh họa"}</div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">Thông tin tài sản</h3>
        <p class="small">${esc(s.mota)}</p>
        <div class="kv">${attrs.map(([k, v]) => `<div>${k}</div><div><b>${esc(v ?? "—")}</b></div>`).join("")}</div>
        <div class="hint info small">Thuộc tính trên nằm ở bảng con <code>${sub}</code> (chuyên biệt hóa EER). Khóa chính bảng con chính là <code>MaTaiSan</code>, tham chiếu <code>TAISAN</code>.</div></div>
    </div>
    <div>
      <div class="card">
        <div class="row"><div class="grow"><div class="muted small">${s.giahientai ? "Giá hiện tại (lưu trong PHIENDAUGIA.GiaHienTai)" : "Giá khởi điểm (chưa có lượt)"}</div>
          <div class="bigprice">${money(s.giahientai ?? s.giakhoidiem)}</div>
          <div class="small">Bước giá <b>${money(s.buocgia)}</b> · Giá khởi điểm ${money(s.giakhoidiem)} · Phiên bản <b>${s.phienban}</b> · Lượt dẫn đầu <b>${s.maluotdandau ?? "—"}</b></div></div>
          <div style="text-align:right"><div class="countdown" data-start="${s.thoidiemmo}" data-end="${s.thoidiemdong}" data-st="${s.trangthaiphien}"></div>
          <div class="small muted">Mở ${fmtTime(s.thoidiemmo)}<br>Đóng ${fmtTime(s.thoidiemdong)}</div></div></div>
      </div>
      <div class="bidbox" style="margin-top:12px"><h3 style="margin-top:0">Trả giá</h3>
        <div class="row"><label class="field">Người trả giá<select id="bUser">${S.users.map((u) => `<option value="${u[0]}" ${u[0] === me ? "selected" : ""}>#${u[0]} ${esc(u[1])}</option>`).join("")}</select></label>
          <label class="field grow">Số tiền (tối thiểu ${money(minNext)})<input id="bAmt" type="number" value="${minNext}" step="${Number(s.buocgia)}"></label></div>
        <div class="methods" style="margin-top:8px">
          <label class="sel"><input type="radio" name="bm" value="fn_TraGia" checked><b>Phương án 1</b> · fn_TraGia<br><span class="muted small">khóa dòng SELECT … FOR UPDATE</span></label>
          <label><input type="radio" name="bm" value="fn_TraGia_Serializable"><b>Phương án 2</b> · fn_TraGia_Serializable<br><span class="muted small">đọc không khóa (có lỗi khi chạy đồng thời)</span></label></div>
        <div class="row" style="margin-top:8px"><label class="field grow">Mã yêu cầu (UUID – chống gửi trùng)<input id="bUuid" class="mono" value="${uuid4()}"></label>
          <button class="btn sm light" onclick="$('#bUuid').value=uuid4()">Mã mới</button></div>
        <div class="row" style="margin-top:10px"><button class="btn brand" onclick="doBid()">🔨 Trả giá</button>
          <button class="btn light" id="btnResend" onclick="doBid(true)" ${S.lastBid && S.lastBid.phien === id ? "" : "disabled"}>🔁 Gửi lại đúng yêu cầu vừa gửi</button></div>
        <div class="small muted" style="margin-top:6px">Mỗi lần bấm, website gọi <code>SELECT fn_…(phiên, người, số tiền, mã yêu cầu)</code> → xem câu SQL thật và đường đi trong mã nguồn hàm ở Bảng SQL.</div>
      </div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">Đăng ký tham gia &amp; duyệt</h3>
        <div class="row"><span class="grow small">Bạn đang là <b>${esc(userName(me))}</b>: ${myReg ? `đã đăng ký – <span class="badge ${myReg.trangthaidangky}">${STATUS_VI[myReg.trangthaidangky] || myReg.trangthaidangky}</span>` : "chưa đăng ký phiên này"}</span>
          <button class="btn sm" onclick="doRegister()">📝 Đăng ký tham gia</button></div>
        <div style="margin-top:8px">${regs.length ? `<table class="grid"><tr><th>Người dùng</th><th>Trạng thái</th><th>Lúc đăng ký</th><th>Duyệt (người bán / quản trị)</th></tr>${regs.map((r) => `<tr>
          <td>#${r.manguoidung} ${esc(r.hoten)}</td><td><span class="badge ${r.trangthaidangky}">${STATUS_VI[r.trangthaidangky] || r.trangthaidangky}</span></td><td>${fmtTime(r.thoidiemdangky)}</td>
          <td><button class="btn sm ok" onclick="doApprove(${r.manguoidung},'DA_DUYET')">Duyệt</button> <button class="btn sm bad" onclick="doApprove(${r.manguoidung},'TU_CHOI')">Từ chối</button></td></tr>`).join("")}</table>` : `<div class="muted small">Chưa có đăng ký.</div>`}</div>
      </div>
      <div class="card" style="margin-top:12px"><h3 style="margin-top:0">Điều khiển phiên</h3>
        <div class="row"><button class="btn bad" onclick="doClose()">🔒 Đóng phiên (fn_DongPhienDauGia)</button>
          <button class="btn gray" onclick="doTime('end')">⏩ Tua tới giờ đóng</button>
          <button class="btn gray" onclick="doTime('extend')">🔄 Gia hạn 2 giờ (Bước 0)</button></div>
        <div class="small muted" style="margin-top:6px">Hai nút xám là công cụ hỗ trợ demo (không phải nghiệp vụ), câu SQL vẫn hiện đầy đủ.</div>
        ${res.length ? `<div class="hint good" style="margin-top:10px"><b>Kết quả (KETQUADAUGIA):</b> ${res[0].maluotthang ? `người thắng <b>${esc(res[0].nguoithang)}</b> – lượt #${res[0].maluotthang} – giá <b>${money(res[0].giathang)}</b>` : "không có người thắng (MaLuotThang = NULL)"} · chốt ${fmtTime(res[0].thoidiemchot)}</div>` : ""}
      </div>
    </div></div>
   <div class="tabs2"><button class="active" data-t="h">Lịch sử trả giá (${hist.length})</button><button data-t="l">Nhật ký thay đổi (${logs.length})</button></div>
   <div id="tab-h">${hist.length ? `<table class="grid"><tr><th>Lượt</th><th>Người trả giá</th><th>Số tiền</th><th>Mức tăng (LAG)</th><th>Lúc chấp nhận</th><th>Mã yêu cầu</th></tr>${hist.map((h) => `<tr ${h.maluottragia === s.maluotdandau ? 'style="background:#fff3e6;font-weight:600"' : ""}>
      <td>#${h.maluottragia}${h.maluottragia === s.maluotdandau ? " 👑" : ""}</td><td>${esc(h.nguoitragia)}</td><td class="num">${money(h.sotien)}</td><td class="num">${h.muctang ? "+" + money(h.muctang) : "—"}</td><td>${fmtTime(h.thoidiemchapnhan)}</td><td class="mono small">${esc(h.mayeucau)}</td></tr>`).join("")}</table>` : `<div class="muted">Chưa có lượt trả giá.</div>`}</div>
   <div id="tab-l" style="display:none">${logs.length ? `<table class="grid"><tr><th>#</th><th>Hành động</th><th>Tác nhân</th><th>Chi tiết (JSONB)</th><th>Lúc</th><th>Mã giao dịch</th></tr>${logs.map((l) => `<tr><td>${l.manhatky}</td><td>${esc(l.hanhdong)}</td><td>${l.matacnhan ?? "hệ thống"}</td><td class="mono small">${esc(JSON.stringify(l.chitiet))}</td><td>${fmtTime(l.thoidiemghi)}</td><td>${l.magiaodich}</td></tr>`).join("")}</table>` : ""}</div>`;
  $$(".tabs2 button").forEach((b) => b.onclick = () => { $$(".tabs2 button").forEach((x) => x.classList.toggle("active", x === b)); $("#tab-h").style.display = b.dataset.t === "h" ? "" : "none"; $("#tab-l").style.display = b.dataset.t === "l" ? "" : "none"; });
  $$(".methods input").forEach((i) => i.onchange = () => $$(".methods label").forEach((l) => l.classList.toggle("sel", $("input", l).checked)));
  if (S.lastBid && S.lastBid.phien === id) { $$(".methods input").forEach((i) => { i.checked = i.value === S.lastBid.method; i.onchange(); }); }
  tickCountdowns();
  window.scrollTo(0, 0); $("#main").scrollTop = 0;
};
window.doBid = async (resend) => {
  const body = resend ? S.lastBid : { phien: S.session, user: Number($("#bUser").value), amount: Number($("#bAmt").value), method: $("input[name=bm]:checked").value, uuid: $("#bUuid").value.trim() };
  const d = await api("POST", "/api/bid", body);
  if (resend) d.title = "🔁 GỬI LẠI cùng mã yêu cầu – " + d.title;
  addEntry(d);
  S.lastBid = { ...body, uuid: d.uuid };
  if (d.ok) toast((resend ? "Gửi lại: hàm trả về lượt #" : "✔ Trả giá thành công – lượt #") + d.result + (resend ? " (không tạo lượt mới)" : ""), "ok");
  else toast("✖ " + d.steps.find((s) => s.error).error.message, "bad");
  await openSession(S.session, true);
  if (!resend) $("#bUuid").value = uuid4();
};
window.doRegister = async () => { const d = await api("POST", "/api/register", { phien: S.session, user: S.who }); addEntry(d); toast(d.ok ? "✔ Đã gửi đăng ký – đang chờ duyệt" : "✖ " + d.steps[0].error.message, d.ok ? "ok" : "bad"); openSession(S.session, true); };
window.doApprove = async (u, st) => { const d = await api("POST", "/api/approve", { phien: S.session, user: u, status: st }); addEntry(d); toast(d.ok ? "✔ Đã cập nhật đăng ký" : "✖ Lỗi", d.ok ? "ok" : "bad"); openSession(S.session, true); };
window.doClose = async () => { const d = await api("POST", "/api/close", { phien: S.session }); addEntry(d); toast(d.ok ? "✔ Đã chốt phiên" : "✖ " + d.steps[0].error.message, d.ok ? "ok" : "bad"); await refreshStatus(); openSession(S.session, true); };
window.doTime = async (mode) => { const d = await api("POST", "/api/time", { phien: S.session, mode }); addEntry(d); const ok = d.ok && d.steps[0].rowcount > 0; toast(ok ? "✔ Đã cập nhật giờ phiên" : "Không có dòng nào thay đổi (xem Bảng SQL)", ok ? "ok" : "bad"); openSession(S.session, true); };
window.openCreate = () => {
  const free = S.assets.filter((a) => !a[5]);
  openModal(`<h3>Mở phiên đấu giá mới</h3><p class="small muted">Chọn tài sản chưa có phiên đang chạy. Website sinh câu INSERT vào PHIENDAUGIA, và các CHECK trong DDL sẽ kiểm tra dữ liệu.</p>
    <label class="field">Tài sản<select id="cA">${free.map((a) => `<option value="${a[0]}">#${a[0]} ${esc(a[1])} (người bán: ${esc(a[4])})</option>`).join("")}</select></label>
    <div class="row" style="margin-top:8px"><label class="field grow">Giá khởi điểm<input id="cS" type="number" value="10000000"></label><label class="field grow">Bước giá<input id="cB" type="number" value="500000"></label><label class="field">Kéo dài (giờ)<input id="cH" type="number" value="24"></label></div>
    <div class="hint small">Thử nhập bước giá = 0 để thấy PostgreSQL từ chối vì CHECK <code>ck_phiendaugia_buocgia</code>.</div>
    <button class="btn brand" onclick="doCreate()">Mở phiên</button>`);
};
window.doCreate = async () => {
  const d = await api("POST", "/api/create_session", { asset: Number($("#cA").value), start: Number($("#cS").value), step: Number($("#cB").value), hours: Number($("#cH").value) });
  addEntry(d);
  if (d.ok) { closeModal(); toast("✔ Đã mở phiên #" + d.result, "ok"); await loadMeta(); await refreshStatus(); openSession(d.result); }
  else toast("✖ " + d.steps[0].error.message, "bad");
};
function openModal(html) { $("#modalBody").innerHTML = html; $("#modal").classList.remove("hidden"); }
window.closeModal = () => $("#modal").classList.add("hidden");

// ------------------------------------------------------------------ ③ THỬ NGHIỆM 2 TAB
const L = { timer: null, seen: { A: null, B: null }, last: null, timeline: [] };
function labShell() {
  $("#page-lab").innerHTML = `<h1>③ Thử nghiệm 2 tab – hai người trả giá cùng lúc</h1>
  <p class="lead">Hai khung dưới đây là <b>hai kết nối PostgreSQL thật, độc lập</b> (giống 2 tab Query Tool của pgAdmin). Kết nối giữ được giao dịch mở giữa các lần bấm, nên bạn có thể
  <code>BEGIN</code> ở tab A, chưa <code>COMMIT</code>, rồi sang tab B trả giá và <b>thấy tab B bị treo vì chờ khóa</b>. Bảng "Soi khóa" bên dưới tự cập nhật mỗi 0,8 giây.</p>
  <div class="card lab-cfg">
    <label class="field">Phiên<input id="lP" type="number" value="1" style="width:80px"></label>
    <label class="field">Người A<select id="lUA"></select></label><label class="field">Giá A<input id="lGA" type="number" value="6250000"></label>
    <label class="field">Người B<select id="lUB"></select></label><label class="field">Giá B<input id="lGB" type="number" value="6000000"></label>
    <label class="field">Hàm trả giá<select id="lFn"><option value="fn_TraGia_Serializable">Phương án 2 – fn_TraGia_Serializable</option><option value="fn_TraGia">Phương án 1 – fn_TraGia</option></select></label>
    <button class="btn gray" onclick="labReset()">↺ Đặt lại phiên</button>
  </div>
  <div class="hint small">Người A và B phải có đăng ký <b>đã duyệt</b> cho phiên (phiên 1: #7 và #8). Giá B thấp hơn giá A thì mới thấy lỗi của phương án 2.</div>
  <div class="steps-guide">
    <div class="sg"><b>Bước 1</b>Đặt lại phiên về trạng thái ban đầu<button class="btn sm gray" onclick="labReset()">Chạy</button></div>
    <div class="sg"><b>Bước 2</b>Tab A: BEGIN + trả giá, CHƯA commit<button class="btn sm" onclick="labPreset('A','begin',true)">Chạy</button></div>
    <div class="sg"><b>Bước 3</b>Tab B: trả giá thấp hơn → sẽ TREO<button class="btn sm" onclick="labPreset('B','auto',true)">Chạy</button></div>
    <div class="sg"><b>Bước 4</b>Đọc bảng "Soi khóa": B bị ai chặn? đã INSERT chưa?<button class="btn sm light" onclick="labSnapshot()">Ghi vào Bảng SQL</button></div>
    <div class="sg"><b>Bước 5</b>Tab A: COMMIT → B chạy tiếp<button class="btn sm" onclick="labPreset('A','commit',true)">Chạy</button></div>
    <div class="sg"><b>Bước 6</b>Đối soát: NHAT_QUAN hay SAI_LECH?<button class="btn sm light" onclick="labSnapshot(true)">Ghi vào Bảng SQL</button></div>
  </div>
  <div class="twotabs">${["A", "B"].map((t) => `<div class="tab" id="tab${t}">
     <div class="tab-head"><b>Tab ${t}</b><span class="muted small" id="pid${t}"></span><span class="st" id="st${t}"></span></div>
     <div class="presets">
       <button onclick="labPreset('${t}','begin')">BEGIN + trả giá</button><button onclick="labPreset('${t}','auto')">Trả giá (auto-commit)</button>
       <button onclick="labPreset('${t}','ser')">BEGIN SERIALIZABLE + trả giá</button><button onclick="labPreset('${t}','commit')">COMMIT</button>
       <button onclick="labPreset('${t}','rollback')">ROLLBACK</button><button onclick="labPreset('${t}','view')">Xem phiên</button></div>
     <textarea id="sql${t}" spellcheck="false"></textarea>
     <div class="run"><button class="btn brand sm" onclick="labRun('${t}')">▶ Chạy (F5)</button><button class="btn bad sm" id="cancel${t}" onclick="labCancel('${t}')" style="display:none">✖ Hủy lệnh đang chờ</button>
       <span class="small muted" id="hint${t}"></span></div>
     <div class="out" id="out${t}"></div></div>`).join("")}</div>
  <div class="monitor card"><div class="row"><h3 class="grow" style="margin:0">🔍 Soi khóa – ai đang chặn ai? (tự cập nhật)</h3><span id="verdict"></span></div>
    <div id="monText" style="margin:8px 0"></div><div id="monTable"></div>
    <details><summary>Câu SQL dùng để soi (pg_stat_activity + pg_locks)</summary><pre class="code" id="monSql"></pre></details>
    <h3>Đối soát &amp; lượt đã COMMIT <span class="muted small">(kết nối thứ ba, chỉ nhìn thấy dữ liệu đã COMMIT)</span></h3>
    <div class="row" style="align-items:flex-start"><div class="grow" id="chkTable"></div><div class="grow" id="bidTable"></div></div>
    <h3>Dòng thời gian</h3><div class="timeline" id="timeline"><div class="muted">Chưa có thao tác.</div></div></div>`;
  const opts = (sel) => S.users.map((u) => `<option value="${u[0]}" ${u[0] === sel ? "selected" : ""}>#${u[0]} ${esc(u[1])}</option>`).join("");
  $("#lUA").innerHTML = opts(8); $("#lUB").innerHTML = opts(7);
  labPreset("A", "begin"); labPreset("B", "auto");
}
function labSQL(t, kind) {
  const p = Number($("#lP").value), fn = $("#lFn").value;
  const u = Number($("#lU" + t).value), g = Number($("#lG" + t).value);
  const call = `${fn}(${p}, ${u}, ${g}, gen_random_uuid()) AS luot_cua_${t}`;
  return {
    begin: `-- Tab ${t}: mở giao dịch và trả giá, CHƯA COMMIT (giữ khóa)\nBEGIN;\nSELECT ${call};`,
    auto: `-- Tab ${t}: trả giá ở chế độ auto-commit (giống bấm F5 bình thường)\nSELECT current_setting('transaction_isolation') AS muc_co_lap,\n       ${call};`,
    ser: `-- Tab ${t}: SERIALIZABLE thật (đặt ở đầu giao dịch)\nBEGIN ISOLATION LEVEL SERIALIZABLE;\nSELECT current_setting('transaction_isolation') AS muc_co_lap,\n       ${call};`,
    commit: "COMMIT;", rollback: "ROLLBACK;",
    view: `SELECT MaPhien, GiaHienTai, MaLuotDanDau, PhienBan FROM PHIENDAUGIA WHERE MaPhien = ${p};`,
  }[kind];
}
window.labPreset = (t, kind, run) => { $("#sql" + t).value = labSQL(t, kind); if (run) labRun(t); };
window.labRun = async (t) => {
  const sql = $("#sql" + t).value;
  const label = sql.split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("--")).join(" ").replace(/\s+/g, " ").slice(0, 120) || sql;
  try { await api("POST", `/api/lab/${t}/exec`, { sql, label }); pushTL(t, "Gửi: " + label); }
  catch (e) { toast(e.message, "bad"); }
  labPoll();
};
window.labCancel = async (t) => { await api("POST", `/api/lab/${t}/cancel`); pushTL(t, "Gửi yêu cầu hủy lệnh đang chờ"); };
window.labReset = async () => { const d = await api("POST", "/api/lab/reset", { phien: Number($("#lP").value) }); addEntry(d); L.timeline = []; pushTL("", "Đặt lại phiên " + $("#lP").value); toast(d.steps.some((s) => s.error) ? "✖ Lỗi khi đặt lại" : "✔ Đã đặt lại phiên", d.steps.some((s) => s.error) ? "bad" : "ok"); labPoll(); };
window.labSnapshot = (chk) => {
  if (!L.last) return;
  addEntry({ kind: "lab", title: chk ? "Đối soát sau thử nghiệm" : "Ảnh chụp trạng thái khóa lúc này", steps: chk ? [L.last.check, L.last.bids] : [L.last.monitor],
    explain: chk ? { what: "So sánh giá lưu trong phiên với giá cao nhất trong lịch sử trả giá.", how: ["NHAT_QUAN = khớp. SAI_LECH = có lượt bị ghi đè (mất cập nhật)."] }
      : { what: "pg_stat_activity cho biết mỗi kết nối đang làm gì; pg_blocking_pids cho biết ai chặn ai; pg_locks cho biết đã ghi vào bảng nào.", how: monLines(L.last) } });
};
function pushTL(t, msg) { L.timeline.unshift({ t, msg, at: new Date().toLocaleTimeString("vi-VN") }); renderTL(); }
function renderTL() { $("#timeline").innerHTML = L.timeline.map((x) => `<div class="${x.t}"><b>${x.at}</b> ${x.t ? "Tab " + x.t + ": " : ""}${esc(x.msg)}</div>`).join("") || '<div class="muted">Chưa có thao tác.</div>'; }
function labStart() { if (!$("#tabA")) labShell(); labPoll(); clearInterval(L.timer); L.timer = setInterval(labPoll, 800); }
function labStop() { clearInterval(L.timer); L.timer = null; }
let polling = false;
async function labPoll() {
  if (polling || !$("#tabA")) return; polling = true;
  try {
    const s = await api("GET", "/api/lab/state?phien=" + Number($("#lP").value));
    L.last = s; renderLab(s);
  } catch (e) { /* bỏ qua */ } finally { polling = false; }
}
function monRows(s) { return rowsOf(s.monitor); }
function tabOfPid(s, pid) { return Object.values(s.tabs).find((t) => t.pid === pid); }
function monLines(s) {
  const out = [];
  monRows(s).forEach((r) => {
    const me = tabOfPid(s, r.pid); if (!me) return;
    const who = "Tab " + me.name;
    if (r.wait_event_type === "Lock") {
      const by = (r.bi_chan_boi || []).map((p) => (tabOfPid(s, p) ? "Tab " + tabOfPid(s, p).name : "pid " + p)).join(", ");
      out.push(`${who} (pid ${r.pid}) đang CHỜ KHÓA – bị chặn bởi ${by}. ` + (r.da_insert_luottragia ? "Nó ĐÃ INSERT lượt mới vào LUOTTRAGIA rồi mới phải chờ, tức là đã kiểm tra giá xong (chờ ở câu UPDATE)." : "Nó CHƯA ghi gì, tức là bị chặn ngay từ lúc đọc phiên (SELECT … FOR UPDATE)."));
    } else if (r.state === "idle in transaction") {
      out.push(`${who} (pid ${r.pid}) đang MỞ GIAO DỊCH chưa COMMIT được ${r.giay_trong_giao_dich}s` + (r.dang_dung_phiendaugia ? ", đang giữ khóa liên quan bảng PHIENDAUGIA" : "") + (r.da_insert_luottragia ? ", đã INSERT lượt mới (chưa ai khác nhìn thấy)." : "."));
    } else if (r.state === "idle in transaction (aborted)") {
      out.push(`${who} có giao dịch bị LỖI – phải ROLLBACK.`);
    } else {
      out.push(`${who} (pid ${r.pid}): ${r.state} – không giữ giao dịch.`);
    }
  });
  return out;
}
function renderLab(s) {
  ["A", "B"].forEach((t) => {
    const tab = s.tabs[t], mon = monRows(s).find((r) => r.pid === tab.pid);
    const waiting = tab.busy && mon && mon.wait_event_type === "Lock";
    $("#pid" + t).textContent = tab.pid ? "pid " + tab.pid : "";
    const el = $("#tab" + t);
    el.classList.toggle("waiting", !!waiting); el.classList.toggle("intrans", !tab.busy && tab.tx === "INTRANS");
    $("#st" + t).innerHTML = waiting ? `<span class="spinner"></span> Đang CHỜ KHÓA… ${tab.job.seconds}s`
      : tab.busy ? `<span class="spinner"></span> Đang chạy…` : tab.tx === "INTRANS" ? "🕒 Giao dịch đang mở (chưa COMMIT)"
      : tab.tx === "INERROR" ? "⚠ Giao dịch lỗi – cần ROLLBACK" : tab.tx === "IDLE" ? "✔ Rảnh" : esc(tab.tx);
    $("#cancel" + t).style.display = tab.busy ? "" : "none";
    let html = "";
    if (tab.busy) {
      const fn = $("#lFn").value, ser = fn === "fn_TraGia_Serializable";
      const line = mon && mon.da_insert_luottragia ? 317 : (ser ? 317 : 143);
      html = `<div class="waitbox"><b>⏳ Waiting for the query to complete…</b> (${tab.job.seconds}s)<br>${waiting ? (mon.da_insert_luottragia
          ? `Hàm đã chạy qua dòng 285 (đọc phiên KHÔNG khóa, thấy giá cũ), dòng 302 (kiểm tra giá: hợp lệ), dòng 313 (INSERT lượt mới) và đang <b>đứng chờ ở dòng ${line}</b> (UPDATE PHIENDAUGIA) vì tab kia giữ khóa dòng phiên.`
          : `Hàm đang <b>đứng chờ ở dòng 143</b> (SELECT … FOR UPDATE): chưa kiểm tra giá, chưa ghi gì. Khi tab kia COMMIT, nó sẽ đọc được giá MỚI NHẤT.`) : "Đang thực thi…"}</div>`;
    } else if (tab.history[0]) {
      const j = tab.history[0];
      html = `<div class="small muted">Lệnh gần nhất (${j.seconds}s):</div>` + j.steps.map((st) => st.error
        ? `<div class="err"><b>LỖI:</b> ${esc(st.error.message)}${st.error.where ? ` <span class="small">(dòng ${st.error.where.file_line} queries.sql)</span>` : ""}</div>`
        : `<div class="small"><code>${esc(st.status)}</code></div>${st.columns ? tableHTML(st.columns, st.rows || [], 10) : ""}`).join("");
    }
    $("#out" + t).innerHTML = html || '<div class="muted small">Chưa chạy lệnh nào.</div>';
    const sig = tab.history[0] ? tab.history[0].label + tab.history[0].seconds + tab.history.length : null;
    if (sig && L.seen[t] !== null && sig !== L.seen[t]) {
      const j = tab.history[0], err = j.steps.find((x) => x.error);
      pushTL(t, (err ? "✖ Lỗi: " + err.error.message : "✔ Xong") + ` sau ${j.seconds}s – ${j.label}`);
      const fn = (j.sql.match(/fn_\w+/) || [])[0];
      addEntry({ kind: "lab", title: `Tab ${t}: ${j.label} (${j.seconds}s)`, steps: j.steps,
        explain: { what: j.seconds > 1.5 ? `Lệnh này đã phải CHỜ ${j.seconds} giây vì tab kia giữ khóa, rồi mới chạy xong.` : "Lệnh chạy ngay, không phải chờ.", how: [] } });
      if (fn) api("GET", "/api/source/" + fn).then((src) => { const w = err && err.error.where; src.error_line = w ? w.file_line : null; const d2 = { kind: "lab", title: `Mã nguồn ${fn} – tham khảo cho lệnh vừa chạy ở Tab ${t}`, source: src }; addEntry(d2); });
    }
    L.seen[t] = sig;
  });
  $("#monSql").innerHTML = hl(s.monitor.sql);
  const lines = monLines(s);
  $("#monText").innerHTML = lines.length ? lines.map((l) => `<div class="hint ${l.includes("CHỜ KHÓA") ? "info" : ""}">${esc(l)}</div>`).join("") : '<div class="muted small">Hai tab chưa kết nối – hãy chạy một lệnh.</div>';
  $("#monTable").innerHTML = s.monitor.columns ? tableHTML(s.monitor.columns, s.monitor.rows || []) : "";
  $("#chkTable").innerHTML = s.check.columns ? tableHTML(s.check.columns, s.check.rows || []) : (s.check.error ? `<div class="err">${esc(s.check.error.message)}</div>` : "");
  $("#bidTable").innerHTML = s.bids.columns ? tableHTML(s.bids.columns, s.bids.rows || []) : "";
  const c = rowsOf(s.check)[0];
  $("#verdict").innerHTML = c ? `<span class="verdict ${c.doi_soat === "NHAT_QUAN" ? "ok" : "bad"}">${c.doi_soat === "NHAT_QUAN" ? "✔ NHAT_QUAN" : "✖ SAI_LECH"}</span>` : "";
}

// ------------------------------------------------------------------ ④ TRUY VẤN
async function initQueries() {
  const qs = await api("GET", "/api/queries");
  $("#page-queries").dataset.ready = 1;
  $("#page-queries").innerHTML = `<h1>④ Truy vấn nâng cao &amp; thống kê</h1>
   <p class="lead">12 truy vấn ở khối II của <code>queries.sql</code>, chạy <b>nguyên văn</b> theo đúng khoảng dòng trong file.</p>` +
    qs.map((q) => `<div class="card" style="margin-bottom:12px"><div class="row"><div class="grow"><h3 style="margin:0">${esc(q.title)}</h3>
      <div class="muted small">queries.sql · dòng ${q.a}–${q.b}</div></div><button class="btn brand" onclick="runQuery('${q.key}')">▶ Chạy</button></div>
      ${explainHTML(q.explain)}<details><summary>Xem câu SQL</summary><pre class="code">${hl(q.sql)}</pre></details><div id="qres-${q.key}"></div></div>`).join("");
}
window.runQuery = async (key) => {
  const d = await api("POST", "/api/queries/" + key);
  addEntry(d);
  const s = d.steps[0];
  $("#qres-" + key).innerHTML = s.error ? `<div class="err">${esc(s.error.message)}</div>` : `<div class="meta">Kết quả: <b>${esc(s.status)}</b> · ${s.ms} ms</div>` + tableHTML(s.columns, s.rows || [], 40);
};

// ------------------------------------------------------------------ ⑤ CƠ CHẾ VẬN HÀNH
function initDocs() {
  if ($("#page-docs").dataset.ready) return;
  $("#page-docs").dataset.ready = 1;
  const cr = Object.entries(S.credits).map(([k, c]) => `<li>Tài sản #${k}: <a href="${esc(c.page)}" target="_blank" rel="noopener">${esc(c.title)}</a> – ${esc(c.author || "?")} – ${esc(c.license)}</li>`).join("");
  $("#page-docs").innerHTML = `<div class="docs"><h1>⑤ Cơ chế vận hành của website và của CSDL</h1>
  <h2>1. Website này chạy thế nào?</h2>
  <div class="arch"><div class="box"><b>🖥 Trình duyệt</b>Trang HTML + JavaScript. Mỗi nút bấm gửi một yêu cầu tới máy chủ.</div><div class="arrow">→</div>
    <div class="box"><b>🐍 Máy chủ Flask (app.py)</b>Chọn câu SQL tương ứng: gọi hàm của đồ án, chạy nguyên văn từ file, hoặc sinh câu theo cấu trúc DDL.</div><div class="arrow">→</div>
    <div class="box"><b>🔌 psycopg (ClientCursor)</b>Ghép tham số thành <b>một chuỗi SQL hoàn chỉnh</b> rồi mới gửi. Chuỗi đó chính là thứ hiện trên Bảng SQL, không phải bản minh họa.</div><div class="arrow">→</div>
    <div class="box"><b>🐘 PostgreSQL 18</b>Database <code>daugia_web</code>. Chạy hàm PL/pgSQL, kiểm tra CHECK/khóa ngoại/UNIQUE, quản lý khóa và giao dịch.</div></div>
  <div class="card"><h3 style="margin-top:0">Ba loại câu lệnh trên Bảng SQL</h3><table class="grid">
    <tr><th>Nhãn</th><th>Ý nghĩa</th><th>Ví dụ</th></tr>
    <tr><td><span class="kind func">Gọi hàm có sẵn trong queries.sql</span></td><td>Website chỉ gọi <code>SELECT fn_…(…)</code>; toàn bộ logic nằm trong hàm của đồ án.</td><td>Trả giá, đóng phiên, lọc danh sách phiên</td></tr>
    <tr><td><span class="kind file">Chạy nguyên văn từ file .sql</span></td><td>Đọc file trong thư mục đồ án, tách từng câu (hiểu cả thân hàm $$…$$), giữ đúng số dòng.</td><td>Trang ①, trang ④</td></tr>
    <tr><td><span class="kind gen">SQL do website sinh theo cấu trúc DDL</span></td><td>Đồ án không có hàm cho thao tác này, nên website sinh INSERT/UPDATE đúng theo bảng trong DDL. Ràng buộc của bảng vẫn được PostgreSQL kiểm tra.</td><td>Đăng ký, duyệt, mở phiên mới</td></tr></table></div>
  <div class="card"><h3 style="margin-top:0">Vì sao website biết lỗi nằm ở dòng nào của queries.sql?</h3>
    <p>Khi hàm PL/pgSQL gặp <code>RAISE EXCEPTION</code>, PostgreSQL trả kèm ngữ cảnh, ví dụ <code>PL/pgSQL function fn_tragia(...) line 39 at RAISE</code>. "line 39" đếm từ dòng chứa <code>AS $$</code> của hàm.
    Website tìm dòng <code>AS $$</code> của <code>fn_TraGia</code> trong file (dòng 116), nên dòng lỗi = 116 + 39 − 1 = <b>dòng 154</b>: đúng câu RAISE "Người bán không được trả giá…".</p></div>
  <h2>2. Cấu trúc dữ liệu (11 bảng)</h2>
  <div class="card"><table class="grid">
    <tr><th>Bảng</th><th>Vai trò</th><th>Ràng buộc đáng chú ý</th></tr>
    <tr><td>NGUOIDUNG</td><td>Người dùng; một người có thể là người bán ở phiên này, người mua ở phiên khác</td><td>UNIQUE email</td></tr>
    <tr><td>DANHMUC</td><td>Cây danh mục 3 cấp (tự tham chiếu MaDanhMucCha)</td><td>Duyệt bằng WITH RECURSIVE</td></tr>
    <tr><td>TAISAN + 3 bảng con</td><td>Chuyên biệt hóa EER: TACPHAMNGHETHUAT, DOSUUTAM, THIETBIDIENTU</td><td>Khóa chính bảng con = MaTaiSan (ON DELETE CASCADE)</td></tr>
    <tr><td>PHIENDAUGIA</td><td>Phiên đấu giá; lưu sẵn GiaHienTai + MaLuotDanDau để đọc nhanh</td><td>CHECK giá &gt; 0, đóng &gt; mở, (GiaHienTai IS NULL) = (MaLuotDanDau IS NULL); FK (MaLuotDanDau, MaPhien) DEFERRABLE</td></tr>
    <tr><td>DANGKY</td><td>Đăng ký tham gia; phải DA_DUYET mới được trả giá</td><td>PK (MaPhien, MaNguoiDung)</td></tr>
    <tr><td>LUOTTRAGIA</td><td>Lịch sử mọi lượt hợp lệ</td><td>UNIQUE MaYeuCau (chống gửi trùng), UNIQUE (MaPhien, SoTien), FK tới DANGKY</td></tr>
    <tr><td>KETQUADAUGIA</td><td>Kết quả chốt</td><td>PK MaPhien nên mỗi phiên tối đa 1 kết quả</td></tr>
    <tr><td>NHATKYTHAYDOI</td><td>Nhật ký (JSONB), mã giao dịch txid_current()</td><td>—</td></tr></table></div>
  <h2>3. Một lượt trả giá đi qua những gì?</h2>
  <div class="card"><ol>
    <li>Bạn bấm <b>Trả giá</b>: trình duyệt gửi (phiên, người, số tiền, mã UUID) lên máy chủ.</li>
    <li>Máy chủ gửi đúng một câu <code>SELECT fn_TraGia(1, 8, 5750000.0, '…'::uuid)</code>. Kết nối ở chế độ auto-commit, nên cả hàm là <b>một giao dịch</b>.</li>
    <li>Trong hàm: khóa theo mã yêu cầu, khóa dòng phiên (FOR UPDATE), kiểm tra trạng thái / người bán / đăng ký / giá / giờ.</li>
    <li>Hợp lệ thì INSERT LUOTTRAGIA, UPDATE PHIENDAUGIA (giá + người dẫn đầu + PhienBan), INSERT NHATKYTHAYDOI rồi COMMIT. Khóa ngoại trì hoãn được kiểm tra lúc COMMIT.</li>
    <li>Không hợp lệ thì RAISE EXCEPTION: <b>mọi thay đổi trong giao dịch bị hủy</b>. Website tô đỏ dòng RAISE.</li>
    <li>Gửi lại cùng UUID: hàm tìm thấy mã yêu cầu đã có và trả mã lượt cũ, không ghi thêm.</li></ol></div>
  <h2>4. Kiểm soát đồng thời: vì sao phương án 2 sai?</h2>
  <div class="card"><table class="grid">
    <tr><th></th><th>Phương án 1 – fn_TraGia</th><th>Phương án 2 – fn_TraGia_Serializable</th></tr>
    <tr><td>Đọc phiên</td><td>SELECT … <b>FOR UPDATE</b> (dòng 143): khóa ngay</td><td>SELECT thường (dòng 285): <b>không khóa</b></td></tr>
    <tr><td>Người đến sau chờ ở đâu?</td><td>Ở dòng 143, <b>trước</b> khi kiểm tra giá</td><td>Ở UPDATE dòng 317, <b>sau</b> khi đã kiểm tra giá trên dữ liệu cũ</td></tr>
    <tr><td>Kết quả khi B trả thấp hơn A</td><td>B đọc giá mới → bị từ chối ✔</td><td>B ghi đè giá của A → SAI_LECH ✖ (lost update)</td></tr>
    <tr><td>Mức cô lập thực tế</td><td colspan="2">READ COMMITTED (một hàm không tự đặt được SERIALIZABLE; muốn SERIALIZABLE phải <code>BEGIN ISOLATION LEVEL SERIALIZABLE</code> ở phía gọi và thử lại cả giao dịch khi gặp lỗi 40001)</td></tr></table>
    <p>Tự kiểm chứng ở trang <b>③ Thử nghiệm 2 tab</b>: hai khung là hai kết nối PostgreSQL thật giữ giao dịch mở giữa các lần bấm. Bảng "Soi khóa" dùng <code>pg_stat_activity</code>, <code>pg_blocking_pids()</code> và <code>pg_locks</code> để chỉ ra tab nào đang chặn tab nào, và tab bị chặn đã INSERT hay chưa.</p></div>
  <h2>5. Các điểm chưa đúng của đồ án mà website giúp thấy rõ</h2>
  <div class="card"><ul>
    <li>Phương án 2 bị mất cập nhật khi chạy đồng thời (trang ③).</li>
    <li>test_cases.sql test 4.1 truyền 5.750.000, mức đã trả ở test 2.1, nên luôn lỗi (trang ①).</li>
    <li>fn_DongPhienDauGia vẫn ghi KETQUADAUGIA với MaLuotThang = NULL khi không có lượt, khác quy tắc 5 trong business_rules.md.</li>
    <li>CSDL không chặn người bán tự <b>đăng ký</b> phiên của mình; chỉ chặn ở lúc trả giá.</li></ul></div>
  <h2>6. Nguồn ảnh</h2><div class="card small"><p>Ảnh tài sản là ảnh thật có giấy phép tự do (Wikimedia Commons; riêng tài sản #9 từ Flickr qua Openverse), dùng để minh họa; tên tác phẩm và tác giả trong dữ liệu mẫu là hư cấu.</p><ul>${cr}</ul></div></div>`;
}

// ------------------------------------------------------------------ khởi động
$$("#nav button").forEach((b) => b.onclick = () => go(b.dataset.page));
$("#whoami").onchange = (e) => {
  S.who = Number(e.target.value); localStorage.setItem("who", S.who);
  toast("Bạn đang đóng vai: " + userName(S.who));
  if (S.page === "market" && S.session && $("#marketDetail") && $("#marketDetail").innerHTML) openSession(S.session, true);
};
$("#consoleClear").onclick = () => { $("#consoleList").innerHTML = '<div class="empty">Đã xóa.</div>'; };
$("#consoleToggle").onclick = () => $(".layout").classList.toggle("console-hidden");
$("#modal").onclick = (e) => { if (e.target.id === "modal") closeModal(); };
(async function boot() {
  try { S.credits = await (await fetch("/static/img/assets/credits.json")).json(); } catch { S.credits = {}; }
  await refreshStatus(); await loadMeta(); await initSetup();
  const h = location.hash.slice(1);
  go(["setup", "market", "lab", "queries", "docs"].includes(h) ? h : "setup");
})();

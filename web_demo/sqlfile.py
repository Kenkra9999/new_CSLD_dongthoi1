"""Đọc và tách file .sql của đồ án thành từng câu lệnh, giữ nguyên số dòng gốc.

Xử lý đúng: chú thích "--" và "/* */", chuỗi '...', định danh "...",
và thân hàm $$ ... $$ (dấu ; bên trong thân hàm không phải điểm kết thúc câu lệnh).
"""
import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
FILES = {
    "ddl": "DDL_HeThongDauGia.sql",
    "seed": "seed_data.sql",
    "queries": "queries.sql",
    "test": "test_cases.sql",
}


def read_file(key):
    return (PROJECT_DIR / FILES[key]).read_text(encoding="utf-8")


def split_sql(text):
    """Trả về danh sách {sql, line_start, line_end, code_only}."""
    out, i, n = [], 0, len(text)
    start = 0
    dollar = None
    while i < n:
        c = text[i]
        if dollar:
            if text.startswith(dollar, i):
                i += len(dollar); dollar = None
            else:
                i += 1
            continue
        if text.startswith("--", i):
            j = text.find("\n", i); i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2); i = n if j < 0 else j + 2
            continue
        if c == "'":
            i += 1
            while i < n:
                if text[i] == "'" and i + 1 < n and text[i + 1] == "'":
                    i += 2
                elif text[i] == "'":
                    i += 1; break
                else:
                    i += 1
            continue
        if c == '"':
            j = text.find('"', i + 1); i = n if j < 0 else j + 1
            continue
        if c == "$":
            m = re.match(r"\$[A-Za-z_]*\$", text[i:])
            if m:
                dollar = m.group(0); i += len(dollar)
                continue
        if c == ";":
            _push(out, text, start, i + 1)
            start = i + 1
        i += 1
    _push(out, text, start, n)
    return out


def _push(out, text, a, b):
    chunk = text[a:b]
    code = _strip_comments(chunk).strip()
    if not code or code == ";":
        return
    # bỏ dòng trống ở đầu, giữ chú thích đi kèm câu lệnh
    lead = len(chunk) - len(chunk.lstrip("\r\n \t"))
    a2 = a + lead
    sql = text[a2:b].rstrip()
    line_start = text.count("\n", 0, a2) + 1
    line_end = line_start + sql.count("\n")
    out.append({"sql": sql, "line_start": line_start, "line_end": line_end, "code_only": code})


def _strip_comments(s):
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return "\n".join(l.split("--", 1)[0] if not _in_quote_line(l) else l for l in s.split("\n"))


def _in_quote_line(line):
    # đủ dùng cho file của đồ án: chỉ cắt "--" khi nó nằm ngoài chuỗi '...'
    idx = line.find("--")
    return idx >= 0 and line[:idx].count("'") % 2 == 1


def test_sections():
    """Nhóm các câu lệnh của test_cases.sql theo tiêu đề '-- BƯỚC', '-- TEST CASE', '-- Hỗ trợ'."""
    stmts = split_sql(read_file("test"))
    sections, cur = [], None
    for idx, s in enumerate(stmts):
        title = None
        for line in s["sql"].split("\n"):
            t = line.strip()
            if not t:
                continue
            if not t.startswith("--"):
                break
            m = re.match(r"--\s*((BƯỚC|TEST CASE|Hỗ trợ).*)", t)
            if m:
                title = m.group(1).strip()
        if title or cur is None:
            cur = {"title": title or "Mở đầu", "items": []}
            sections.append(cur)
        s = dict(s, index=idx)
        cur["items"].append(s)
    return sections


def function_index():
    """Vị trí từng hàm trong queries.sql: dòng CREATE, dòng 'AS $$' (dòng 1 của thân hàm), dòng kết thúc."""
    lines = read_file("queries").split("\n")
    idx, cur = {}, None
    for no, line in enumerate(lines, 1):
        m = re.match(r"\s*CREATE OR REPLACE FUNCTION\s+(\w+)", line, re.I)
        if m:
            cur = {"name": m.group(1), "create": no}
            continue
        if cur and "dollar" not in cur and "$$" in line:
            cur["dollar"] = no
            continue
        if cur and "dollar" in cur and line.strip().startswith("$$"):
            cur["end"] = no
            idx[cur["name"].lower()] = cur
            cur = None
    return idx


def file_lines(key, a, b):
    lines = read_file(key).split("\n")
    return [{"no": i, "text": lines[i - 1]} for i in range(a, min(b, len(lines)) + 1)]

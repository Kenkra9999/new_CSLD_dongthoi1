"""Nội dung giải thích hiển thị trên website (tiếng Việt).

KEY_LINES: các dòng quan trọng trong queries.sql, kèm ghi chú, để tô sáng khi hiện mã nguồn hàm.
QUERY_LIST: các truy vấn nâng cao, lấy nguyên văn theo khoảng dòng trong queries.sql.
"""

KEY_LINES = {
    "fn_tragia": [
        {"a": 126, "b": 129, "note": "Kiểm tra đầu vào: có mã yêu cầu, số tiền > 0, tối đa 2 chữ số thập phân."},
        {"a": 132, "b": 132, "note": "Khóa tư vấn theo MÃ YÊU CẦU: hai lần gửi cùng UUID phải xếp hàng, nên không thể tạo trùng."},
        {"a": 133, "b": 141, "note": "Nếu mã yêu cầu đã được dùng: trả lại mã lượt cũ (chống gửi trùng / idempotency)."},
        {"a": 143, "b": 143, "note": "SELECT … FOR UPDATE: KHÓA dòng phiên ngay khi đọc. Người đến sau phải CHỜ ở đây, rồi đọc được giá MỚI NHẤT."},
        {"a": 147, "b": 149, "note": "Phiên phải đang ở trạng thái DANG_DIEN_RA."},
        {"a": 151, "b": 155, "note": "Người bán không được tự trả giá tài sản của mình (FOR SHARE giữ dòng tài sản không bị đổi)."},
        {"a": 157, "b": 161, "note": "Người trả giá phải có đăng ký ĐÃ DUYỆT cho phiên này."},
        {"a": 163, "b": 168, "note": "Giá tối thiểu = giá hiện tại + bước giá (hoặc giá khởi điểm nếu chưa ai trả), và phải đúng lưới bước giá."},
        {"a": 171, "b": 174, "note": "Đọc đồng hồ SAU khi đã chờ khóa: nếu chờ quá giờ đóng thì vẫn bị chặn đúng."},
        {"a": 176, "b": 178, "note": "Ghi lượt trả giá mới vào lịch sử (LUOTTRAGIA)."},
        {"a": 180, "b": 182, "note": "Cập nhật giá hiện tại + người dẫn đầu + tăng PhienBan, trong CÙNG giao dịch với lệnh INSERT ở trên (nguyên tử)."},
        {"a": 184, "b": 187, "note": "Ghi nhật ký thay đổi (NHATKYTHAYDOI)."},
    ],
    "fn_tragia_serializable": [
        {"a": 276, "b": 277, "note": "Vòng thử lại 5 lần NẰM TRONG hàm: không có tác dụng (xem phần EXCEPTION bên dưới)."},
        {"a": 279, "b": 282, "note": "Chống gửi trùng nhưng KHÔNG có khóa: gửi trùng đồng thời sẽ báo lỗi duplicate key thay vì trả mã cũ."},
        {"a": 285, "b": 288, "note": "⚠ ĐỌC PHIÊN KHÔNG KHÓA (thiếu FOR UPDATE). Không phải chờ ai, nhưng chỉ thấy dữ liệu đã COMMIT, nên có thể thấy giá CŨ."},
        {"a": 291, "b": 300, "note": "Kiểm tra người bán và đăng ký đã duyệt."},
        {"a": 302, "b": 305, "note": "⚠ Kiểm tra giá dựa trên giá VỪA ĐỌC ở dòng 285, có thể đã cũ."},
        {"a": 307, "b": 310, "note": "Kiểm tra giờ phiên."},
        {"a": 313, "b": 315, "note": "Ghi lượt mới: dòng mới hoàn toàn nên không phải chờ ai."},
        {"a": 317, "b": 319, "note": "⚠ UPDATE dòng phiên: nếu người khác đang giữ khóa dòng này thì CHỜ Ở ĐÂY (tab quay). Chờ xong sẽ GHI ĐÈ giá, vì phép kiểm tra giá không được chạy lại."},
        {"a": 321, "b": 324, "note": "Ghi nhật ký."},
        {"a": 328, "b": 336, "note": "Bắt lỗi 40001 (serialization_failure) để thử lại. Nhưng hàm chạy ở READ COMMITTED nên lỗi này không xảy ra; và thử lại trong cùng giao dịch cũng không giúp gì."},
    ],
    "fn_dongphiendaugia": [
        {"a": 208, "b": 208, "note": "SELECT … FOR UPDATE: khóa dòng phiên. Đóng phiên và trả giá (fn_TraGia) loại trừ lẫn nhau trên cùng khóa này."},
        {"a": 213, "b": 216, "note": "Nếu đã có kết quả thì trả lại kết quả cũ: gọi đóng phiên nhiều lần không tạo thêm người thắng."},
        {"a": 218, "b": 221, "note": "Chưa đến giờ đóng thì không cho chốt."},
        {"a": 222, "b": 224, "note": "Chỉ phiên DANG_DIEN_RA hoặc CHUA_MO mới được chốt."},
        {"a": 226, "b": 230, "note": "Chọn lượt giá cao nhất; nếu bằng giá thì lượt có mã nhỏ hơn (đến trước) thắng."},
        {"a": 232, "b": 233, "note": "Ghi KETQUADAUGIA. Khóa chính là MaPhien, nên mỗi phiên có TỐI ĐA 1 kết quả."},
        {"a": 235, "b": 238, "note": "Đổi trạng thái: có người thắng thì DA_DONG, không có ai trả giá thì THAT_BAI."},
        {"a": 240, "b": 243, "note": "Ghi nhật ký DONG_PHIEN."},
    ],
    "fn_baocaophiendaugiadong": [
        {"a": 36, "b": 48, "note": "CTE đệ quy: lấy danh mục được chọn và TOÀN BỘ danh mục con cháu."},
        {"a": 49, "b": 70, "note": "Khung truy vấn: ghép phiên, tài sản, người bán, đếm lượt trả giá, người dẫn đầu."},
        {"a": 73, "b": 91, "note": "SQL ĐỘNG: chỉ nối điều kiện nào có tham số khác NULL."},
        {"a": 103, "b": 104, "note": "EXECUTE … USING: giá trị truyền dưới dạng tham số $1..$6, không ghép chuỗi, nên chống được SQL injection."},
    ],
}

EXPLAIN = {
    "file_ddl": {
        "what": "Tạo cấu trúc CSDL: xóa 11 bảng cũ (CASCADE) rồi tạo lại.",
        "how": [
            "NGUOIDUNG, DANHMUC (cây cha–con tự tham chiếu), TAISAN và 3 bảng con TACPHAMNGHETHUAT / DOSUUTAM / THIETBIDIENTU (chuyên biệt hóa EER: khóa chính bảng con = khóa chính TAISAN).",
            "PHIENDAUGIA lưu thêm GiaHienTai + MaLuotDanDau (dư thừa có chủ đích để đọc nhanh), có CHECK ràng buộc giá, thời gian, và 'có giá thì phải có người dẫn đầu'.",
            "DANGKY (khóa chính kép MaPhien + MaNguoiDung), LUOTTRAGIA (UNIQUE MaYeuCau chống gửi trùng, UNIQUE (MaPhien, SoTien) không cho 2 lượt cùng giá), KETQUADAUGIA (khóa chính MaPhien nên tối đa 1 kết quả), NHATKYTHAYDOI (JSONB).",
            "Câu ALTER TABLE cuối: khóa ngoại (MaLuotDanDau, MaPhien) → LUOTTRAGIA, DEFERRABLE INITIALLY DEFERRED, tức là chỉ kiểm tra lúc COMMIT, để INSERT lượt và UPDATE phiên trong cùng giao dịch không vướng nhau.",
        ],
        "note": "Các NOTICE 'does not exist, skipping' là bình thường khi chạy lần đầu."},
    "file_seed": {
        "what": "Nạp dữ liệu mẫu trong MỘT giao dịch (BEGIN … COMMIT).",
        "how": [
            "15 người dùng, 21 danh mục 3 cấp, 18 tài sản (6 mỗi loại) và dữ liệu 3 bảng con.",
            "20 phiên: 6 đang diễn ra, 3 chưa mở, 7 đã chốt có người thắng, 4 thất bại. Thời gian tính theo CURRENT_TIMESTAMP lúc nạp.",
            "Đăng ký, 45 lượt trả giá (mỗi lượt một UUID riêng), rồi UPDATE GiaHienTai/MaLuotDanDau từ lượt cao nhất, ghi KETQUADAUGIA và NHATKYTHAYDOI.",
            "Cuối file setval() đồng bộ bộ đếm IDENTITY vì ở trên dùng OVERRIDING SYSTEM VALUE.",
        ],
        "note": "Nếu một câu lỗi, cả giao dịch bị hủy; website tự gửi ROLLBACK."},
    "file_queries": {
        "what": "Khối I: cài 4 hàm. Khối II: chạy các truy vấn nâng cao.",
        "how": [
            "fn_BaoCaoPhienDauGiaDong: báo cáo lọc động (SQL động + CTE đệ quy).",
            "fn_TraGia: trả giá phương án 1, khóa dòng SELECT … FOR UPDATE.",
            "fn_DongPhienDauGia: chốt kết quả, xác định người thắng.",
            "fn_TraGia_Serializable: trả giá phương án 2 (thực tế chạy READ COMMITTED, không khóa: có lỗi mất cập nhật khi chạy đồng thời).",
            "12 truy vấn SELECT ở sau: kết quả của từng câu hiện bên dưới.",
        ]},
    "file_test": {
        "what": "Kịch bản kiểm thử: chạy TỪNG câu (không chạy cả file vì có ca cố tình gây lỗi).",
        "how": ["Bấm ▶ ở từng câu. Câu có gọi hàm sẽ hiện mã nguồn hàm, và nếu lỗi thì tô đỏ đúng dòng RAISE trong queries.sql."]},
    "sessions": {
        "what": "Danh sách phiên lấy bằng hàm có sẵn fn_BaoCaoPhienDauGiaDong.",
        "how": [
            "Mỗi ô lọc bạn chọn trở thành một tham số có tên (p_TrangThai => …). Ô nào bỏ trống thì không truyền.",
            "Bên trong hàm, chỉ điều kiện nào có tham số mới được nối vào câu SQL động, rồi chạy bằng EXECUTE … USING.",
            "Website JOIN thêm PHIENDAUGIA để lấy MaTaiSan (dùng hiện ảnh) và BuocGia.",
        ]},
    "session_detail": {
        "what": "Website chạy 5 câu SELECT để dựng trang chi tiết.",
        "how": [
            "Câu 1 LEFT JOIN cả 3 bảng con: chỉ đúng một bảng con có dữ liệu, tùy loại tài sản (chuyên biệt hóa EER).",
            "Câu 2 lấy nguyên truy vấn 'Lịch sử giá' của queries.sql (hàm cửa sổ LAG tính mức tăng so với lượt trước).",
            "Câu 3–5: đăng ký, kết quả, nhật ký thay đổi.",
        ]},
    "fn_tragia": {
        "what": "Gọi hàm fn_TraGia (phương án 1 – khóa dòng). Cả hàm chạy trong MỘT giao dịch: lỗi ở bất kỳ dòng nào thì mọi thay đổi đều bị hủy.",
        "how": [
            "Khóa theo mã yêu cầu (dòng 132), rồi khóa dòng phiên bằng FOR UPDATE (dòng 143).",
            "Kiểm tra lần lượt: trạng thái phiên, người bán, đăng ký đã duyệt, giá tối thiểu và lưới bước giá, giờ.",
            "Ghi LUOTTRAGIA, cập nhật PHIENDAUGIA, ghi NHATKYTHAYDOI, rồi trả về mã lượt.",
            "Gửi lại cùng UUID: hàm trả lại mã lượt cũ, không tạo lượt mới.",
        ],
        "note": "Nếu báo lỗi: dòng RAISE gây lỗi được tô ĐỎ trong mã nguồn bên dưới (website tra từ 'line N' trong thông báo lỗi của PostgreSQL)."},
    "fn_tragia_serializable": {
        "what": "Gọi hàm fn_TraGia_Serializable (phương án 2). Khi một người trả giá thì chạy đúng; khi hai người chồng nhau thì có lỗi mất cập nhật.",
        "how": [
            "Dòng 285 đọc phiên KHÔNG khóa, dòng 302 kiểm tra giá trên dữ liệu vừa đọc, dòng 317 mới UPDATE.",
            "Gọi bằng SELECT thì mức cô lập là READ COMMITTED (không phải SERIALIZABLE như tên hàm).",
            "Muốn thấy lỗi: dùng trang 'Thử nghiệm 2 tab'.",
        ]},
    "register": {
        "what": "Đăng ký tham gia phiên. Repo KHÔNG có hàm đăng ký, nên website sinh câu INSERT đúng theo cấu trúc bảng DANGKY trong DDL.",
        "how": [
            "Trạng thái ban đầu là CHO_DUYET. Muốn trả giá được, đăng ký phải được duyệt (DA_DUYET); fn_TraGia kiểm tra điều này ở dòng 157–161.",
            "Khóa chính (MaPhien, MaNguoiDung): đăng ký 2 lần cùng phiên sẽ bị PostgreSQL từ chối (lỗi 23505).",
            "Lưu ý: CSDL KHÔNG chặn người bán tự đăng ký phiên của mình (chỉ chặn ở lúc trả giá).",
        ]},
    "approve": {
        "what": "Duyệt / từ chối đăng ký: website sinh câu UPDATE trên bảng DANGKY.",
        "how": ["CHECK ck_dangky_trangthai chỉ yêu cầu trạng thái không rỗng; tập giá trị (CHO_DUYET / DA_DUYET / TU_CHOI) do ứng dụng quy ước."]},
    "fn_dongphiendaugia": {
        "what": "Gọi hàm fn_DongPhienDauGia: chốt người thắng.",
        "how": [
            "Khóa dòng phiên (FOR UPDATE), nên không thể vừa chốt vừa nhận lượt mới từ fn_TraGia.",
            "Chỉ chốt khi đã tới giờ đóng. Mỗi phiên tối đa 1 dòng KETQUADAUGIA (khóa chính MaPhien).",
            "Không có ai trả giá thì vẫn ghi 1 dòng kết quả với MaLuotThang = NULL và trạng thái THAT_BAI (khác với quy tắc 5 trong business_rules.md).",
        ],
        "note": "Phiên đang mở sẽ báo 'Phiên chưa đến giờ đóng'. Dùng nút '⏩ Tua tới giờ đóng' để thử."},
    "time_extend": {
        "what": "Công cụ hỗ trợ (không phải nghiệp vụ): giống BƯỚC 0 của test_cases.sql, mở phiên thêm 2 giờ.",
        "how": ["Website chặn mở lại phiên đã có kết quả để không phá tính nhất quán.",
                "Tác dụng phụ (có sẵn trong Bước 0 của test_cases.sql): giờ mở bị dời về 1 giờ trước, nên các lượt trả giá cũ hơn mốc đó bị câu 'Kiểm tra toàn vẹn' (trang ④) báo là 'Trả giá ngoài giờ phiên'."]},
    "time_end": {
        "what": "Công cụ hỗ trợ (không phải nghiệp vụ): kéo giờ đóng về hiện tại để thử fn_DongPhienDauGia.",
        "how": ["CHECK ck_phiendaugia_thoigian yêu cầu ThoiDiemDong > ThoiDiemMo, nên website dùng GREATEST(…) để không vi phạm."]},
    "create_session": {
        "what": "Mở phiên mới: website sinh câu INSERT theo cấu trúc bảng PHIENDAUGIA.",
        "how": [
            "GiaHienTai và MaLuotDanDau để trống (NULL): CHECK ck_phiendaugia_dandau yêu cầu cả hai cùng NULL hoặc cùng có giá trị.",
            "CHECK ck_phiendaugia_giakhoidiem / buocgia: giá phải > 0. Thử nhập 0 để xem PostgreSQL từ chối.",
        ]},
    "lab_reset": {
        "what": "Đặt lại phiên cho thử nghiệm: xóa lượt phát sinh khi thử, mở phiên 2 giờ, tính lại người dẫn đầu, đồng bộ bộ đếm mã lượt.",
        "how": ["Trước khi chạy, website ROLLBACK cả 2 tab để không còn ai giữ khóa."]},
}

QUERY_LIST = [
    {"key": "tree", "a": 343, "b": 401, "title": "Cây danh mục + cộng dồn tài sản/phiên (WITH RECURSIVE)",
     "explain": {"what": "CTE đệ quy dựng cây 3 cấp; CTE thứ hai sinh mọi cặp (tổ tiên, con cháu) để cộng dồn số liệu từ lá lên gốc.",
                 "how": ["Bước cơ sở: danh mục gốc (MaDanhMucCha IS NULL). Bước đệ quy: JOIN con với cha, cộng CapDo.",
                         "COUNT(DISTINCT …) tránh đếm trùng khi một phiên nằm ở nhiều nhánh tổ tiên."]}},
    {"key": "branch", "a": 404, "b": 434, "title": "Tài sản và phiên thuộc nhánh danh mục 1",
     "explain": {"what": "Duyệt xuống mọi danh mục con cháu của danh mục 1 rồi lấy tài sản, phiên.", "how": []}},
    {"key": "ending", "a": 437, "b": 448, "title": "Phiên sắp kết thúc trong 1 giờ",
     "explain": {"what": "Lọc phiên đang diễn ra có giờ đóng trong khoảng (bây giờ, bây giờ + 1 giờ].", "how": []}},
    {"key": "leaders", "a": 450, "b": 457, "title": "Người dẫn đầu từng phiên",
     "explain": {"what": "Đọc MaLuotDanDau lưu sẵn trong PHIENDAUGIA (nhanh, không phải tính lại từ lịch sử).", "how": ["LEFT JOIN để phiên chưa có lượt vẫn hiện."]}},
    {"key": "history", "a": 459, "b": 467, "title": "Lịch sử giá và mức tăng (LAG)",
     "explain": {"what": "Hàm cửa sổ LAG lấy giá lượt liền trước trong cùng phiên.", "how": []}},
    {"key": "participants", "a": 469, "b": 489, "title": "Số người đăng ký / đã duyệt / đã trả giá",
     "explain": {"what": "Tổng hợp riêng từng bảng trong CTE rồi mới JOIN, để không đếm trùng.", "how": []}},
    {"key": "results", "a": 491, "b": 496, "title": "Kết quả các phiên đã chốt",
     "explain": {"what": "Giá thắng lấy từ lượt thắng (MaLuotThang), không lưu riêng.", "how": []}},
    {"key": "rate", "a": 498, "b": 500, "title": "Tỷ lệ phiên thành công",
     "explain": {"what": "COUNT(MaLuotThang) bỏ qua NULL, nên đếm đúng số phiên có người thắng.", "how": []}},
    {"key": "rank", "a": 502, "b": 529, "title": "Xếp hạng người trả giá trong từng phiên",
     "explain": {"what": "DISTINCT ON lấy giá cao nhất mỗi người; ROW_NUMBER/LEAD xếp hạng; so khớp với MaLuotDanDau.", "how": []}},
    {"key": "rollup", "a": 531, "b": 556, "title": "Tỷ lệ thành công theo nhánh gốc (ROLLUP)",
     "explain": {"what": "Đệ quy gắn mỗi danh mục về gốc; GROUP BY ROLLUP thêm dòng tổng toàn hệ thống.", "how": []}},
    {"key": "buyers", "a": 558, "b": 579, "title": "Bảng xếp hạng người mua (DENSE_RANK)",
     "explain": {"what": "Số phiên tham gia, số phiên thắng, tổng chi; DENSE_RANK theo tổng giá thắng.", "how": []}},
    {"key": "audit", "a": 581, "b": 606, "title": "Kiểm tra toàn vẹn dữ liệu (rỗng = không vi phạm)",
     "explain": {"what": "Dò mọi lượt vi phạm quy tắc + phiên có GiaHienTai lệch giá cao nhất.",
                 "how": ["Chạy câu này sau khi thử nghiệm 2 tab với phương án 2: sẽ thấy dòng 'GiaHienTai khác giá cao nhất của phiên'."]}},
]

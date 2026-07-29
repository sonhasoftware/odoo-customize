-- ############################################################################
-- ĐỒNG BỘ BẢNG PHẲNG  du_lieu_tong_hop_vat_tu
-- ----------------------------------------------------------------------------
-- File này là TOÀN BỘ tầng đồng bộ của module. Trước đây phần việc này nằm ở
-- 2 file (du_lieu_tong_hop_vat_tu_triggers.sql + fn_dlthvt_bulk_sync.sql) với
-- 2 bản mapping song song, 3 cơ chế bật/tắt trigger và 1 hook postcommit.
-- Nay gộp về 1 file, 1 bản mapping duy nhất, không còn công tắc nào.
--
-- Yêu cầu PostgreSQL >= 14 (REFERENCING NEW/OLD TABLE + EXECUTE FUNCTION).
-- Local/server 15–17 đều ổn.
--
-- ============================================================================
-- NGUYÊN TẮC THIẾT KẾ  (đọc phần này trước khi sửa bất cứ thứ gì)
-- ============================================================================
--
-- 1) TRIGGER Ở MỨC CÂU LỆNH, KHÔNG PHẢI MỨC DÒNG.
--    Mỗi trigger khai báo FOR EACH STATEMENT kèm REFERENCING NEW/OLD TABLE
--    (PostgreSQL >= 10; local/server hiện dùng 15–17 đều ổn). Nhờ vậy trigger
--    chỉ chạy ĐÚNG MỘT LẦN cho mỗi câu lệnh SQL, bất kể câu lệnh đó chạm 1
--    dòng hay 50.000 dòng.
--      - Sửa 1 ô trên giao diện Odoo  -> 1 câu UPDATE  -> trigger chạy 1 lần.
--      - Procedure sinh 50.000 dòng   -> 1 câu INSERT  -> trigger chạy 1 lần.
--    Đây là lý do KHÔNG CẦN tắt trigger khi ghi hàng loạt. Mọi cờ điều khiển
--    cũ (app.dlthvt_skip, app.dlthvt_bulk) và mọi câu ALTER TABLE ... DISABLE
--    TRIGGER đã bị bỏ. Không được thêm lại: hễ có công tắc là có ngày quên
--    bật, và bảng phẳng lệch âm thầm.
--
-- 2) MỖI BƯỚC CHỈ CÓ ĐÚNG MỘT HÀM MAPPING.
--    dlthvt_map_<bước>(p_ids) là nguồn chân lý duy nhất cho phép chiếu từ bảng
--    nguồn sang bảng phẳng. Trigger gọi nó, hàm rebuild cũng gọi nó. Vì vậy
--    dữ liệu sinh ra khi sửa tay trên UI và khi import/tính toán hàng loạt
--    LUÔN giống nhau tuyệt đối - không còn khả năng lệch như kiến trúc cũ.
--
-- 3) MỖI HÀM MAPPING LÀ "XOÁ RỒI CHÈN", KHÔNG DÙNG ON CONFLICT.
--    Vì month_key nằm trong khoá duy nhất, nếu dòng nguồn đổi kỳ (period_id)
--    hoặc kỳ đổi tháng bắt đầu thì month_key đổi theo, và cách upsert cũ sẽ
--    để lại dòng phẳng mồ côi với month_key cũ. Xoá trước rồi chèn lại thì
--    luôn đúng trong mọi trường hợp, chi phí tương đương (trong MVCC thì
--    UPDATE cũng là xoá + chèn), lại bỏ được ~350 dòng "DO UPDATE SET".
--    Hệ quả phụ: mỗi hàm mapping là idempotent, gọi bao nhiêu lần cũng thế.
--
-- 4) MỌI CỘT META ĐƯỢC ĐIỀN NGAY TRONG CÂU MAPPING.
--    Kiến trúc cũ có thêm trigger BEFORE trên chính bảng phẳng
--    (dlthvt_fill_meta) để tra period_code / owner_company_id / company_code,
--    tốn 3 câu SELECT cho MỖI dòng phẳng. Nay các cột đó lấy bằng JOIN sẵn
--    trong câu mapping nên trigger đó đã bị xoá.
--
-- ============================================================================
-- HƯỚNG DẪN BẢO TRÌ
-- ============================================================================
--
-- * Thêm một cột mới vào bảng phẳng:
--     sửa DUY NHẤT hàm dlthvt_map_<bước> tương ứng ở PHẦN 4 (thêm tên cột vào
--     danh sách INSERT và thêm biểu thức vào SELECT ở đúng vị trí).
--
-- * Thêm một bước mới (ví dụ b6):
--     (a) viết dlthvt_map_b6 ở PHẦN 4 theo đúng khuôn của các hàm khác;
--     (b) thêm nhánh WHEN 'b6' vào dlthvt_after_change ở PHẦN 5;
--     (c) thêm 3 trigger ins/upd/del cho bảng nguồn ở PHẦN 5;
--     (d) thêm 1 dòng vào dlthvt_rebuild_period ở PHẦN 6.
--
-- * Đổi quy tắc tháng T0..T+3:
--     sửa DUY NHẤT hàm dlthvt_month_date ở PHẦN 3.
--
-- * Nghi ngờ bảng phẳng lệch so với bảng nguồn:
--     chạy  SELECT dlthvt_rebuild_period(<id kỳ>);  hoặc dlthvt_rebuild_all().
--     Hai hàm này an toàn, chạy lại bao nhiêu lần cũng cho ra cùng kết quả.
--
-- * Tuyệt đối KHÔNG dùng TRUNCATE trên các bảng nguồn: TRUNCATE không kích
--   hoạt trigger nên bảng phẳng sẽ không được dọn theo. Dùng DELETE.
--
-- ############################################################################


-- ============================================================================
-- PHẦN 1. DỌN KIẾN TRÚC CŨ
-- ----------------------------------------------------------------------------
-- Phải xoá hết trigger mức dòng và các hàm cũ trước khi tạo cái mới, vì file
-- này được chạy lại mỗi lần cập nhật module. Thứ tự: trigger trước, hàm sau.
-- ============================================================================

DROP TRIGGER IF EXISTS trg_dlthvt_fill_meta   ON du_lieu_tong_hop_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_period_meta ON ke_hoach_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_kd          ON ke_hoach_kinh_doanh;
DROP TRIGGER IF EXISTS trg_dlthvt_sx          ON ke_hoach_san_xuat;
DROP TRIGGER IF EXISTS trg_dlthvt_b1          ON ke_hoach_vat_tu_line;
DROP TRIGGER IF EXISTS trg_dlthvt_b2          ON dinh_muc;
DROP TRIGGER IF EXISTS trg_dlthvt_b3          ON tinh_toan_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_b4          ON tong_hop_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_b5          ON kh_dat_vat_tu;

-- Trigger mức câu lệnh (phiên bản mới) — xoá trước khi tạo lại ở PHẦN 5.
DROP TRIGGER IF EXISTS trg_dlthvt_kd_ins ON ke_hoach_kinh_doanh;
DROP TRIGGER IF EXISTS trg_dlthvt_kd_upd ON ke_hoach_kinh_doanh;
DROP TRIGGER IF EXISTS trg_dlthvt_kd_del ON ke_hoach_kinh_doanh;
DROP TRIGGER IF EXISTS trg_dlthvt_sx_ins ON ke_hoach_san_xuat;
DROP TRIGGER IF EXISTS trg_dlthvt_sx_upd ON ke_hoach_san_xuat;
DROP TRIGGER IF EXISTS trg_dlthvt_sx_del ON ke_hoach_san_xuat;
DROP TRIGGER IF EXISTS trg_dlthvt_b1_ins ON ke_hoach_vat_tu_line;
DROP TRIGGER IF EXISTS trg_dlthvt_b1_upd ON ke_hoach_vat_tu_line;
DROP TRIGGER IF EXISTS trg_dlthvt_b1_del ON ke_hoach_vat_tu_line;
DROP TRIGGER IF EXISTS trg_dlthvt_b2_ins ON dinh_muc;
DROP TRIGGER IF EXISTS trg_dlthvt_b2_upd ON dinh_muc;
DROP TRIGGER IF EXISTS trg_dlthvt_b2_del ON dinh_muc;
DROP TRIGGER IF EXISTS trg_dlthvt_b3_ins ON tinh_toan_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_b3_upd ON tinh_toan_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_b3_del ON tinh_toan_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_b4_ins ON tong_hop_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_b4_upd ON tong_hop_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_b4_del ON tong_hop_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_b5_ins ON kh_dat_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_b5_upd ON kh_dat_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_b5_del ON kh_dat_vat_tu;
DROP TRIGGER IF EXISTS trg_dlthvt_period_upd ON ke_hoach_vat_tu;

DROP FUNCTION IF EXISTS dlthvt_fill_meta();
DROP FUNCTION IF EXISTS dlthvt_sync_period_meta();
DROP FUNCTION IF EXISTS dlthvt_sync_kd();
DROP FUNCTION IF EXISTS dlthvt_sync_sx();
DROP FUNCTION IF EXISTS dlthvt_sync_b1();
DROP FUNCTION IF EXISTS dlthvt_sync_b2();
DROP FUNCTION IF EXISTS dlthvt_sync_b3();
DROP FUNCTION IF EXISTS dlthvt_sync_b4();
DROP FUNCTION IF EXISTS dlthvt_sync_b5();

DROP FUNCTION IF EXISTS public.dlthvt_bulk_sync_kd_period(INTEGER);
DROP FUNCTION IF EXISTS public.dlthvt_bulk_sync_sx_period(INTEGER);
DROP FUNCTION IF EXISTS public.dlthvt_bulk_sync_b1_period(INTEGER);
DROP FUNCTION IF EXISTS public.dlthvt_bulk_sync_b2_period(INTEGER);
DROP FUNCTION IF EXISTS public.dlthvt_bulk_sync_b3_period(INTEGER);
DROP FUNCTION IF EXISTS public.dlthvt_bulk_sync_b4_period(INTEGER);
DROP FUNCTION IF EXISTS public.dlthvt_bulk_sync_b5_period(INTEGER);


-- ============================================================================
-- PHẦN 2. INDEX
-- ----------------------------------------------------------------------------
-- Khoá duy nhất (source_model, source_res_id, month_key) do Odoo tạo từ
-- _sql_constraints; nó cũng là index phục vụ hai việc nóng nhất của file này:
-- xoá theo dòng nguồn trong hàm mapping, và xoá theo dòng nguồn khi DELETE.
-- Các index dưới đây phục vụ câu truy vấn báo cáo.
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_dlthvt_report
    ON du_lieu_tong_hop_vat_tu (step_code, period_id, month_key);

CREATE INDEX IF NOT EXISTS idx_dlthvt_report_month_date
    ON du_lieu_tong_hop_vat_tu (step_code, period_id, month_date);

CREATE INDEX IF NOT EXISTS idx_dlthvt_report_b2_nvl
    ON du_lieu_tong_hop_vat_tu (step_code, period_id, company_id, month_key, ma_nvl);

CREATE INDEX IF NOT EXISTS idx_dlthvt_period_company
    ON du_lieu_tong_hop_vat_tu (step_code, period_company_id, month_date);

CREATE INDEX IF NOT EXISTS idx_dlthvt_owner_company
    ON du_lieu_tong_hop_vat_tu (step_code, owner_company_id, month_date);


-- ============================================================================
-- PHẦN 3. HÀM TIỆN ÍCH
-- ============================================================================

-- Quy tắc tháng của cả module: kỳ có period_month dạng 'MM/YYYY', các cột
-- *_t0..*_t3 tương ứng tháng đó và 3 tháng kế tiếp. Đây là NƠI DUY NHẤT định
-- nghĩa phép cộng tháng - mọi hàm mapping đều gọi hàm này.
CREATE OR REPLACE FUNCTION dlthvt_month_date(p_period_month TEXT, p_offset INT)
RETURNS DATE
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT (TO_DATE(p_period_month, 'MM/YYYY') + (p_offset || ' month')::INTERVAL)::DATE;
$$;

-- Đọc số từ chuỗi SAP: chịu được dấu trừ đứng sau ('123-'), dấu phân cách
-- nghìn, chuỗi rỗng và cả rác. Không bao giờ raise, trả 0 nếu không đọc được.
CREATE OR REPLACE FUNCTION safe_sap_numeric(val TEXT)
RETURNS NUMERIC AS $$
DECLARE
    cleaned TEXT;
BEGIN
    IF val IS NULL OR TRIM(val) = '' THEN RETURN 0; END IF;
    cleaned := TRIM(val);
    IF cleaned LIKE '%-' THEN
        cleaned := '-' || LEFT(cleaned, LENGTH(cleaned) - 1);
    END IF;
    cleaned := regexp_replace(cleaned, '[^0-9.\-]', '', 'g');
    IF cleaned = '' OR cleaned = '-' THEN RETURN 0; END IF;
    RETURN cleaned::NUMERIC;
EXCEPTION WHEN OTHERS THEN
    RETURN 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- ============================================================================
-- PHẦN 4. BẢY HÀM MAPPING  -- NGUỒN CHÂN LÝ DUY NHẤT
-- ----------------------------------------------------------------------------
-- Cả 7 hàm cùng một khuôn, đọc cạnh nhau sẽ thấy ngay chỗ khác biệt:
--
--   1. DELETE các dòng phẳng của những dòng nguồn được chỉ định.
--   2. INSERT lại từ bảng nguồn.
--
-- Điều kiện JOIN chung của mọi hàm:
--   JOIN ke_hoach_vat_tu p ... AND p.period_month ~ '^\d{2}/\d{4}$'
-- Bộ lọc regex này cố ý bỏ qua các kỳ có period_month rỗng hoặc sai định dạng.
-- Kiến trúc cũ không lọc nên TO_DATE sẽ raise và làm HỎNG luôn câu ghi vào
-- bảng nguồn - tức một kỳ dữ liệu bẩn chặn toàn bộ thao tác của người dùng.
-- Nay kỳ bẩn chỉ đơn giản là không có dòng phẳng, sửa period_month rồi chạy
-- dlthvt_rebuild_period là xong.
--
-- 13 cột đầu của mọi hàm là khối chung theo đúng một thứ tự:
--   step_code, source_model, source_res_id,
--   period_id, period_code, period_month, owner_company_id,
--   company_id, company_code, period_company_id, period_company_code,
--   month_key, month_date
-- 4 cột cuối cũng vậy: create_uid, create_date, write_uid, write_date.
-- Phần giữa là các cột riêng của từng bước.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- KD: ke_hoach_kinh_doanh -> 4 dòng/tháng
-- Đơn vị đặt hàng (period_company_id) chính là đơn vị của dòng kế hoạch KD.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dlthvt_map_kd(p_ids INTEGER[])
RETURNS void LANGUAGE sql AS $$
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE source_model = 'ke.hoach.kinh.doanh'
       AND source_res_id = ANY(p_ids);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date,
        ma_sap, nganh_hang, ten_hang, ma_hang, qty, note,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'kd', 'ke.hoach.kinh.doanh', k.id,
        k.period_id, p.code, p.period_month, p.company_id,
        k.company_id, rc.company_code, k.company_id, rc.company_code,
        TO_CHAR(d.md, 'MM/YYYY'), d.md,
        k.ma_sap, nh.ten, k.ten_hang, k.ma_hang, m.qty, k.note,
        k.create_uid, k.create_date, k.write_uid, k.write_date
    FROM ke_hoach_kinh_doanh k
    JOIN ke_hoach_vat_tu p
      ON p.id = k.period_id
     AND p.period_month ~ '^\d{2}/\d{4}$'
    LEFT JOIN res_company rc      ON rc.id = k.company_id
    LEFT JOIN mdm_nganh_hang nh   ON nh.id = k.nganh_hang
    CROSS JOIN LATERAL (
        VALUES (0, k.qty_t0), (1, k.qty_t1), (2, k.qty_t2), (3, k.qty_t3)
    ) AS m(idx, qty)
    CROSS JOIN LATERAL (
        SELECT dlthvt_month_date(p.period_month, m.idx) AS md
    ) AS d
    WHERE k.id = ANY(p_ids);
$$;

-- ---------------------------------------------------------------------------
-- SX: ke_hoach_san_xuat -> 4 dòng/tháng
-- Giống KD hoàn toàn về cấu trúc; company_id ở đây là đơn vị của dòng kế
-- hoạch sản xuất (company_sx_id là nhà máy, không dùng cho bảng phẳng).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dlthvt_map_sx(p_ids INTEGER[])
RETURNS void LANGUAGE sql AS $$
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE source_model = 'ke.hoach.san.xuat'
       AND source_res_id = ANY(p_ids);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date,
        ma_sap, nganh_hang, ten_hang, ma_hang, qty, note,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'sx', 'ke.hoach.san.xuat', s.id,
        s.period_id, p.code, p.period_month, p.company_id,
        s.company_id, rc.company_code, s.company_id, rc.company_code,
        TO_CHAR(d.md, 'MM/YYYY'), d.md,
        s.ma_sap, nh.ten, s.ten_hang, s.ma_hang, m.qty, s.note,
        s.create_uid, s.create_date, s.write_uid, s.write_date
    FROM ke_hoach_san_xuat s
    JOIN ke_hoach_vat_tu p
      ON p.id = s.period_id
     AND p.period_month ~ '^\d{2}/\d{4}$'
    LEFT JOIN res_company rc    ON rc.id = s.company_id
    LEFT JOIN mdm_nganh_hang nh ON nh.id = s.nganh_hang
    CROSS JOIN LATERAL (
        VALUES (0, s.qty_t0), (1, s.qty_t1), (2, s.qty_t2), (3, s.qty_t3)
    ) AS m(idx, qty)
    CROSS JOIN LATERAL (
        SELECT dlthvt_month_date(p.period_month, m.idx) AS md
    ) AS d
    WHERE s.id = ANY(p_ids);
$$;

-- ---------------------------------------------------------------------------
-- B1: ke_hoach_vat_tu_line -> 4 dòng/tháng
-- Khác KD/SX ở 3 cột đối chiếu KD / SX / chênh lệch, và nganh_hang ở bảng này
-- đã là text sẵn nên không cần join mdm_nganh_hang.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dlthvt_map_b1(p_ids INTEGER[])
RETURNS void LANGUAGE sql AS $$
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE source_model = 'ke.hoach.vat.tu.line'
       AND source_res_id = ANY(p_ids);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date,
        ma_sap, nganh_hang, ten_hang, ma_hang, qty, note,
        qty_kinh_doanh, qty_san_xuat, qty_chenh_lech,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b1', 'ke.hoach.vat.tu.line', l.id,
        l.period_id, p.code, p.period_month, p.company_id,
        l.company_id, rc.company_code, l.company_id, rc.company_code,
        TO_CHAR(d.md, 'MM/YYYY'), d.md,
        l.ma_sap, l.nganh_hang, l.ten_hang, l.ma_hang, m.qty, l.note,
        m.qty_kd, m.qty_sx, m.qty_cl,
        l.create_uid, l.create_date, l.write_uid, l.write_date
    FROM ke_hoach_vat_tu_line l
    JOIN ke_hoach_vat_tu p
      ON p.id = l.period_id
     AND p.period_month ~ '^\d{2}/\d{4}$'
    LEFT JOIN res_company rc ON rc.id = l.company_id
    CROSS JOIN LATERAL (
        VALUES
            (0, l.qty_t0, l.qty_kd_t0, l.qty_sx_t0, l.qty_cl_t0),
            (1, l.qty_t1, l.qty_kd_t1, l.qty_sx_t1, l.qty_cl_t1),
            (2, l.qty_t2, l.qty_kd_t2, l.qty_sx_t2, l.qty_cl_t2),
            (3, l.qty_t3, l.qty_kd_t3, l.qty_sx_t3, l.qty_cl_t3)
    ) AS m(idx, qty, qty_kd, qty_sx, qty_cl)
    CROSS JOIN LATERAL (
        SELECT dlthvt_month_date(p.period_month, m.idx) AS md
    ) AS d
    WHERE l.id = ANY(p_ids);
$$;

-- ---------------------------------------------------------------------------
-- B2: dinh_muc -> 4 dòng/tháng
-- sl_dinh_muc_ap_dung = định mức thay đổi nếu người dùng có ghi đè, ngược lại
-- là định mức gốc. Đây là cột mà các bước sau thực sự dùng để tính.
-- period_company_id = company_id giống bản bulk cũ (đường sinh định mức thực tế);
-- trigger row cũ để NULL nên hai đường từng lệch nhau - nay chốt theo bulk.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dlthvt_map_b2(p_ids INTEGER[])
RETURNS void LANGUAGE sql AS $$
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE source_model = 'dinh.muc'
       AND source_res_id = ANY(p_ids);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date,
        ma_sap, ma_vat_tu, ma_tp, ten_tp, ten_sap, ma_nvl, ten_nvl, ten_vat_tu,
        sl_dinh_muc, sl_dinh_muc_thay_doi, sl_dinh_muc_ap_dung,
        qty, qty_kinh_doanh, qty_san_xuat, qty_chenh_lech,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b2', 'dinh.muc', dm.id,
        dm.period_id, p.code, p.period_month, p.company_id,
        dm.company_id, rc.company_code, dm.company_id, rc.company_code,
        TO_CHAR(d.md, 'MM/YYYY'), d.md,
        dm.ma_sap, dm.ma_nvl, dm.ma_tp, dm.ten_tp, dm.ten_sap,
        dm.ma_nvl, dm.ten_nvl, dm.ten_nvl,
        dm.sl_dinh_muc,
        CASE WHEN dm.co_sl_dinh_muc_override THEN dm.sl_dinh_muc_thay_doi END,
        CASE WHEN dm.co_sl_dinh_muc_override
             THEN dm.sl_dinh_muc_thay_doi ELSE dm.sl_dinh_muc END,
        m.qty, m.qty_kd, m.qty_sx, m.qty_cl,
        dm.create_uid, dm.create_date, dm.write_uid, dm.write_date
    FROM dinh_muc dm
    JOIN ke_hoach_vat_tu p
      ON p.id = dm.period_id
     AND p.period_month ~ '^\d{2}/\d{4}$'
    LEFT JOIN res_company rc ON rc.id = dm.company_id
    CROSS JOIN LATERAL (
        VALUES
            (0, dm.qty_t0, dm.qty_kinh_doanh_t0, dm.qty_san_xuat_t0, dm.qty_chenh_lech_t0),
            (1, dm.qty_t1, dm.qty_kinh_doanh_t1, dm.qty_san_xuat_t1, dm.qty_chenh_lech_t1),
            (2, dm.qty_t2, dm.qty_kinh_doanh_t2, dm.qty_san_xuat_t2, dm.qty_chenh_lech_t2),
            (3, dm.qty_t3, dm.qty_kinh_doanh_t3, dm.qty_san_xuat_t3, dm.qty_chenh_lech_t3)
    ) AS m(idx, qty, qty_kd, qty_sx, qty_cl)
    CROSS JOIN LATERAL (
        SELECT dlthvt_month_date(p.period_month, m.idx) AS md
    ) AS d
    WHERE dm.id = ANY(p_ids);
$$;

-- ---------------------------------------------------------------------------
-- B3: tinh_toan_vat_tu -> 4 dòng/tháng
-- Từ bước này trở đi, đơn vị đặt hàng là don_vi_kd_id (không còn là company_id
-- nữa), nên cần join res_company hai lần: một cho đơn vị sản xuất, một cho
-- đơn vị kinh doanh.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dlthvt_map_b3(p_ids INTEGER[])
RETURNS void LANGUAGE sql AS $$
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE source_model = 'tinh.toan.vat.tu'
       AND source_res_id = ANY(p_ids);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date,
        ma_sap, ma_vat_tu, ma_nvl, ten_nvl, ten_vat_tu,
        don_vi_tinh, do_day, kho_1, kho_2, trong_luong_kg_tam, qty,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b3', 'tinh.toan.vat.tu', t.id,
        t.period_id, p.code, p.period_month, p.company_id,
        t.company_id, rc_sx.company_code, t.don_vi_kd_id, rc_kd.company_code,
        TO_CHAR(d.md, 'MM/YYYY'), d.md,
        t.ma_vat_tu, t.ma_vat_tu, t.ma_vat_tu, t.ten_vat_tu, t.ten_vat_tu,
        t.don_vi_tinh, t.do_day, t.kho_1, t.kho_2, t.trong_luong_kg_tam, m.qty,
        t.create_uid, t.create_date, t.write_uid, t.write_date
    FROM tinh_toan_vat_tu t
    JOIN ke_hoach_vat_tu p
      ON p.id = t.period_id
     AND p.period_month ~ '^\d{2}/\d{4}$'
    LEFT JOIN res_company rc_sx ON rc_sx.id = t.company_id
    LEFT JOIN res_company rc_kd ON rc_kd.id = t.don_vi_kd_id
    CROSS JOIN LATERAL (
        VALUES (0, t.qty_t0), (1, t.qty_t1), (2, t.qty_t2), (3, t.qty_t3)
    ) AS m(idx, qty)
    CROSS JOIN LATERAL (
        SELECT dlthvt_month_date(p.period_month, m.idx) AS md
    ) AS d
    WHERE t.id = ANY(p_ids);
$$;

-- ---------------------------------------------------------------------------
-- B4: tong_hop_vat_tu -> 4 dòng/tháng
-- Lưu ý nghiệp vụ: ton_dau, so_luong_du_phong, so_luong_thieu, so_luong_can_mua
-- ở bảng nguồn là giá trị CỦA CẢ KỲ, không phải theo tháng. ton_dau được lặp
-- lại ở cả 4 tháng (báo cáo cần thấy tồn đầu kỳ trên mọi dòng), còn 3 cột
-- dự phòng/thiếu/cần mua chỉ gán vào tháng cuối (T+3) và để 0 ở 3 tháng đầu
-- để cột tổng của báo cáo không bị cộng trùng 4 lần.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dlthvt_map_b4(p_ids INTEGER[])
RETURNS void LANGUAGE sql AS $$
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE source_model = 'tong.hop.vat.tu'
       AND source_res_id = ANY(p_ids);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date,
        ma_sap, ma_nvl, ten_nvl, ten_vat_tu, don_vi_tinh,
        ma_dat_hang, chung_loai, ton_dau,
        ve_du_kien_don_vi, ve_du_kien, vt_can_dung, ton_cuoi,
        so_luong_du_phong, so_luong_thieu, so_luong_can_mua, ghi_chu,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b4', 'tong.hop.vat.tu', th.id,
        th.period_id, p.code, p.period_month, p.company_id,
        th.company_id, rc_sx.company_code, th.don_vi_kd_id, rc_kd.company_code,
        TO_CHAR(d.md, 'MM/YYYY'), d.md,
        th.ma_sap, th.ma_sap, th.ten_nvl, th.ten_nvl, th.don_vi_tinh,
        th.ma_dat_hang, th.chung_loai, th.ton_dau,
        m.ve_dv, m.ve_bcu, m.can_dung, m.ton_cuoi,
        CASE WHEN m.idx = 3 THEN th.so_luong_du_phong ELSE 0 END,
        CASE WHEN m.idx = 3 THEN th.so_luong_thieu    ELSE 0 END,
        CASE WHEN m.idx = 3 THEN th.so_luong_can_mua  ELSE 0 END,
        th.ghi_chu,
        th.create_uid, th.create_date, th.write_uid, th.write_date
    FROM tong_hop_vat_tu th
    JOIN ke_hoach_vat_tu p
      ON p.id = th.period_id
     AND p.period_month ~ '^\d{2}/\d{4}$'
    LEFT JOIN res_company rc_sx ON rc_sx.id = th.company_id
    LEFT JOIN res_company rc_kd ON rc_kd.id = th.don_vi_kd_id
    CROSS JOIN LATERAL (
        VALUES
            (0, th.ve_du_kien_don_vi_t0, th.ve_du_kien_t0, th.vt_can_dung_t0, th.ton_cuoi_t0),
            (1, th.ve_du_kien_don_vi_t1, th.ve_du_kien_t1, th.vt_can_dung_t1, th.ton_cuoi_t1),
            (2, th.ve_du_kien_don_vi_t2, th.ve_du_kien_t2, th.vt_can_dung_t2, th.ton_cuoi_t2),
            (3, th.ve_du_kien_don_vi_t3, th.ve_du_kien_t3, th.vt_can_dung_t3, th.ton_cuoi_t3)
    ) AS m(idx, ve_dv, ve_bcu, can_dung, ton_cuoi)
    CROSS JOIN LATERAL (
        SELECT dlthvt_month_date(p.period_month, m.idx) AS md
    ) AS d
    WHERE th.id = ANY(p_ids);
$$;

-- ---------------------------------------------------------------------------
-- B5: kh_dat_vat_tu -> ĐÚNG 1 dòng (không tách theo tháng)
-- Bảng nguồn của B5 đã gộp cả kỳ thành một dòng cho mỗi mã NVL, các cột *_t0..t3
-- nằm ngang trên chính dòng đó. Vì vậy chỉ sinh 1 dòng phẳng ở tháng T0.
-- Ba cặp cột "alias" (tong_sl_vt_can_dung, tong_hang_di_duong_sl, sl_ton_kho,
-- gia_tri_ton_kho) là bản sao để các view báo cáo cũ gọi được tên quen thuộc.
-- B5 là mức BCU nên không thuộc đơn vị đặt hàng nào -> period_company_id NULL.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dlthvt_map_b5(p_ids INTEGER[])
RETURNS void LANGUAGE sql AS $$
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE source_model = 'kh.dat.vat.tu'
       AND source_res_id = ANY(p_ids);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, period_code, period_month, owner_company_id,
        company_id, company_code,
        month_key, month_date,
        ma_sap, ma_nvl, ten_nvl, ten_vat_tu, don_vi_tinh, chung_loai,
        tong_ton_nvl_sl, don_gia_ton_kho, gia_tri_ton_nvl_dau_ky,
        tong_sl_vt_can_dung_t0, tong_sl_vt_can_dung_t1,
        tong_sl_vt_can_dung_t2, tong_sl_vt_can_dung_t3,
        tong_vt_can_dung, tong_sl_vt_can_dung,
        tong_hang_di_duong_sl_t0, tong_hang_di_duong_sl_t1,
        tong_hang_di_duong_sl_t2, tong_hang_di_duong_sl_t3,
        tong_hang_di_duong, tong_hang_di_duong_sl,
        sl_du_tru_toi_thieu, sl_can_mua_theo_moq,
        sl_dat_mua_de_xuat, sl_dat_mua_chot,
        don_gia_mua, gia_tri_mua_hang,
        sl_ton_kho_cuoi_ky, sl_ton_kho,
        vt_loi_ton_lau, so_ngay_vong_quay_ton,
        don_gia_ton_kho_cuoi_ky, gia_tri_ton_kho_cuoi_ky, gia_tri_ton_kho,
        ghi_chu,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b5', 'kh.dat.vat.tu', k.id,
        k.period_id, p.code, p.period_month, p.company_id,
        k.company_id, rc.company_code,
        TO_CHAR(d.md, 'MM/YYYY'), d.md,
        k.ma_sap, k.ma_sap, k.ten_nvl, k.ten_nvl, k.don_vi_tinh, k.chung_loai,
        k.tong_ton_nvl_sl, k.don_gia_ton_kho,
        COALESCE(k.tong_ton_nvl_sl, 0) * COALESCE(k.don_gia_ton_kho, 0),
        k.tong_sl_vt_can_dung_t0, k.tong_sl_vt_can_dung_t1,
        k.tong_sl_vt_can_dung_t2, k.tong_sl_vt_can_dung_t3,
        k.tong_vt_can_dung, k.tong_vt_can_dung,
        k.tong_hang_di_duong_sl_t0, k.tong_hang_di_duong_sl_t1,
        k.tong_hang_di_duong_sl_t2, k.tong_hang_di_duong_sl_t3,
        k.tong_hang_di_duong, k.tong_hang_di_duong,
        k.sl_du_tru_toi_thieu, k.sl_can_mua_theo_moq,
        k.sl_dat_mua_de_xuat, k.sl_dat_mua_chot,
        k.don_gia_mua, k.gia_tri_mua_hang,
        k.sl_ton_kho_cuoi_ky, k.sl_ton_kho_cuoi_ky,
        k.vt_loi_ton_lau, k.so_ngay_vong_quay_ton,
        k.don_gia_ton_kho_cuoi_ky, k.gia_tri_ton_kho_cuoi_ky, k.gia_tri_ton_kho_cuoi_ky,
        k.ghi_chu,
        k.create_uid, k.create_date, k.write_uid, k.write_date
    FROM kh_dat_vat_tu k
    JOIN ke_hoach_vat_tu p
      ON p.id = k.period_id
     AND p.period_month ~ '^\d{2}/\d{4}$'
    LEFT JOIN res_company rc ON rc.id = k.company_id
    CROSS JOIN LATERAL (
        SELECT dlthvt_month_date(p.period_month, 0) AS md
    ) AS d
    WHERE k.id = ANY(p_ids);
$$;


-- ============================================================================
-- PHẦN 5. TRIGGER
-- ----------------------------------------------------------------------------
-- Chỉ có ĐÚNG HAI hàm trigger cho cả 7 bước. Bước nào được truyền vào qua
-- tham số TG_ARGV[0] khi khai báo trigger, nên thêm bước mới không phải viết
-- thêm hàm trigger.
--
-- Mỗi bảng nguồn cần 3 trigger riêng vì PostgreSQL không cho phép một trigger
-- vừa có transition table vừa gắn nhiều sự kiện:
--     "transition tables cannot be specified for triggers with more than one event"
-- INSERT và UPDATE dùng chung hàm (cùng đọc newtab), DELETE dùng hàm riêng.
--
-- Về INSERT ... ON CONFLICT DO UPDATE trên bảng nguồn: PostgreSQL tách đúng
-- phần chèn sang trigger INSERT và phần cập nhật sang trigger UPDATE, nên cả
-- hai được xử lý đầy đủ mà không trùng nhau.
-- ============================================================================

-- Dòng nguồn được thêm hoặc sửa: dựng lại các dòng phẳng của chúng.
CREATE OR REPLACE FUNCTION dlthvt_after_change() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE
    v_ids INTEGER[] := ARRAY(SELECT id FROM newtab);
BEGIN
    -- Câu lệnh không chạm dòng nào vẫn kích hoạt trigger mức câu lệnh.
    IF cardinality(v_ids) = 0 THEN
        RETURN NULL;
    END IF;

    CASE TG_ARGV[0]
        WHEN 'kd' THEN PERFORM dlthvt_map_kd(v_ids);
        WHEN 'sx' THEN PERFORM dlthvt_map_sx(v_ids);
        WHEN 'b1' THEN PERFORM dlthvt_map_b1(v_ids);
        WHEN 'b2' THEN PERFORM dlthvt_map_b2(v_ids);
        WHEN 'b3' THEN PERFORM dlthvt_map_b3(v_ids);
        WHEN 'b4' THEN PERFORM dlthvt_map_b4(v_ids);
        WHEN 'b5' THEN PERFORM dlthvt_map_b5(v_ids);
    END CASE;

    RETURN NULL;
END;
$$;

-- Dòng nguồn bị xoá: dọn các dòng phẳng tương ứng. Điều kiện lọc khớp đúng
-- hai cột đầu của khoá duy nhất nên luôn đi bằng index.
CREATE OR REPLACE FUNCTION dlthvt_after_delete() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE source_model = TG_ARGV[0]
       AND source_res_id IN (SELECT id FROM oldtab);
    RETURN NULL;
END;
$$;

-- --- KD ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_dlthvt_kd_ins ON ke_hoach_kinh_doanh;
CREATE TRIGGER trg_dlthvt_kd_ins AFTER INSERT ON ke_hoach_kinh_doanh
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('kd');

DROP TRIGGER IF EXISTS trg_dlthvt_kd_upd ON ke_hoach_kinh_doanh;
CREATE TRIGGER trg_dlthvt_kd_upd AFTER UPDATE ON ke_hoach_kinh_doanh
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('kd');

DROP TRIGGER IF EXISTS trg_dlthvt_kd_del ON ke_hoach_kinh_doanh;
CREATE TRIGGER trg_dlthvt_kd_del AFTER DELETE ON ke_hoach_kinh_doanh
REFERENCING OLD TABLE AS oldtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_delete('ke.hoach.kinh.doanh');

-- --- SX ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_dlthvt_sx_ins ON ke_hoach_san_xuat;
CREATE TRIGGER trg_dlthvt_sx_ins AFTER INSERT ON ke_hoach_san_xuat
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('sx');

DROP TRIGGER IF EXISTS trg_dlthvt_sx_upd ON ke_hoach_san_xuat;
CREATE TRIGGER trg_dlthvt_sx_upd AFTER UPDATE ON ke_hoach_san_xuat
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('sx');

DROP TRIGGER IF EXISTS trg_dlthvt_sx_del ON ke_hoach_san_xuat;
CREATE TRIGGER trg_dlthvt_sx_del AFTER DELETE ON ke_hoach_san_xuat
REFERENCING OLD TABLE AS oldtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_delete('ke.hoach.san.xuat');

-- --- B1 ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_dlthvt_b1_ins ON ke_hoach_vat_tu_line;
CREATE TRIGGER trg_dlthvt_b1_ins AFTER INSERT ON ke_hoach_vat_tu_line
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('b1');

DROP TRIGGER IF EXISTS trg_dlthvt_b1_upd ON ke_hoach_vat_tu_line;
CREATE TRIGGER trg_dlthvt_b1_upd AFTER UPDATE ON ke_hoach_vat_tu_line
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('b1');

DROP TRIGGER IF EXISTS trg_dlthvt_b1_del ON ke_hoach_vat_tu_line;
CREATE TRIGGER trg_dlthvt_b1_del AFTER DELETE ON ke_hoach_vat_tu_line
REFERENCING OLD TABLE AS oldtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_delete('ke.hoach.vat.tu.line');

-- --- B2 ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_dlthvt_b2_ins ON dinh_muc;
CREATE TRIGGER trg_dlthvt_b2_ins AFTER INSERT ON dinh_muc
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('b2');

DROP TRIGGER IF EXISTS trg_dlthvt_b2_upd ON dinh_muc;
CREATE TRIGGER trg_dlthvt_b2_upd AFTER UPDATE ON dinh_muc
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('b2');

DROP TRIGGER IF EXISTS trg_dlthvt_b2_del ON dinh_muc;
CREATE TRIGGER trg_dlthvt_b2_del AFTER DELETE ON dinh_muc
REFERENCING OLD TABLE AS oldtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_delete('dinh.muc');

-- --- B3 ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_dlthvt_b3_ins ON tinh_toan_vat_tu;
CREATE TRIGGER trg_dlthvt_b3_ins AFTER INSERT ON tinh_toan_vat_tu
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('b3');

DROP TRIGGER IF EXISTS trg_dlthvt_b3_upd ON tinh_toan_vat_tu;
CREATE TRIGGER trg_dlthvt_b3_upd AFTER UPDATE ON tinh_toan_vat_tu
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('b3');

DROP TRIGGER IF EXISTS trg_dlthvt_b3_del ON tinh_toan_vat_tu;
CREATE TRIGGER trg_dlthvt_b3_del AFTER DELETE ON tinh_toan_vat_tu
REFERENCING OLD TABLE AS oldtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_delete('tinh.toan.vat.tu');

-- --- B4 ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_dlthvt_b4_ins ON tong_hop_vat_tu;
CREATE TRIGGER trg_dlthvt_b4_ins AFTER INSERT ON tong_hop_vat_tu
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('b4');

DROP TRIGGER IF EXISTS trg_dlthvt_b4_upd ON tong_hop_vat_tu;
CREATE TRIGGER trg_dlthvt_b4_upd AFTER UPDATE ON tong_hop_vat_tu
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('b4');

DROP TRIGGER IF EXISTS trg_dlthvt_b4_del ON tong_hop_vat_tu;
CREATE TRIGGER trg_dlthvt_b4_del AFTER DELETE ON tong_hop_vat_tu
REFERENCING OLD TABLE AS oldtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_delete('tong.hop.vat.tu');

-- --- B5 ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_dlthvt_b5_ins ON kh_dat_vat_tu;
CREATE TRIGGER trg_dlthvt_b5_ins AFTER INSERT ON kh_dat_vat_tu
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('b5');

DROP TRIGGER IF EXISTS trg_dlthvt_b5_upd ON kh_dat_vat_tu;
CREATE TRIGGER trg_dlthvt_b5_upd AFTER UPDATE ON kh_dat_vat_tu
REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_change('b5');

DROP TRIGGER IF EXISTS trg_dlthvt_b5_del ON kh_dat_vat_tu;
CREATE TRIGGER trg_dlthvt_b5_del AFTER DELETE ON kh_dat_vat_tu
REFERENCING OLD TABLE AS oldtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_delete('kh.dat.vat.tu');


-- ============================================================================
-- PHẦN 6. DỰNG LẠI BẢNG PHẲNG
-- ----------------------------------------------------------------------------
-- Dùng khi kỳ đổi tháng bắt đầu, khi cập nhật module, hoặc khi cần kiểm tra
-- lại tính đúng đắn. Cả hai hàm đều idempotent.
-- ============================================================================

CREATE OR REPLACE FUNCTION dlthvt_rebuild_period(p_period_id INTEGER)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    -- Xoá sạch theo kỳ trước, vì nếu period_month đổi thì month_key của mọi
    -- dòng cũ đều sai và không thể đối chiếu lại theo khoá được nữa.
    DELETE FROM du_lieu_tong_hop_vat_tu WHERE period_id = p_period_id;

    PERFORM dlthvt_map_kd(ARRAY(SELECT id FROM ke_hoach_kinh_doanh  WHERE period_id = p_period_id));
    PERFORM dlthvt_map_sx(ARRAY(SELECT id FROM ke_hoach_san_xuat    WHERE period_id = p_period_id));
    PERFORM dlthvt_map_b1(ARRAY(SELECT id FROM ke_hoach_vat_tu_line WHERE period_id = p_period_id));
    PERFORM dlthvt_map_b2(ARRAY(SELECT id FROM dinh_muc             WHERE period_id = p_period_id));
    PERFORM dlthvt_map_b3(ARRAY(SELECT id FROM tinh_toan_vat_tu     WHERE period_id = p_period_id));
    PERFORM dlthvt_map_b4(ARRAY(SELECT id FROM tong_hop_vat_tu      WHERE period_id = p_period_id));
    PERFORM dlthvt_map_b5(ARRAY(SELECT id FROM kh_dat_vat_tu        WHERE period_id = p_period_id));
END;
$$;

CREATE OR REPLACE FUNCTION dlthvt_rebuild_all()
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    r RECORD;
BEGIN
    -- Dọn cả những dòng mồ côi không còn kỳ nào trỏ tới.
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE period_id IS NULL
        OR period_id NOT IN (SELECT id FROM ke_hoach_vat_tu);

    -- Đi theo từng kỳ để mảng id không phình quá lớn.
    FOR r IN SELECT id FROM ke_hoach_vat_tu ORDER BY id LOOP
        PERFORM dlthvt_rebuild_period(r.id);
    END LOOP;
END;
$$;


-- ============================================================================
-- PHẦN 7. KỲ ĐỔI THÔNG TIN
-- ----------------------------------------------------------------------------
-- period_month quyết định month_key/month_date của MỌI dòng phẳng thuộc kỳ,
-- mà month_key lại nằm trong khoá duy nhất, nên đổi nó thì buộc phải dựng lại
-- cả kỳ. Còn đổi code hay đơn vị lập kế hoạch thì chỉ là cột meta, cập nhật
-- tại chỗ bằng một câu UPDATE là đủ.
-- ============================================================================

CREATE OR REPLACE FUNCTION dlthvt_after_period_update() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE
    r RECORD;
BEGIN
    -- Bỏ qua câu UPDATE không đụng 3 cột meta của kỳ.
    IF NOT EXISTS (
        SELECT 1
          FROM newtab n
          JOIN oldtab o ON o.id = n.id
         WHERE n.period_month IS DISTINCT FROM o.period_month
            OR n.code         IS DISTINCT FROM o.code
            OR n.company_id   IS DISTINCT FROM o.company_id
    ) THEN
        RETURN NULL;
    END IF;

    -- (a) Kỳ đổi tháng bắt đầu -> dựng lại toàn bộ.
    FOR r IN
        SELECT n.id
          FROM newtab n
          JOIN oldtab o ON o.id = n.id
         WHERE n.period_month IS DISTINCT FROM o.period_month
    LOOP
        PERFORM dlthvt_rebuild_period(r.id);
    END LOOP;

    -- (b) Kỳ chỉ đổi số chứng từ / đơn vị lập kế hoạch -> sửa meta tại chỗ.
    UPDATE du_lieu_tong_hop_vat_tu d
       SET period_code      = n.code,
           owner_company_id = n.company_id,
           write_uid        = COALESCE(n.write_uid, d.write_uid),
           write_date       = NOW() AT TIME ZONE 'UTC'
      FROM newtab n
      JOIN oldtab o ON o.id = n.id
     WHERE d.period_id = n.id
       AND n.period_month IS NOT DISTINCT FROM o.period_month
       AND (n.code IS DISTINCT FROM o.code
            OR n.company_id IS DISTINCT FROM o.company_id);

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_dlthvt_period_upd ON ke_hoach_vat_tu;
-- Không dùng "UPDATE OF col1, col2": PostgreSQL cấm kết hợp danh sách cột
-- với transition table. Lọc cột thay đổi nằm trong thân hàm ở trên.
CREATE TRIGGER trg_dlthvt_period_upd
AFTER UPDATE ON ke_hoach_vat_tu
REFERENCING OLD TABLE AS oldtab NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_period_update();


-- ============================================================================
-- PHẦN 8. ĐỒNG BỘ BOM TỪ SAP:  md_sap_bom -> bom
-- ----------------------------------------------------------------------------
-- Bảng md_sap_bom do module MDM nạp về từ SAP và rất lớn (hàng trăm nghìn
-- dòng), nên trigger mức dòng ở kiến trúc cũ là không dùng được: mỗi lần nạp
-- lại SAP là hàng trăm nghìn lần gọi trigger. Nay cũng dùng trigger mức câu
-- lệnh, và quan trọng hơn: phần backfill dùng CHUNG hàm với trigger.
--
-- Kiến trúc cũ có hai bản mapping (thân trigger và câu backfill) và chúng ĐÃ
-- lệch nhau thật: trigger điền sl_spdm = 1.0 khi giá trị rỗng, còn backfill
-- để NULL - làm các bước sau chia cho NULL. Nay chỉ còn một bản nên hết lệch.
--
-- Một mã (ma_tp, ma_nvl) có thể xuất hiện nhiều lần trong md_sap_bom;
-- DISTINCT ON ... ORDER BY id DESC lấy bản ghi mới nhất.
-- do_day / kho_1 / kho_2 chỉ đặt 0 khi tạo mới và không bao giờ ghi đè, vì đó
-- là số người dùng tự nhập trong Odoo, SAP không có.
-- ============================================================================

CREATE OR REPLACE FUNCTION bom_sync_from_sap(p_ids INTEGER[] DEFAULT NULL)
RETURNS void LANGUAGE sql AS $$
    INSERT INTO bom (
        ma_tp, ten_tp, ma_nvl, ten_nvl, sl_dinh_muc, sl_spdm,
        do_day, kho_1, kho_2,
        create_uid, create_date, write_uid, write_date
    )
    SELECT DISTINCT ON (TRIM(s.ma_tp), TRIM(s.ma_nvl))
        TRIM(s.ma_tp),
        COALESCE(NULLIF(TRIM(s.ten_tp),  ''), TRIM(s.ma_tp)),
        TRIM(s.ma_nvl),
        COALESCE(NULLIF(TRIM(s.ten_nvl), ''), TRIM(s.ma_nvl)),
        safe_sap_numeric(s.sl_dm),
        COALESCE(NULLIF(safe_sap_numeric(s.sl_spdm), 0), 1.0),
        0, 0, 0,
        1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC'
    FROM md_sap_bom s
    WHERE (p_ids IS NULL OR s.id = ANY(p_ids))
      AND s.ma_tp  IS NOT NULL AND TRIM(s.ma_tp)  <> ''
      AND s.ma_nvl IS NOT NULL AND TRIM(s.ma_nvl) <> ''
    ORDER BY TRIM(s.ma_tp), TRIM(s.ma_nvl), s.id DESC
    ON CONFLICT (ma_tp, ma_nvl) DO UPDATE SET
        ten_tp      = COALESCE(NULLIF(EXCLUDED.ten_tp,  ''), bom.ten_tp),
        ten_nvl     = COALESCE(NULLIF(EXCLUDED.ten_nvl, ''), bom.ten_nvl),
        sl_dinh_muc = EXCLUDED.sl_dinh_muc,
        sl_spdm     = COALESCE(EXCLUDED.sl_spdm, bom.sl_spdm, 1.0),
        write_date  = NOW() AT TIME ZONE 'UTC';
$$;

CREATE OR REPLACE FUNCTION bom_after_sap_change() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE
    v_ids INTEGER[] := ARRAY(SELECT id FROM newtab);
BEGIN
    IF cardinality(v_ids) > 0 THEN
        PERFORM bom_sync_from_sap(v_ids);
    END IF;
    RETURN NULL;
END;
$$;

-- md_sap_bom thuộc module khác nên có thể chưa tồn tại khi cài module này.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'md_sap_bom'
    ) THEN
        DROP TRIGGER IF EXISTS trg_sync_sap_bom     ON md_sap_bom;
        DROP TRIGGER IF EXISTS trg_sync_sap_bom_ins ON md_sap_bom;
        DROP TRIGGER IF EXISTS trg_sync_sap_bom_upd ON md_sap_bom;

        CREATE TRIGGER trg_sync_sap_bom_ins AFTER INSERT ON md_sap_bom
        REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
        EXECUTE FUNCTION bom_after_sap_change();

        CREATE TRIGGER trg_sync_sap_bom_upd AFTER UPDATE ON md_sap_bom
        REFERENCING NEW TABLE AS newtab FOR EACH STATEMENT
        EXECUTE FUNCTION bom_after_sap_change();

        -- Backfill dữ liệu SAP đã có sẵn, dùng đúng hàm mà trigger dùng.
        -- NULL = quét toàn bộ bảng, không dựng mảng id hàng trăm nghìn phần tử.
        PERFORM bom_sync_from_sap(NULL);
    END IF;
END $$;

DROP FUNCTION IF EXISTS sync_md_sap_bom_to_bom();


-- ============================================================================
-- PHẦN 9. DỰNG LẠI BẢNG PHẲNG SAU KHI CẬP NHẬT MODULE
-- ----------------------------------------------------------------------------
-- Phép chiếu ở PHẦN 4 có thể thay đổi giữa các phiên bản module, nên dữ liệu
-- phẳng cũ có khả năng đã lỗi thời. Câu dưới đây dựng lại toàn bộ bằng 7 câu
-- lệnh set-based cho mỗi kỳ, chạy mỗi lần cập nhật module.
-- Nếu về sau bảng phẳng lớn tới mức làm chậm việc cập nhật module, có thể bỏ
-- dòng này và chỉ chạy dlthvt_rebuild_period() cho từng kỳ khi cần.
-- ============================================================================

SELECT dlthvt_rebuild_all();

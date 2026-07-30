-- ############################################################################
-- ĐỒNG BỘ BẢNG PHẲNG  du_lieu_tong_hop_vat_tu
-- ============================================================================
-- PHẦN 1. DROP TRIGGER / HÀM
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
-- PHẦN 2. INDEX (báo cáo trên du_lieu_tong_hop_vat_tu)
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

-- Quy tắc tháng T0..T+3: period_month 'MM/YYYY' + offset tháng.
CREATE OR REPLACE FUNCTION dlthvt_month_date(p_period_month TEXT, p_offset INT)
RETURNS DATE
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT (TO_DATE(p_period_month, 'MM/YYYY') + (p_offset || ' month')::INTERVAL)::DATE;
$$;

-- Parse số từ chuỗi SAP (dấu trừ đuôi, phân cách nghìn, rác -> 0).
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
-- PHẦN 4. HÀM MAPPING (KD, SX, B1–B5)
-- ----------------------------------------------------------------------------
-- Mỗi hàm: DELETE dòng phẳng của source_res_id trong p_ids, rồi INSERT lại.
-- Chỉ map kỳ có period_month đúng định dạng MM/YYYY.
-- Khối cột meta đầu/cuối giống nhau giữa các bước; phần giữa là cột riêng từng bước.
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
-- sl_dinh_muc_ap_dung = override nếu có, không thì sl_dinh_muc gốc.
-- period_company_id = company_id của dòng định mức.
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
-- B5: kh_dat_vat_tu -> 1 dòng/tháng T0 (bảng nguồn đã gộp cả kỳ)
-- Một số cột lặp tên alias phục vụ view báo cáo.
-- BCU: period_company_id NULL.
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
-- PHẦN 5. TRIGGER trên bảng nguồn
-- ----------------------------------------------------------------------------
-- dlthvt_after_change: INSERT/UPDATE -> map lại dòng phẳng (tham số bước qua TG_ARGV).
-- dlthvt_after_delete: DELETE -> xóa dòng phẳng theo source_model + source_res_id.
-- Mỗi bảng 3 trigger (ins/upd/del) — PostgreSQL yêu cầu tách sự kiện khi dùng transition table.
-- ============================================================================

-- INSERT/UPDATE nguồn: map lại bảng phẳng.
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

-- DELETE nguồn: xóa dòng phẳng tương ứng.
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
-- PHẦN 6. DỰNG LẠI BẢNG PHẲNG (chạy tay khi cần)
-- ----------------------------------------------------------------------------
-- dlthvt_rebuild_period(id): xóa + map lại một kỳ.
-- dlthvt_rebuild_all(): dọn mồ côi + rebuild mọi kỳ.
-- ============================================================================

CREATE OR REPLACE FUNCTION dlthvt_rebuild_period(p_period_id INTEGER)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
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
    -- Dòng phẳng (period_id NULL hoặc kỳ không còn tồn tại).
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE period_id IS NULL
        OR period_id NOT IN (SELECT id FROM ke_hoach_vat_tu);

    -- Rebuild từng kỳ (tránh mảng id quá lớn).
    FOR r IN SELECT id FROM ke_hoach_vat_tu ORDER BY id LOOP
        PERFORM dlthvt_rebuild_period(r.id);
    END LOOP;
END;
$$;


-- ============================================================================
-- PHẦN 7. TRIGGER ke_hoach_vat_tu (đổi period_month / code / company_id)
-- ----------------------------------------------------------------------------
-- Đổi period_month -> dlthvt_rebuild_period (month_key phụ thuộc tháng bắt đầu).
-- Chỉ đổi code hoặc company_id -> UPDATE meta trên bảng phẳng tại chỗ.
-- ============================================================================

CREATE OR REPLACE FUNCTION dlthvt_after_period_update() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE
    r RECORD;
BEGIN
    -- Bỏ qua UPDATE không đụng period_month, code, company_id.
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

    -- Đổi period_month -> rebuild kỳ.
    FOR r IN
        SELECT n.id
          FROM newtab n
          JOIN oldtab o ON o.id = n.id
         WHERE n.period_month IS DISTINCT FROM o.period_month
    LOOP
        PERFORM dlthvt_rebuild_period(r.id);
    END LOOP;

    -- Chỉ đổi code / company_id -> cập nhật meta bảng phẳng.
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
CREATE TRIGGER trg_dlthvt_period_upd
AFTER UPDATE ON ke_hoach_vat_tu
REFERENCING OLD TABLE AS oldtab NEW TABLE AS newtab FOR EACH STATEMENT
EXECUTE FUNCTION dlthvt_after_period_update();


-- ============================================================================
-- PHẦN 8. ĐỒNG BỘ BOM: md_sap_bom -> bom
-- ----------------------------------------------------------------------------
-- bom_sync_from_sap: UPSERT từ SAP; DISTINCT ON (ma_tp, ma_nvl) lấy bản mới nhất.
-- do_day / kho_1 / kho_2 chỉ set 0 khi tạo mới, không ghi đè khi UPDATE.
-- Trigger mức câu lệnh trên md_sap_bom + nạp lần đầu lúc cài module.
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

        -- Nạp toàn bộ md_sap_bom hiện có sang bom (lần đầu cài module).
        PERFORM bom_sync_from_sap(NULL);
    END IF;
END $$;

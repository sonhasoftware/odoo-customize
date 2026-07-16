-- =============================================================================
-- Rebuild bảng phẳng du_lieu_tong_hop_vat_tu theo kỳ (set-based, 1 lần/kỳ).
-- Gọi sau import/compute bulk; UI vẫn dùng trigger row khi app.dlthvt_skip <> '1'.
-- =============================================================================

CREATE OR REPLACE FUNCTION public.dlthvt_bulk_sync_kd_period(p_period_id INTEGER)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_period_month TEXT;
    v_period_code  TEXT;
    v_owner_company_id INTEGER;
BEGIN
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE step_code = 'kd' AND period_id = p_period_id;

    SELECT code, period_month, company_id
      INTO v_period_code, v_period_month, v_owner_company_id
      FROM ke_hoach_vat_tu WHERE id = p_period_id;

    IF v_period_month IS NULL THEN RETURN; END IF;

    PERFORM set_config('app.dlthvt_bulk', '1', true);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id, period_id,
        period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date, ma_sap, ma_vat_tu,
        nganh_hang, ten_hang, ma_hang, qty, note,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'kd', 'ke.hoach.kinh.doanh', k.id, k.period_id,
        v_period_code, v_period_month, v_owner_company_id,
        k.company_id, rc.company_code, k.company_id, rc.company_code,
        TO_CHAR((TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE, 'MM/YYYY'),
        (TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE,
        k.ma_sap, NULL,
        nh.ten, k.ten_hang, k.ma_hang,
        CASE m.i WHEN 0 THEN k.qty_t0 WHEN 1 THEN k.qty_t1 WHEN 2 THEN k.qty_t2 ELSE k.qty_t3 END,
        k.note,
        k.create_uid, k.create_date, k.write_uid, k.write_date
    FROM ke_hoach_kinh_doanh k
    CROSS JOIN generate_series(0, 3) AS m(i)
    LEFT JOIN res_company rc ON rc.id = k.company_id
    LEFT JOIN mdm_nganh_hang nh ON nh.id = k.nganh_hang
    WHERE k.period_id = p_period_id
    ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
        step_code = EXCLUDED.step_code, period_id = EXCLUDED.period_id,
        period_code = EXCLUDED.period_code, period_month = EXCLUDED.period_month,
        owner_company_id = EXCLUDED.owner_company_id,
        company_id = EXCLUDED.company_id, company_code = EXCLUDED.company_code,
        period_company_id = EXCLUDED.period_company_id,
        period_company_code = EXCLUDED.period_company_code,
        month_date = EXCLUDED.month_date, ma_sap = EXCLUDED.ma_sap,
        nganh_hang = EXCLUDED.nganh_hang, ten_hang = EXCLUDED.ten_hang,
        ma_hang = EXCLUDED.ma_hang, qty = EXCLUDED.qty, note = EXCLUDED.note,
        write_uid = EXCLUDED.write_uid, write_date = EXCLUDED.write_date;

    PERFORM set_config('app.dlthvt_bulk', '', true);
END;
$$;

CREATE OR REPLACE FUNCTION public.dlthvt_bulk_sync_sx_period(p_period_id INTEGER)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_period_month TEXT;
    v_period_code  TEXT;
    v_owner_company_id INTEGER;
BEGIN
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE step_code = 'sx' AND period_id = p_period_id;

    SELECT code, period_month, company_id
      INTO v_period_code, v_period_month, v_owner_company_id
      FROM ke_hoach_vat_tu WHERE id = p_period_id;

    IF v_period_month IS NULL THEN RETURN; END IF;

    PERFORM set_config('app.dlthvt_bulk', '1', true);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id, period_id,
        period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date, ma_sap, ma_vat_tu,
        nganh_hang, ten_hang, ma_hang, qty, note,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'sx', 'ke.hoach.san.xuat', s.id, s.period_id,
        v_period_code, v_period_month, v_owner_company_id,
        s.company_id, rc.company_code, s.company_id, rc.company_code,
        TO_CHAR((TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE, 'MM/YYYY'),
        (TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE,
        s.ma_sap, NULL,
        nh.ten, s.ten_hang, s.ma_hang,
        CASE m.i WHEN 0 THEN s.qty_t0 WHEN 1 THEN s.qty_t1 WHEN 2 THEN s.qty_t2 ELSE s.qty_t3 END,
        s.note,
        s.create_uid, s.create_date, s.write_uid, s.write_date
    FROM ke_hoach_san_xuat s
    CROSS JOIN generate_series(0, 3) AS m(i)
    LEFT JOIN res_company rc ON rc.id = s.company_id
    LEFT JOIN mdm_nganh_hang nh ON nh.id = s.nganh_hang
    WHERE s.period_id = p_period_id
    ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
        step_code = EXCLUDED.step_code, period_id = EXCLUDED.period_id,
        period_code = EXCLUDED.period_code, period_month = EXCLUDED.period_month,
        owner_company_id = EXCLUDED.owner_company_id,
        company_id = EXCLUDED.company_id, company_code = EXCLUDED.company_code,
        period_company_id = EXCLUDED.period_company_id,
        period_company_code = EXCLUDED.period_company_code,
        month_date = EXCLUDED.month_date, ma_sap = EXCLUDED.ma_sap,
        nganh_hang = EXCLUDED.nganh_hang, ten_hang = EXCLUDED.ten_hang,
        ma_hang = EXCLUDED.ma_hang, qty = EXCLUDED.qty, note = EXCLUDED.note,
        write_uid = EXCLUDED.write_uid, write_date = EXCLUDED.write_date;

    PERFORM set_config('app.dlthvt_bulk', '', true);
END;
$$;

CREATE OR REPLACE FUNCTION public.dlthvt_bulk_sync_b1_period(p_period_id INTEGER)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_period_month TEXT;
    v_period_code  TEXT;
    v_owner_company_id INTEGER;
BEGIN
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE step_code = 'b1' AND period_id = p_period_id;

    SELECT code, period_month, company_id
      INTO v_period_code, v_period_month, v_owner_company_id
      FROM ke_hoach_vat_tu WHERE id = p_period_id;

    IF v_period_month IS NULL THEN RETURN; END IF;

    PERFORM set_config('app.dlthvt_bulk', '1', true);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id, period_id,
        period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date, ma_sap, ma_vat_tu,
        nganh_hang, ten_hang, ma_hang,
        qty, note, qty_kinh_doanh, qty_san_xuat, qty_chenh_lech,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b1', 'ke.hoach.vat.tu.line', l.id, l.period_id,
        v_period_code, v_period_month, v_owner_company_id,
        l.company_id, rc.company_code, l.company_id, rc.company_code,
        TO_CHAR((TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE, 'MM/YYYY'),
        (TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE,
        l.ma_sap, NULL, l.nganh_hang, l.ten_hang, l.ma_hang,
        CASE m.i WHEN 0 THEN l.qty_t0 WHEN 1 THEN l.qty_t1 WHEN 2 THEN l.qty_t2 ELSE l.qty_t3 END,
        l.note,
        CASE m.i WHEN 0 THEN l.qty_kd_t0 WHEN 1 THEN l.qty_kd_t1 WHEN 2 THEN l.qty_kd_t2 ELSE l.qty_kd_t3 END,
        CASE m.i WHEN 0 THEN l.qty_sx_t0 WHEN 1 THEN l.qty_sx_t1 WHEN 2 THEN l.qty_sx_t2 ELSE l.qty_sx_t3 END,
        CASE m.i WHEN 0 THEN l.qty_cl_t0 WHEN 1 THEN l.qty_cl_t1 WHEN 2 THEN l.qty_cl_t2 ELSE l.qty_cl_t3 END,
        l.create_uid, l.create_date, l.write_uid, l.write_date
    FROM ke_hoach_vat_tu_line l
    CROSS JOIN generate_series(0, 3) AS m(i)
    LEFT JOIN res_company rc ON rc.id = l.company_id
    WHERE l.period_id = p_period_id
    ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
        step_code = EXCLUDED.step_code, period_id = EXCLUDED.period_id,
        period_code = EXCLUDED.period_code, period_month = EXCLUDED.period_month,
        owner_company_id = EXCLUDED.owner_company_id,
        company_id = EXCLUDED.company_id, company_code = EXCLUDED.company_code,
        period_company_id = EXCLUDED.period_company_id,
        period_company_code = EXCLUDED.period_company_code,
        month_date = EXCLUDED.month_date, ma_sap = EXCLUDED.ma_sap,
        nganh_hang = EXCLUDED.nganh_hang, ten_hang = EXCLUDED.ten_hang,
        ma_hang = EXCLUDED.ma_hang, qty = EXCLUDED.qty, note = EXCLUDED.note,
        qty_kinh_doanh = EXCLUDED.qty_kinh_doanh, qty_san_xuat = EXCLUDED.qty_san_xuat,
        qty_chenh_lech = EXCLUDED.qty_chenh_lech,
        write_uid = EXCLUDED.write_uid, write_date = EXCLUDED.write_date;

    PERFORM set_config('app.dlthvt_bulk', '', true);
END;
$$;

CREATE OR REPLACE FUNCTION public.dlthvt_bulk_sync_b2_period(p_period_id INTEGER)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_period_month TEXT;
    v_period_code  TEXT;
    v_owner_company_id INTEGER;
    v_month_base   DATE;
    v_k0 TEXT; v_k1 TEXT; v_k2 TEXT; v_k3 TEXT;
    v_d0 DATE; v_d1 DATE; v_d2 DATE; v_d3 DATE;
BEGIN
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE step_code = 'b2' AND period_id = p_period_id;

    SELECT code, period_month, company_id
      INTO v_period_code, v_period_month, v_owner_company_id
      FROM ke_hoach_vat_tu WHERE id = p_period_id;

    IF v_period_month IS NULL THEN RETURN; END IF;

    v_month_base := TO_DATE(v_period_month, 'MM/YYYY');
    v_d0 := v_month_base;
    v_d1 := (v_month_base + INTERVAL '1 month')::DATE;
    v_d2 := (v_month_base + INTERVAL '2 month')::DATE;
    v_d3 := (v_month_base + INTERVAL '3 month')::DATE;
    v_k0 := TO_CHAR(v_d0, 'MM/YYYY');
    v_k1 := TO_CHAR(v_d1, 'MM/YYYY');
    v_k2 := TO_CHAR(v_d2, 'MM/YYYY');
    v_k3 := TO_CHAR(v_d3, 'MM/YYYY');

    PERFORM set_config('app.dlthvt_bulk', '1', true);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id, period_id,
        period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date, ma_sap, ma_vat_tu,
        qty, ma_tp, ten_tp, ten_sap, ma_nvl, bom_sale_id, ten_nvl, ten_vat_tu, sl_dinh_muc,
        qty_kinh_doanh, qty_san_xuat, qty_chenh_lech,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b2', 'dinh.muc', d.id, d.period_id,
        v_period_code, v_period_month, v_owner_company_id,
        d.company_id, rc.company_code, d.company_id, rc.company_code,
        m.month_key, m.month_date,
        d.ma_sap, d.ma_nvl,
        m.qty,
        d.ma_tp, d.ten_tp, d.ten_sap, d.ma_nvl, d.bom_sale_id, d.ten_nvl, d.ten_nvl, d.sl_dinh_muc,
        m.qty_kd, m.qty_sx, m.qty_cl,
        d.create_uid, d.create_date, d.write_uid, d.write_date
    FROM dinh_muc d
    LEFT JOIN res_company rc ON rc.id = d.company_id
    CROSS JOIN LATERAL (
        VALUES
            (v_k0, v_d0, d.qty_t0, d.qty_kinh_doanh_t0, d.qty_san_xuat_t0, d.qty_chenh_lech_t0),
            (v_k1, v_d1, d.qty_t1, d.qty_kinh_doanh_t1, d.qty_san_xuat_t1, d.qty_chenh_lech_t1),
            (v_k2, v_d2, d.qty_t2, d.qty_kinh_doanh_t2, d.qty_san_xuat_t2, d.qty_chenh_lech_t2),
            (v_k3, v_d3, d.qty_t3, d.qty_kinh_doanh_t3, d.qty_san_xuat_t3, d.qty_chenh_lech_t3)
    ) AS m(month_key, month_date, qty, qty_kd, qty_sx, qty_cl)
    WHERE d.period_id = p_period_id;

    PERFORM set_config('app.dlthvt_bulk', '', true);
END;
$$;

CREATE OR REPLACE FUNCTION public.dlthvt_bulk_sync_b3_period(p_period_id INTEGER)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_period_month TEXT;
    v_period_code  TEXT;
    v_owner_company_id INTEGER;
BEGIN
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE step_code = 'b3' AND period_id = p_period_id;

    SELECT code, period_month, company_id
      INTO v_period_code, v_period_month, v_owner_company_id
      FROM ke_hoach_vat_tu WHERE id = p_period_id;

    IF v_period_month IS NULL THEN RETURN; END IF;

    PERFORM set_config('app.dlthvt_bulk', '1', true);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id, period_id,
        period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date, ma_sap, ma_vat_tu,
        qty, ma_nvl, ten_nvl, ten_vat_tu,
        don_vi_tinh, do_day, kho_1, kho_2, trong_luong_kg_tam,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b3', 'tinh.toan.vat.tu', t.id, t.period_id,
        v_period_code, v_period_month, v_owner_company_id,
        t.company_id, rc_sx.company_code, t.don_vi_kd_id, rc_kd.company_code,
        TO_CHAR((TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE, 'MM/YYYY'),
        (TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE,
        t.ma_vat_tu, t.ma_vat_tu,
        CASE m.i WHEN 0 THEN t.qty_t0 WHEN 1 THEN t.qty_t1 WHEN 2 THEN t.qty_t2 ELSE t.qty_t3 END,
        t.ma_vat_tu, t.ten_vat_tu, t.ten_vat_tu,
        t.don_vi_tinh, t.do_day, t.kho_1, t.kho_2, t.trong_luong_kg_tam,
        t.create_uid, t.create_date, t.write_uid, t.write_date
    FROM tinh_toan_vat_tu t
    CROSS JOIN generate_series(0, 3) AS m(i)
    LEFT JOIN res_company rc_sx ON rc_sx.id = t.company_id
    LEFT JOIN res_company rc_kd ON rc_kd.id = t.don_vi_kd_id
    WHERE t.period_id = p_period_id
    ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
        step_code = EXCLUDED.step_code, period_id = EXCLUDED.period_id,
        period_code = EXCLUDED.period_code, period_month = EXCLUDED.period_month,
        owner_company_id = EXCLUDED.owner_company_id,
        company_id = EXCLUDED.company_id, company_code = EXCLUDED.company_code,
        period_company_id = EXCLUDED.period_company_id,
        period_company_code = EXCLUDED.period_company_code,
        month_date = EXCLUDED.month_date, ma_sap = EXCLUDED.ma_sap,
        ma_vat_tu = EXCLUDED.ma_vat_tu, qty = EXCLUDED.qty,
        ma_nvl = EXCLUDED.ma_nvl, ten_nvl = EXCLUDED.ten_nvl,
        ten_vat_tu = EXCLUDED.ten_vat_tu,
        don_vi_tinh = EXCLUDED.don_vi_tinh,
        do_day = EXCLUDED.do_day, kho_1 = EXCLUDED.kho_1, kho_2 = EXCLUDED.kho_2,
        trong_luong_kg_tam = EXCLUDED.trong_luong_kg_tam,
        write_uid = EXCLUDED.write_uid, write_date = EXCLUDED.write_date;

    PERFORM set_config('app.dlthvt_bulk', '', true);
END;
$$;

CREATE OR REPLACE FUNCTION public.dlthvt_bulk_sync_b4_period(p_period_id INTEGER)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_period_month TEXT;
    v_period_code  TEXT;
    v_owner_company_id INTEGER;
BEGIN
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE step_code = 'b4' AND period_id = p_period_id;

    SELECT code, period_month, company_id
      INTO v_period_code, v_period_month, v_owner_company_id
      FROM ke_hoach_vat_tu WHERE id = p_period_id;

    IF v_period_month IS NULL THEN RETURN; END IF;

    PERFORM set_config('app.dlthvt_bulk', '1', true);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id, period_id,
        period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date, ma_sap, ma_nvl,
        ten_nvl, ten_vat_tu, don_vi_tinh, ma_dat_hang, chung_loai,
        ton_dau, ve_du_kien_don_vi, ve_du_kien, vt_can_dung, ton_cuoi,
        so_luong_du_phong, so_luong_thieu, so_luong_can_mua, ghi_chu,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b4', 'tong.hop.vat.tu', th.id, th.period_id,
        v_period_code, v_period_month, v_owner_company_id,
        th.company_id, rc_sx.company_code, th.don_vi_kd_id, rc_kd.company_code,
        TO_CHAR((TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE, 'MM/YYYY'),
        (TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE,
        th.ma_sap, th.ma_sap, th.ten_nvl, th.ten_nvl, th.don_vi_tinh,
        th.ma_dat_hang, th.chung_loai, th.ton_dau,
        CASE m.i WHEN 0 THEN th.ve_du_kien_don_vi_t0 WHEN 1 THEN th.ve_du_kien_don_vi_t1
                 WHEN 2 THEN th.ve_du_kien_don_vi_t2 ELSE th.ve_du_kien_don_vi_t3 END,
        CASE m.i WHEN 0 THEN th.ve_du_kien_t0 WHEN 1 THEN th.ve_du_kien_t1
                 WHEN 2 THEN th.ve_du_kien_t2 ELSE th.ve_du_kien_t3 END,
        CASE m.i WHEN 0 THEN th.vt_can_dung_t0 WHEN 1 THEN th.vt_can_dung_t1
                 WHEN 2 THEN th.vt_can_dung_t2 ELSE th.vt_can_dung_t3 END,
        CASE m.i WHEN 0 THEN th.ton_cuoi_t0 WHEN 1 THEN th.ton_cuoi_t1
                 WHEN 2 THEN th.ton_cuoi_t2 ELSE th.ton_cuoi_t3 END,
        CASE WHEN m.i = 3 THEN th.so_luong_du_phong ELSE 0 END,
        CASE WHEN m.i = 3 THEN th.so_luong_thieu ELSE 0 END,
        CASE WHEN m.i = 3 THEN th.so_luong_can_mua ELSE 0 END,
        th.ghi_chu,
        th.create_uid, th.create_date, th.write_uid, th.write_date
    FROM tong_hop_vat_tu th
    CROSS JOIN generate_series(0, 3) AS m(i)
    LEFT JOIN res_company rc_sx ON rc_sx.id = th.company_id
    LEFT JOIN res_company rc_kd ON rc_kd.id = th.don_vi_kd_id
    WHERE th.period_id = p_period_id
    ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
        step_code = EXCLUDED.step_code, period_id = EXCLUDED.period_id,
        period_code = EXCLUDED.period_code, period_month = EXCLUDED.period_month,
        owner_company_id = EXCLUDED.owner_company_id,
        company_id = EXCLUDED.company_id, company_code = EXCLUDED.company_code,
        period_company_id = EXCLUDED.period_company_id,
        period_company_code = EXCLUDED.period_company_code,
        month_date = EXCLUDED.month_date, ma_sap = EXCLUDED.ma_sap,
        ma_nvl = EXCLUDED.ma_nvl, ten_nvl = EXCLUDED.ten_nvl,
        ten_vat_tu = EXCLUDED.ten_vat_tu, don_vi_tinh = EXCLUDED.don_vi_tinh,
        ma_dat_hang = EXCLUDED.ma_dat_hang, chung_loai = EXCLUDED.chung_loai,
        ton_dau = EXCLUDED.ton_dau, ve_du_kien_don_vi = EXCLUDED.ve_du_kien_don_vi,
        ve_du_kien = EXCLUDED.ve_du_kien, vt_can_dung = EXCLUDED.vt_can_dung,
        ton_cuoi = EXCLUDED.ton_cuoi, so_luong_du_phong = EXCLUDED.so_luong_du_phong,
        so_luong_thieu = EXCLUDED.so_luong_thieu, so_luong_can_mua = EXCLUDED.so_luong_can_mua,
        ghi_chu = EXCLUDED.ghi_chu, write_uid = EXCLUDED.write_uid,
        write_date = EXCLUDED.write_date;

    PERFORM set_config('app.dlthvt_bulk', '', true);
END;
$$;

CREATE OR REPLACE FUNCTION public.dlthvt_bulk_sync_b5_period(p_period_id INTEGER)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_period_month TEXT;
    v_period_code  TEXT;
    v_owner_company_id INTEGER;
    v_month_key TEXT;
    v_month_date DATE;
BEGIN
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE step_code = 'b5' AND period_id = p_period_id;

    SELECT code, period_month, company_id
      INTO v_period_code, v_period_month, v_owner_company_id
      FROM ke_hoach_vat_tu WHERE id = p_period_id;

    IF v_period_month IS NULL THEN RETURN; END IF;

    v_month_date := TO_DATE(v_period_month, 'MM/YYYY');
    v_month_key := TO_CHAR(v_month_date, 'MM/YYYY');

    PERFORM set_config('app.dlthvt_bulk', '1', true);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id, period_id,
        period_code, period_month, owner_company_id,
        company_id, company_code,
        month_key, month_date, ma_sap, ma_nvl,
        ten_nvl, ten_vat_tu, don_vi_tinh, chung_loai,
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
        ghi_chu, create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b5', 'kh.dat.vat.tu', k.id, k.period_id,
        v_period_code, v_period_month, v_owner_company_id,
        k.company_id, rc.company_code,
        v_month_key, v_month_date, k.ma_sap, k.ma_sap,
        k.ten_nvl, k.ten_nvl, k.don_vi_tinh, k.chung_loai,
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
        k.ghi_chu, k.create_uid, k.create_date, k.write_uid, k.write_date
    FROM kh_dat_vat_tu k
    LEFT JOIN res_company rc ON rc.id = k.company_id
    WHERE k.period_id = p_period_id
    ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
        step_code = EXCLUDED.step_code, period_id = EXCLUDED.period_id,
        period_code = EXCLUDED.period_code, period_month = EXCLUDED.period_month,
        owner_company_id = EXCLUDED.owner_company_id,
        company_id = EXCLUDED.company_id, company_code = EXCLUDED.company_code,
        month_date = EXCLUDED.month_date, ma_sap = EXCLUDED.ma_sap,
        ma_nvl = EXCLUDED.ma_nvl, ten_nvl = EXCLUDED.ten_nvl,
        ten_vat_tu = EXCLUDED.ten_vat_tu, don_vi_tinh = EXCLUDED.don_vi_tinh,
        chung_loai = EXCLUDED.chung_loai,
        tong_ton_nvl_sl = EXCLUDED.tong_ton_nvl_sl,
        don_gia_ton_kho = EXCLUDED.don_gia_ton_kho,
        gia_tri_ton_nvl_dau_ky = EXCLUDED.gia_tri_ton_nvl_dau_ky,
        tong_sl_vt_can_dung_t0 = EXCLUDED.tong_sl_vt_can_dung_t0,
        tong_sl_vt_can_dung_t1 = EXCLUDED.tong_sl_vt_can_dung_t1,
        tong_sl_vt_can_dung_t2 = EXCLUDED.tong_sl_vt_can_dung_t2,
        tong_sl_vt_can_dung_t3 = EXCLUDED.tong_sl_vt_can_dung_t3,
        tong_vt_can_dung = EXCLUDED.tong_vt_can_dung,
        tong_sl_vt_can_dung = EXCLUDED.tong_sl_vt_can_dung,
        tong_hang_di_duong_sl_t0 = EXCLUDED.tong_hang_di_duong_sl_t0,
        tong_hang_di_duong_sl_t1 = EXCLUDED.tong_hang_di_duong_sl_t1,
        tong_hang_di_duong_sl_t2 = EXCLUDED.tong_hang_di_duong_sl_t2,
        tong_hang_di_duong_sl_t3 = EXCLUDED.tong_hang_di_duong_sl_t3,
        tong_hang_di_duong = EXCLUDED.tong_hang_di_duong,
        tong_hang_di_duong_sl = EXCLUDED.tong_hang_di_duong_sl,
        sl_du_tru_toi_thieu = EXCLUDED.sl_du_tru_toi_thieu,
        sl_can_mua_theo_moq = EXCLUDED.sl_can_mua_theo_moq,
        sl_dat_mua_de_xuat = EXCLUDED.sl_dat_mua_de_xuat,
        sl_dat_mua_chot = EXCLUDED.sl_dat_mua_chot,
        don_gia_mua = EXCLUDED.don_gia_mua,
        gia_tri_mua_hang = EXCLUDED.gia_tri_mua_hang,
        sl_ton_kho_cuoi_ky = EXCLUDED.sl_ton_kho_cuoi_ky,
        sl_ton_kho = EXCLUDED.sl_ton_kho,
        vt_loi_ton_lau = EXCLUDED.vt_loi_ton_lau,
        so_ngay_vong_quay_ton = EXCLUDED.so_ngay_vong_quay_ton,
        don_gia_ton_kho_cuoi_ky = EXCLUDED.don_gia_ton_kho_cuoi_ky,
        gia_tri_ton_kho_cuoi_ky = EXCLUDED.gia_tri_ton_kho_cuoi_ky,
        gia_tri_ton_kho = EXCLUDED.gia_tri_ton_kho,
        ghi_chu = EXCLUDED.ghi_chu,
        write_uid = EXCLUDED.write_uid, write_date = EXCLUDED.write_date;

    PERFORM set_config('app.dlthvt_bulk', '', true);
END;
$$;

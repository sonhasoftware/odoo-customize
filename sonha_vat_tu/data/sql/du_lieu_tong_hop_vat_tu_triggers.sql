-- =============================================================================
-- Trigger đồng bộ bảng phẳng du_lieu_tong_hop_vat_tu từ 5 bảng nguồn B1–B5.
-- =============================================================================

-- Composite index cho query báo cáo
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

CREATE OR REPLACE FUNCTION dlthvt_fill_meta() RETURNS TRIGGER AS $$
BEGIN
    IF COALESCE(current_setting('app.dlthvt_bulk', true), '') = '1' THEN
        RETURN NEW;
    END IF;

    SELECT p.code, p.period_month, p.company_id
      INTO NEW.period_code, NEW.period_month, NEW.owner_company_id
      FROM ke_hoach_vat_tu p
     WHERE p.id = NEW.period_id;

    -- B3/B4 trigger gán period_company_id = don_vi_kd_id; không ghi đè bằng NULL.
    IF NEW.period_company_id IS NULL AND NEW.step_code IN ('kd', 'sx') THEN
        NEW.period_company_id := NEW.company_id;
    END IF;

    IF NEW.period_company_id IS NOT NULL THEN
        SELECT c.company_code
          INTO NEW.period_company_code
          FROM res_company c
         WHERE c.id = NEW.period_company_id;
    ELSE
        NEW.period_company_code := NULL;
    END IF;

    SELECT c.company_code
      INTO NEW.company_code
      FROM res_company c
     WHERE c.id = NEW.company_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dlthvt_fill_meta ON du_lieu_tong_hop_vat_tu;
CREATE TRIGGER trg_dlthvt_fill_meta
BEFORE INSERT OR UPDATE ON du_lieu_tong_hop_vat_tu
FOR EACH ROW EXECUTE PROCEDURE dlthvt_fill_meta();

-- =============================================================================
-- Kỳ: ke_hoach_vat_tu → cập nhật meta (đơn vị lập kế hoạch) trên bảng phẳng
-- =============================================================================
CREATE OR REPLACE FUNCTION dlthvt_sync_period_meta() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    UPDATE du_lieu_tong_hop_vat_tu
       SET owner_company_id = NEW.company_id,
           period_code = NEW.code,
           period_month = NEW.period_month,
           write_uid = COALESCE(NEW.write_uid, 1),
           write_date = NOW()
     WHERE period_id = NEW.id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dlthvt_period_meta ON ke_hoach_vat_tu;
CREATE TRIGGER trg_dlthvt_period_meta
AFTER INSERT OR UPDATE OF company_id, code, period_month ON ke_hoach_vat_tu
FOR EACH ROW EXECUTE PROCEDURE dlthvt_sync_period_meta();

-- =============================================================================
-- B1: ke_hoach_vat_tu_line → du_lieu_tong_hop_vat_tu
-- =============================================================================
CREATE OR REPLACE FUNCTION dlthvt_sync_b1() RETURNS TRIGGER AS $$
DECLARE
    v_period_month TEXT;
    v_month_key TEXT;
    v_month_date DATE;
    v_qty NUMERIC;
    v_qty_kd NUMERIC;
    v_qty_sx NUMERIC;
    v_qty_cl NUMERIC;
BEGIN
    IF COALESCE(current_setting('app.dlthvt_skip', true), '') = '1' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'ke.hoach.vat.tu.line' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;

    SELECT period_month INTO v_period_month
    FROM ke_hoach_vat_tu
    WHERE id = NEW.period_id;

    FOR i IN 0..3 LOOP
        v_month_date := (TO_DATE(v_period_month, 'MM/YYYY') + (i || ' month')::INTERVAL)::DATE;
        v_month_key  := TO_CHAR(v_month_date, 'MM/YYYY');

        v_qty := CASE i WHEN 0 THEN NEW.qty_t0 WHEN 1 THEN NEW.qty_t1 WHEN 2 THEN NEW.qty_t2 WHEN 3 THEN NEW.qty_t3 END;
        v_qty_kd := CASE i WHEN 0 THEN NEW.qty_kd_t0 WHEN 1 THEN NEW.qty_kd_t1 WHEN 2 THEN NEW.qty_kd_t2 WHEN 3 THEN NEW.qty_kd_t3 END;
        v_qty_sx := CASE i WHEN 0 THEN NEW.qty_sx_t0 WHEN 1 THEN NEW.qty_sx_t1 WHEN 2 THEN NEW.qty_sx_t2 WHEN 3 THEN NEW.qty_sx_t3 END;
        v_qty_cl := CASE i WHEN 0 THEN NEW.qty_cl_t0 WHEN 1 THEN NEW.qty_cl_t1 WHEN 2 THEN NEW.qty_cl_t2 WHEN 3 THEN NEW.qty_cl_t3 END;

        INSERT INTO du_lieu_tong_hop_vat_tu (
            step_code, source_model, source_res_id, period_id, company_id,
            period_company_id, month_key, month_date, ma_sap, ma_vat_tu,
            nganh_hang, ten_hang, ma_hang,
            qty, note, qty_kinh_doanh, qty_san_xuat, qty_chenh_lech,
            create_uid, create_date, write_uid, write_date
        ) VALUES (
            'b1', 'ke.hoach.vat.tu.line', NEW.id, NEW.period_id, NEW.company_id,
            NEW.company_id, v_month_key, v_month_date, NEW.ma_sap, NULL,
            NEW.nganh_hang, NEW.ten_hang, NEW.ma_hang,
            v_qty, NEW.note, v_qty_kd, v_qty_sx, v_qty_cl,
            NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
        )
        ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
            step_code = EXCLUDED.step_code,
            period_id = EXCLUDED.period_id,
            company_id = EXCLUDED.company_id,
            period_company_id = EXCLUDED.period_company_id,
            month_date = EXCLUDED.month_date,
            ma_sap = EXCLUDED.ma_sap,
            nganh_hang = EXCLUDED.nganh_hang,
            ten_hang = EXCLUDED.ten_hang,
            ma_hang = EXCLUDED.ma_hang,
            qty = EXCLUDED.qty,
            note = EXCLUDED.note,
            qty_kinh_doanh = EXCLUDED.qty_kinh_doanh,
            qty_san_xuat = EXCLUDED.qty_san_xuat,
            qty_chenh_lech = EXCLUDED.qty_chenh_lech,
            write_uid = EXCLUDED.write_uid,
            write_date = EXCLUDED.write_date;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dlthvt_b1 ON ke_hoach_vat_tu_line;
CREATE TRIGGER trg_dlthvt_b1
AFTER INSERT OR UPDATE OR DELETE ON ke_hoach_vat_tu_line
FOR EACH ROW EXECUTE PROCEDURE dlthvt_sync_b1();

-- =============================================================================
-- B2: dinh_muc → du_lieu_tong_hop_vat_tu
-- =============================================================================
CREATE OR REPLACE FUNCTION dlthvt_sync_b2() RETURNS TRIGGER AS $$
DECLARE
    v_period_month TEXT;
    v_month_key TEXT;
    v_month_date DATE;
    v_qty NUMERIC;
    v_qty_kinh_doanh NUMERIC;
    v_qty_san_xuat NUMERIC;
    v_qty_chenh_lech NUMERIC;
BEGIN
    IF COALESCE(current_setting('app.dlthvt_skip', true), '') = '1' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'dinh.muc' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;

    SELECT period_month INTO v_period_month
    FROM ke_hoach_vat_tu
    WHERE id = NEW.period_id;

    FOR i IN 0..3 LOOP
        v_month_date := (TO_DATE(v_period_month, 'MM/YYYY') + (i || ' month')::INTERVAL)::DATE;
        v_month_key  := TO_CHAR(v_month_date, 'MM/YYYY');
        
        v_qty := CASE i
            WHEN 0 THEN NEW.qty_t0
            WHEN 1 THEN NEW.qty_t1
            WHEN 2 THEN NEW.qty_t2
            WHEN 3 THEN NEW.qty_t3
        END;
        v_qty_kinh_doanh := CASE i
            WHEN 0 THEN NEW.qty_kinh_doanh_t0
            WHEN 1 THEN NEW.qty_kinh_doanh_t1
            WHEN 2 THEN NEW.qty_kinh_doanh_t2
            WHEN 3 THEN NEW.qty_kinh_doanh_t3
        END;
        v_qty_san_xuat := CASE i
            WHEN 0 THEN NEW.qty_san_xuat_t0
            WHEN 1 THEN NEW.qty_san_xuat_t1
            WHEN 2 THEN NEW.qty_san_xuat_t2
            WHEN 3 THEN NEW.qty_san_xuat_t3
        END;
        v_qty_chenh_lech := CASE i
            WHEN 0 THEN NEW.qty_chenh_lech_t0
            WHEN 1 THEN NEW.qty_chenh_lech_t1
            WHEN 2 THEN NEW.qty_chenh_lech_t2
            WHEN 3 THEN NEW.qty_chenh_lech_t3
        END;

        INSERT INTO du_lieu_tong_hop_vat_tu (
            step_code, source_model, source_res_id, period_id, company_id, month_key,
            month_date, ma_sap, ma_vat_tu, nganh_hang, ten_hang, ma_hang,
            qty, note, ma_tp, ten_tp, ten_sap, ma_nvl, bom_sale_id,
            ten_nvl, ten_vat_tu, sl_dinh_muc,
            qty_kinh_doanh, qty_san_xuat, qty_chenh_lech, ma_effect,
            create_uid, create_date, write_uid, write_date
        ) VALUES (
            'b2', 'dinh.muc', NEW.id, NEW.period_id,
            NEW.company_id, v_month_key, v_month_date, NEW.ma_sap,
            NEW.ma_nvl, NULL, NULL, NULL,
            v_qty, NULL, NEW.ma_tp, NEW.ten_tp,
            NEW.ten_sap, NEW.ma_nvl, NEW.bom_sale_id, NEW.ten_nvl, NEW.ten_nvl,
            NEW.sl_dinh_muc,
            v_qty_kinh_doanh, v_qty_san_xuat, v_qty_chenh_lech, NULL,
            NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
        )
        ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
            step_code = EXCLUDED.step_code,
            period_id = EXCLUDED.period_id,
            company_id = EXCLUDED.company_id,
            month_date = EXCLUDED.month_date,
            ma_sap = EXCLUDED.ma_sap,
            ma_vat_tu = EXCLUDED.ma_vat_tu,
            qty = EXCLUDED.qty,
            ma_tp = EXCLUDED.ma_tp,
            ten_tp = EXCLUDED.ten_tp,
            ten_sap = EXCLUDED.ten_sap,
            ma_nvl = EXCLUDED.ma_nvl,
            bom_sale_id = EXCLUDED.bom_sale_id,
            ten_nvl = EXCLUDED.ten_nvl,
            ten_vat_tu = EXCLUDED.ten_vat_tu,
            sl_dinh_muc = EXCLUDED.sl_dinh_muc,
            qty_kinh_doanh = EXCLUDED.qty_kinh_doanh,
            qty_san_xuat = EXCLUDED.qty_san_xuat,
            qty_chenh_lech = EXCLUDED.qty_chenh_lech,
            write_uid = EXCLUDED.write_uid,
            write_date = EXCLUDED.write_date;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dlthvt_b2 ON dinh_muc;
CREATE TRIGGER trg_dlthvt_b2
AFTER INSERT OR UPDATE OR DELETE ON dinh_muc
FOR EACH ROW EXECUTE PROCEDURE dlthvt_sync_b2();

-- =============================================================================
-- B3: tinh_toan_vat_tu → du_lieu_tong_hop_vat_tu
-- =============================================================================
CREATE OR REPLACE FUNCTION dlthvt_sync_b3() RETURNS TRIGGER AS $$
DECLARE
    v_period_month TEXT;
    v_month_key TEXT;
    v_month_date DATE;
    v_qty NUMERIC;
BEGIN
    IF COALESCE(current_setting('app.dlthvt_skip', true), '') = '1' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'tinh.toan.vat.tu' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;

    SELECT period_month INTO v_period_month
    FROM ke_hoach_vat_tu
    WHERE id = NEW.period_id;

    FOR i IN 0..3 LOOP
        v_month_date := (TO_DATE(v_period_month, 'MM/YYYY') + (i || ' month')::INTERVAL)::DATE;
        v_month_key  := TO_CHAR(v_month_date, 'MM/YYYY');
        
        v_qty := CASE i
            WHEN 0 THEN NEW.qty_t0
            WHEN 1 THEN NEW.qty_t1
            WHEN 2 THEN NEW.qty_t2
            WHEN 3 THEN NEW.qty_t3
        END;

        INSERT INTO du_lieu_tong_hop_vat_tu (
            step_code, source_model, source_res_id, period_id, company_id,
            period_company_id, month_key,
            month_date, ma_sap, ma_vat_tu,
            qty, ma_nvl, ten_nvl, ten_vat_tu,
            don_vi_tinh, do_day, kho_1, kho_2, trong_luong_kg_tam,
            create_uid, create_date, write_uid, write_date
        ) VALUES (
            'b3', 'tinh.toan.vat.tu', NEW.id, NEW.period_id,
            NEW.company_id, NEW.don_vi_kd_id, v_month_key, v_month_date,
            NEW.ma_vat_tu, NEW.ma_vat_tu,
            v_qty, NEW.ma_vat_tu, NEW.ten_vat_tu, NEW.ten_vat_tu,
            NEW.don_vi_tinh, NEW.do_day, NEW.kho_1, NEW.kho_2,
            NEW.trong_luong_kg_tam,
            NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
        )
        ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
            step_code = EXCLUDED.step_code,
            period_id = EXCLUDED.period_id,
            company_id = EXCLUDED.company_id,
            period_company_id = EXCLUDED.period_company_id,
            month_date = EXCLUDED.month_date,
            ma_sap = EXCLUDED.ma_sap,
            ma_vat_tu = EXCLUDED.ma_vat_tu,
            qty = EXCLUDED.qty,
            ma_nvl = EXCLUDED.ma_nvl,
            ten_nvl = EXCLUDED.ten_nvl,
            ten_vat_tu = EXCLUDED.ten_vat_tu,
            don_vi_tinh = EXCLUDED.don_vi_tinh,
            do_day = EXCLUDED.do_day,
            kho_1 = EXCLUDED.kho_1,
            kho_2 = EXCLUDED.kho_2,
            trong_luong_kg_tam = EXCLUDED.trong_luong_kg_tam,
            write_uid = EXCLUDED.write_uid,
            write_date = EXCLUDED.write_date;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dlthvt_b3 ON tinh_toan_vat_tu;
CREATE TRIGGER trg_dlthvt_b3
AFTER INSERT OR UPDATE OR DELETE ON tinh_toan_vat_tu
FOR EACH ROW EXECUTE PROCEDURE dlthvt_sync_b3();

-- =============================================================================
-- B4: tong_hop_vat_tu → du_lieu_tong_hop_vat_tu
-- =============================================================================
CREATE OR REPLACE FUNCTION dlthvt_sync_b4() RETURNS TRIGGER AS $$
DECLARE
    v_period_month TEXT;
    v_month_key TEXT;
    v_month_date DATE;
    v_ve_du_kien_don_vi NUMERIC;
    v_ve_du_kien NUMERIC;
    v_vt_can_dung NUMERIC;
    v_ton_cuoi NUMERIC;
BEGIN
    IF COALESCE(current_setting('app.dlthvt_skip', true), '') = '1' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'tong.hop.vat.tu' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;

    SELECT period_month INTO v_period_month
    FROM ke_hoach_vat_tu
    WHERE id = NEW.period_id;

    FOR i IN 0..3 LOOP
        v_month_date := (TO_DATE(v_period_month, 'MM/YYYY') + (i || ' month')::INTERVAL)::DATE;
        v_month_key  := TO_CHAR(v_month_date, 'MM/YYYY');
        
        v_ve_du_kien_don_vi := CASE i WHEN 0 THEN NEW.ve_du_kien_don_vi_t0 WHEN 1 THEN NEW.ve_du_kien_don_vi_t1 WHEN 2 THEN NEW.ve_du_kien_don_vi_t2 WHEN 3 THEN NEW.ve_du_kien_don_vi_t3 END;
        v_ve_du_kien := CASE i WHEN 0 THEN NEW.ve_du_kien_t0 WHEN 1 THEN NEW.ve_du_kien_t1 WHEN 2 THEN NEW.ve_du_kien_t2 WHEN 3 THEN NEW.ve_du_kien_t3 END;
        v_vt_can_dung := CASE i WHEN 0 THEN NEW.vt_can_dung_t0 WHEN 1 THEN NEW.vt_can_dung_t1 WHEN 2 THEN NEW.vt_can_dung_t2 WHEN 3 THEN NEW.vt_can_dung_t3 END;
        v_ton_cuoi := CASE i WHEN 0 THEN NEW.ton_cuoi_t0 WHEN 1 THEN NEW.ton_cuoi_t1 WHEN 2 THEN NEW.ton_cuoi_t2 WHEN 3 THEN NEW.ton_cuoi_t3 END;

        INSERT INTO du_lieu_tong_hop_vat_tu (
            step_code, source_model, source_res_id, period_id, company_id, period_company_id, month_key,
            month_date, ma_sap, ma_nvl,
            ten_nvl, ten_vat_tu, don_vi_tinh, ma_dat_hang, chung_loai,
            ton_dau, ve_du_kien_don_vi, ve_du_kien, vt_can_dung, ton_cuoi, so_luong_du_phong, so_luong_thieu, so_luong_can_mua,
            ghi_chu,
            create_uid, create_date, write_uid, write_date
        ) VALUES (
            'b4', 'tong.hop.vat.tu', NEW.id, NEW.period_id,
            NEW.company_id, NEW.don_vi_kd_id, v_month_key, v_month_date, NEW.ma_sap, NEW.ma_sap,
            NEW.ten_nvl, NEW.ten_nvl, NEW.don_vi_tinh, NEW.ma_dat_hang, NEW.chung_loai,
            NEW.ton_dau, v_ve_du_kien_don_vi, v_ve_du_kien, v_vt_can_dung, v_ton_cuoi,
            CASE WHEN i = 3 THEN NEW.so_luong_du_phong ELSE 0 END,
            CASE WHEN i = 3 THEN NEW.so_luong_thieu ELSE 0 END,
            CASE WHEN i = 3 THEN NEW.so_luong_can_mua ELSE 0 END,
            NEW.ghi_chu,
            NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
        )
        ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
            step_code = EXCLUDED.step_code,
            period_id = EXCLUDED.period_id,
            company_id = EXCLUDED.company_id,
            period_company_id = EXCLUDED.period_company_id,
            month_date = EXCLUDED.month_date,
            ma_sap = EXCLUDED.ma_sap,
            ma_nvl = EXCLUDED.ma_nvl,
            ten_nvl = EXCLUDED.ten_nvl,
            ten_vat_tu = EXCLUDED.ten_vat_tu,
            don_vi_tinh = EXCLUDED.don_vi_tinh,
            ma_dat_hang = EXCLUDED.ma_dat_hang,
            chung_loai = EXCLUDED.chung_loai,
            ton_dau = EXCLUDED.ton_dau,
            ve_du_kien_don_vi = EXCLUDED.ve_du_kien_don_vi,
            ve_du_kien = EXCLUDED.ve_du_kien,
            vt_can_dung = EXCLUDED.vt_can_dung,
            ton_cuoi = EXCLUDED.ton_cuoi,
            so_luong_du_phong = EXCLUDED.so_luong_du_phong,
            so_luong_thieu = EXCLUDED.so_luong_thieu,
            so_luong_can_mua = EXCLUDED.so_luong_can_mua,
            ghi_chu = EXCLUDED.ghi_chu,
            write_uid = EXCLUDED.write_uid,
            write_date = EXCLUDED.write_date;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dlthvt_b4 ON tong_hop_vat_tu;
CREATE TRIGGER trg_dlthvt_b4
AFTER INSERT OR UPDATE OR DELETE ON tong_hop_vat_tu
FOR EACH ROW EXECUTE PROCEDURE dlthvt_sync_b4();


-- =============================================================================
-- B5: kh_dat_vat_tu → du_lieu_tong_hop_vat_tu
-- =============================================================================
CREATE OR REPLACE FUNCTION dlthvt_sync_b5() RETURNS TRIGGER AS $$
DECLARE
    v_period_month TEXT;
    v_month_key TEXT;
    v_month_date DATE;
BEGIN
    IF COALESCE(current_setting('app.dlthvt_skip', true), '') = '1' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'kh.dat.vat.tu' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;

    SELECT period_month INTO v_period_month
    FROM ke_hoach_vat_tu
    WHERE id = NEW.period_id;

    -- B5 now has single-value fields (not per-month), so we insert one record
    v_month_date := TO_DATE(v_period_month, 'MM/YYYY');
    v_month_key  := TO_CHAR(v_month_date, 'MM/YYYY');

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id, period_id, company_id, month_key,
        month_date, ma_sap, ma_nvl,
        ten_nvl, ten_vat_tu, don_vi_tinh, chung_loai,
        tong_ton_nvl_sl, don_gia_ton_kho, gia_tri_ton_nvl_dau_ky,
        tong_sl_vt_can_dung_t0, tong_sl_vt_can_dung_t1, tong_sl_vt_can_dung_t2, tong_sl_vt_can_dung_t3,
        tong_vt_can_dung, tong_sl_vt_can_dung,
        tong_hang_di_duong_sl_t0, tong_hang_di_duong_sl_t1, tong_hang_di_duong_sl_t2, tong_hang_di_duong_sl_t3,
        tong_hang_di_duong, tong_hang_di_duong_sl,
        sl_du_tru_toi_thieu, sl_dat_mua_de_xuat, sl_dat_mua_chot, sl_can_mua_theo_moq,
        don_gia_mua, gia_tri_mua_hang,
        sl_ton_kho_cuoi_ky, sl_ton_kho, vt_loi_ton_lau,
        so_ngay_vong_quay_ton, don_gia_ton_kho_cuoi_ky, gia_tri_ton_kho_cuoi_ky, gia_tri_ton_kho,
        ghi_chu,
        create_uid, create_date, write_uid, write_date
    ) VALUES (
        'b5', 'kh.dat.vat.tu', NEW.id, NEW.period_id,
        NEW.company_id, v_month_key, v_month_date, NEW.ma_sap, NEW.ma_sap,
        NEW.ten_nvl, NEW.ten_nvl, NEW.don_vi_tinh, NEW.chung_loai,
        NEW.tong_ton_nvl_sl, NEW.don_gia_ton_kho,
        COALESCE(NEW.tong_ton_nvl_sl, 0) * COALESCE(NEW.don_gia_ton_kho, 0),
        NEW.tong_sl_vt_can_dung_t0, NEW.tong_sl_vt_can_dung_t1, NEW.tong_sl_vt_can_dung_t2, NEW.tong_sl_vt_can_dung_t3,
        NEW.tong_vt_can_dung, NEW.tong_vt_can_dung,
        NEW.tong_hang_di_duong_sl_t0, NEW.tong_hang_di_duong_sl_t1, NEW.tong_hang_di_duong_sl_t2, NEW.tong_hang_di_duong_sl_t3,
        NEW.tong_hang_di_duong, NEW.tong_hang_di_duong,
        NEW.sl_du_tru_toi_thieu, NEW.sl_dat_mua_de_xuat, NEW.sl_dat_mua_chot, NEW.sl_can_mua_theo_moq,
        NEW.don_gia_mua, NEW.gia_tri_mua_hang,
        NEW.sl_ton_kho_cuoi_ky, NEW.sl_ton_kho_cuoi_ky, NEW.vt_loi_ton_lau,
        NEW.so_ngay_vong_quay_ton, NEW.don_gia_ton_kho_cuoi_ky, NEW.gia_tri_ton_kho_cuoi_ky, NEW.gia_tri_ton_kho_cuoi_ky,
        NEW.ghi_chu,
        NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
    )
    ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
        step_code = EXCLUDED.step_code,
        period_id = EXCLUDED.period_id,
        company_id = EXCLUDED.company_id,
        month_date = EXCLUDED.month_date,
        ma_sap = EXCLUDED.ma_sap,
        ma_nvl = EXCLUDED.ma_nvl,
        ten_nvl = EXCLUDED.ten_nvl,
        ten_vat_tu = EXCLUDED.ten_vat_tu,
        don_vi_tinh = EXCLUDED.don_vi_tinh,
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
        sl_dat_mua_de_xuat = EXCLUDED.sl_dat_mua_de_xuat,
        sl_dat_mua_chot = EXCLUDED.sl_dat_mua_chot,
        sl_can_mua_theo_moq = EXCLUDED.sl_can_mua_theo_moq,
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
        write_uid = EXCLUDED.write_uid,
        write_date = EXCLUDED.write_date;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dlthvt_b5 ON kh_dat_vat_tu;
CREATE TRIGGER trg_dlthvt_b5
AFTER INSERT OR UPDATE OR DELETE ON kh_dat_vat_tu
FOR EACH ROW EXECUTE PROCEDURE dlthvt_sync_b5();

-- =============================================================================
-- KD: ke_hoach_kinh_doanh -> du_lieu_tong_hop_vat_tu
-- =============================================================================
CREATE OR REPLACE FUNCTION dlthvt_sync_kd() RETURNS TRIGGER AS $$
DECLARE
    v_period_month TEXT;
    v_month_key TEXT;
    v_month_date DATE;
    v_qty NUMERIC;
    v_nganh_hang TEXT;
BEGIN
    IF COALESCE(current_setting('app.dlthvt_skip', true), '') = '1' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'ke.hoach.kinh.doanh' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;

    SELECT period_month INTO v_period_month
    FROM ke_hoach_vat_tu
    WHERE id = NEW.period_id;

    SELECT nh.ten INTO v_nganh_hang
    FROM mdm_nganh_hang nh
    WHERE nh.id = NEW.nganh_hang;

    FOR i IN 0..3 LOOP
        v_month_date := (TO_DATE(v_period_month, 'MM/YYYY') + (i || ' month')::INTERVAL)::DATE;
        v_month_key  := TO_CHAR(v_month_date, 'MM/YYYY');
        v_qty := CASE i WHEN 0 THEN NEW.qty_t0 WHEN 1 THEN NEW.qty_t1 WHEN 2 THEN NEW.qty_t2 WHEN 3 THEN NEW.qty_t3 END;

        INSERT INTO du_lieu_tong_hop_vat_tu (
            step_code, source_model, source_res_id, period_id, company_id,
            period_company_id, month_key, month_date, ma_sap, ma_vat_tu,
            nganh_hang, ten_hang, ma_hang,
            qty, note,
            create_uid, create_date, write_uid, write_date
        ) VALUES (
            'kd', 'ke.hoach.kinh.doanh', NEW.id, NEW.period_id, NEW.company_id,
            NEW.company_id, v_month_key, v_month_date, NEW.ma_sap, NULL,
            v_nganh_hang, NEW.ten_hang, NEW.ma_hang,
            v_qty, NEW.note,
            NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
        )
        ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
            step_code = EXCLUDED.step_code,
            period_id = EXCLUDED.period_id,
            company_id = EXCLUDED.company_id,
            period_company_id = EXCLUDED.period_company_id,
            month_date = EXCLUDED.month_date,
            ma_sap = EXCLUDED.ma_sap,
            nganh_hang = EXCLUDED.nganh_hang,
            ten_hang = EXCLUDED.ten_hang,
            ma_hang = EXCLUDED.ma_hang,
            qty = EXCLUDED.qty,
            note = EXCLUDED.note,
            write_uid = EXCLUDED.write_uid,
            write_date = EXCLUDED.write_date;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dlthvt_kd ON ke_hoach_kinh_doanh;
CREATE TRIGGER trg_dlthvt_kd
AFTER INSERT OR UPDATE OR DELETE ON ke_hoach_kinh_doanh
FOR EACH ROW EXECUTE PROCEDURE dlthvt_sync_kd();

-- =============================================================================
-- SX: ke_hoach_san_xuat -> du_lieu_tong_hop_vat_tu
-- =============================================================================
CREATE OR REPLACE FUNCTION dlthvt_sync_sx() RETURNS TRIGGER AS $$
DECLARE
    v_period_month TEXT;
    v_month_key TEXT;
    v_month_date DATE;
    v_qty NUMERIC;
    v_nganh_hang TEXT;
BEGIN
    IF COALESCE(current_setting('app.dlthvt_skip', true), '') = '1' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'ke.hoach.san.xuat' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;

    SELECT period_month INTO v_period_month
    FROM ke_hoach_vat_tu
    WHERE id = NEW.period_id;

    SELECT nh.ten INTO v_nganh_hang
    FROM mdm_nganh_hang nh
    WHERE nh.id = NEW.nganh_hang;

    FOR i IN 0..3 LOOP
        v_month_date := (TO_DATE(v_period_month, 'MM/YYYY') + (i || ' month')::INTERVAL)::DATE;
        v_month_key  := TO_CHAR(v_month_date, 'MM/YYYY');
        v_qty := CASE i WHEN 0 THEN NEW.qty_t0 WHEN 1 THEN NEW.qty_t1 WHEN 2 THEN NEW.qty_t2 WHEN 3 THEN NEW.qty_t3 END;

        INSERT INTO du_lieu_tong_hop_vat_tu (
            step_code, source_model, source_res_id, period_id, company_id,
            period_company_id, month_key, month_date, ma_sap, ma_vat_tu,
            nganh_hang, ten_hang, ma_hang,
            qty, note,
            create_uid, create_date, write_uid, write_date
        ) VALUES (
            'sx', 'ke.hoach.san.xuat', NEW.id, NEW.period_id, NEW.company_id,
            NEW.company_id, v_month_key, v_month_date, NEW.ma_sap, NULL,
            v_nganh_hang, NEW.ten_hang, NEW.ma_hang,
            v_qty, NEW.note,
            NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
        )
        ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
            step_code = EXCLUDED.step_code,
            period_id = EXCLUDED.period_id,
            company_id = EXCLUDED.company_id,
            period_company_id = EXCLUDED.period_company_id,
            month_date = EXCLUDED.month_date,
            ma_sap = EXCLUDED.ma_sap,
            nganh_hang = EXCLUDED.nganh_hang,
            ten_hang = EXCLUDED.ten_hang,
            ma_hang = EXCLUDED.ma_hang,
            qty = EXCLUDED.qty,
            note = EXCLUDED.note,
            write_uid = EXCLUDED.write_uid,
            write_date = EXCLUDED.write_date;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dlthvt_sx ON ke_hoach_san_xuat;
CREATE TRIGGER trg_dlthvt_sx
AFTER INSERT OR UPDATE OR DELETE ON ke_hoach_san_xuat
FOR EACH ROW EXECUTE PROCEDURE dlthvt_sync_sx();

-- =============================================================================
-- SYNC: md_sap_bom → bom (ORM table)
-- =============================================================================

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

CREATE OR REPLACE FUNCTION sync_md_sap_bom_to_bom() RETURNS TRIGGER AS $$
DECLARE
    v_sl_dm   NUMERIC;
    v_sl_spdm NUMERIC;
BEGIN
    IF NEW.ma_tp IS NULL OR TRIM(NEW.ma_tp) = '' THEN RETURN NEW; END IF;
    IF NEW.ma_nvl IS NULL OR TRIM(NEW.ma_nvl) = '' THEN RETURN NEW; END IF;

    v_sl_dm   := safe_sap_numeric(NEW.sl_dm);
    v_sl_spdm := NULLIF(safe_sap_numeric(NEW.sl_spdm), 0);
    IF v_sl_spdm IS NULL THEN v_sl_spdm := 1.0; END IF;

    INSERT INTO bom (
        ma_tp, ten_tp, ma_nvl, ten_nvl, sl_dinh_muc, sl_spdm,
        do_day, kho_1, kho_2,
        create_uid, create_date, write_uid, write_date
    ) VALUES (
        TRIM(NEW.ma_tp),
        COALESCE(NULLIF(TRIM(NEW.ten_tp),  ''), TRIM(NEW.ma_tp)),
        TRIM(NEW.ma_nvl),
        COALESCE(NULLIF(TRIM(NEW.ten_nvl), ''), TRIM(NEW.ma_nvl)),
        COALESCE(v_sl_dm, 0),
        v_sl_spdm,
        0, 0, 0,
        1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC'
    )
    ON CONFLICT (ma_tp, ma_nvl) DO UPDATE SET
        ten_tp      = COALESCE(NULLIF(EXCLUDED.ten_tp,  ''), bom.ten_tp),
        ten_nvl     = COALESCE(NULLIF(EXCLUDED.ten_nvl, ''), bom.ten_nvl),
        sl_dinh_muc = EXCLUDED.sl_dinh_muc,
        sl_spdm     = COALESCE(EXCLUDED.sl_spdm, bom.sl_spdm, 1.0),
        write_date  = NOW() AT TIME ZONE 'UTC';

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'md_sap_bom'
    ) THEN
        DROP TRIGGER IF EXISTS trg_sync_sap_bom ON md_sap_bom;
        CREATE TRIGGER trg_sync_sap_bom
        AFTER INSERT OR UPDATE ON md_sap_bom
        FOR EACH ROW EXECUTE PROCEDURE sync_md_sap_bom_to_bom();

        -- Backfill: đồng bộ toàn bộ dữ liệu md_sap_bom hiện có
        INSERT INTO bom (ma_tp, ten_tp, ma_nvl, ten_nvl,
                         sl_dinh_muc, sl_spdm, do_day, kho_1, kho_2,
                         create_uid, create_date, write_uid, write_date)
        SELECT
            d.ma_tp, d.ten_tp, d.ma_nvl, d.ten_nvl,
            d.sl_dm_num, d.sl_spdm_num,
            0, 0, 0,
            1, NOW() AT TIME ZONE 'UTC',
            1, NOW() AT TIME ZONE 'UTC'
        FROM (
            SELECT DISTINCT ON (TRIM(s.ma_tp), TRIM(s.ma_nvl))
                TRIM(s.ma_tp)                                                    AS ma_tp,
                COALESCE(NULLIF(TRIM(s.ten_tp),  ''), TRIM(s.ma_tp))            AS ten_tp,
                TRIM(s.ma_nvl)                                                   AS ma_nvl,
                COALESCE(NULLIF(TRIM(s.ten_nvl), ''), TRIM(s.ma_nvl))           AS ten_nvl,
                safe_sap_numeric(s.sl_dm)                                        AS sl_dm_num,
                NULLIF(safe_sap_numeric(s.sl_spdm), 0)                          AS sl_spdm_num
            FROM md_sap_bom s
            WHERE s.ma_tp  IS NOT NULL AND TRIM(s.ma_tp)  != ''
              AND s.ma_nvl IS NOT NULL AND TRIM(s.ma_nvl) != ''
            ORDER BY TRIM(s.ma_tp), TRIM(s.ma_nvl), s.id DESC
        ) d
        ON CONFLICT (ma_tp, ma_nvl) DO UPDATE SET
            ten_tp      = COALESCE(NULLIF(EXCLUDED.ten_tp,  ''), bom.ten_tp),
            ten_nvl     = COALESCE(NULLIF(EXCLUDED.ten_nvl, ''), bom.ten_nvl),
            sl_dinh_muc = EXCLUDED.sl_dinh_muc,
            sl_spdm     = COALESCE(EXCLUDED.sl_spdm, bom.sl_spdm, 1.0),
            write_date  = NOW() AT TIME ZONE 'UTC';
    END IF;
END $$;

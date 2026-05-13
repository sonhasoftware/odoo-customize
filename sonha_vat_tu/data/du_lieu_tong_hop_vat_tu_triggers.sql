-- =============================================================================
-- Trigger đồng bộ bảng phẳng du_lieu_tong_hop_vat_tu từ 5 bảng nguồn B1–B5.
-- + Trigger sync md_sap_bom → bom (ORM).
-- File này được load bởi du_lieu_tong_hop_vat_tu.py > init() và action_rebuild.
-- Chạy idempotent: CREATE OR REPLACE + DROP TRIGGER IF EXISTS.
-- =============================================================================

-- Composite index cho query báo cáo
CREATE INDEX IF NOT EXISTS idx_dlthvt_report
    ON du_lieu_tong_hop_vat_tu (step_code, period_id, month_key);

-- =============================================================================
-- B1: ke_hoach_thanh_pham → du_lieu_tong_hop_vat_tu
-- =============================================================================
CREATE OR REPLACE FUNCTION dlthvt_sync_b1() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'ke.hoach.thanh.pham' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;
    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, company_id, month_key, ma_sap,
        nganh_hang_id, dong_hang_id, ma_hang_id, qty, note,
        ma_tp, ten_sap, ma_nvl, ma_effect, don_vi_tinh,
        do_day, kho_1, kho_2, trong_luong_kg_tam, sl_dinh_muc,
        ma_dat_hang, chung_loai, ton_dau, ve_du_kien, vt_can_dung, ton_cuoi,
        so_luong_du_phong, so_luong_thieu, so_luong_can_mua, ghi_chu,
        tong_ton_nvl_sl, tong_hang_di_duong_sl, tong_sl_vt_can_dung,
        sl_du_tru_toi_thieu, sl_can_mua_theo_moq, sl_dat_mua_de_xuat,
        sl_dat_mua_chot, sl_ton_kho, so_ngay_vong_quay_ton, don_gia_ton_kho, gia_tri_ton_kho,
        create_uid, create_date, write_uid, write_date
    ) VALUES (
        'b1', 'ke.hoach.thanh.pham', NEW.id,
        NEW.period_id, NEW.company_id, NEW.month_key, NEW.ma_sap,
        NEW.nganh_hang_id, NEW.dong_hang_id, NEW.ma_hang_id, NEW.qty, NEW.note,
        NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
    )
    ON CONFLICT (source_model, source_res_id) DO UPDATE SET
        step_code = EXCLUDED.step_code,
        period_id = EXCLUDED.period_id,
        company_id = EXCLUDED.company_id,
        month_key = EXCLUDED.month_key,
        ma_sap = EXCLUDED.ma_sap,
        nganh_hang_id = EXCLUDED.nganh_hang_id,
        dong_hang_id = EXCLUDED.dong_hang_id,
        ma_hang_id = EXCLUDED.ma_hang_id,
        qty = EXCLUDED.qty,
        note = EXCLUDED.note,
        write_uid = EXCLUDED.write_uid,
        write_date = EXCLUDED.write_date;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dlthvt_b1 ON ke_hoach_thanh_pham;
CREATE TRIGGER trg_dlthvt_b1
AFTER INSERT OR UPDATE OR DELETE ON ke_hoach_thanh_pham
FOR EACH ROW EXECUTE PROCEDURE dlthvt_sync_b1();

-- =============================================================================
-- B2: dinh_muc → du_lieu_tong_hop_vat_tu
-- =============================================================================
CREATE OR REPLACE FUNCTION dlthvt_sync_b2() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'dinh.muc' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;
    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, company_id, month_key, ma_sap,
        nganh_hang_id, dong_hang_id, ma_hang_id, qty, note,
        ma_tp, ten_sap, ma_nvl, ma_effect, don_vi_tinh,
        do_day, kho_1, kho_2, trong_luong_kg_tam, sl_dinh_muc,
        ma_dat_hang, chung_loai, ton_dau, ve_du_kien, vt_can_dung, ton_cuoi,
        so_luong_du_phong, so_luong_thieu, so_luong_can_mua, ghi_chu,
        tong_ton_nvl_sl, tong_hang_di_duong_sl, tong_sl_vt_can_dung,
        sl_du_tru_toi_thieu, sl_can_mua_theo_moq, sl_dat_mua_de_xuat,
        sl_dat_mua_chot, sl_ton_kho, so_ngay_vong_quay_ton, don_gia_ton_kho, gia_tri_ton_kho,
        create_uid, create_date, write_uid, write_date
    ) VALUES (
        'b2', 'dinh.muc', NEW.id,
        NEW.period_id, NEW.company_id, NEW.month_key, NEW.ma_sap,
        NULL, NULL, NULL, NEW.qty, NULL,
        NEW.ma_tp, NEW.ten_sap, NEW.ma_nvl, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
    )
    ON CONFLICT (source_model, source_res_id) DO UPDATE SET
        step_code = EXCLUDED.step_code,
        period_id = EXCLUDED.period_id,
        company_id = EXCLUDED.company_id,
        month_key = EXCLUDED.month_key,
        ma_sap = EXCLUDED.ma_sap,
        qty = EXCLUDED.qty,
        ma_tp = EXCLUDED.ma_tp,
        ten_sap = EXCLUDED.ten_sap,
        ma_nvl = EXCLUDED.ma_nvl,
        write_uid = EXCLUDED.write_uid,
        write_date = EXCLUDED.write_date;
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
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'tinh.toan.vat.tu' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;
    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, company_id, month_key, ma_sap,
        nganh_hang_id, dong_hang_id, ma_hang_id, qty, note,
        ma_tp, ten_sap, ma_nvl, ma_effect, don_vi_tinh,
        do_day, kho_1, kho_2, trong_luong_kg_tam, sl_dinh_muc,
        ma_dat_hang, chung_loai, ton_dau, ve_du_kien, vt_can_dung, ton_cuoi,
        so_luong_du_phong, so_luong_thieu, so_luong_can_mua, ghi_chu,
        tong_ton_nvl_sl, tong_hang_di_duong_sl, tong_sl_vt_can_dung,
        sl_du_tru_toi_thieu, sl_can_mua_theo_moq, sl_dat_mua_de_xuat,
        sl_dat_mua_chot, sl_ton_kho, so_ngay_vong_quay_ton, don_gia_ton_kho, gia_tri_ton_kho,
        create_uid, create_date, write_uid, write_date
    ) VALUES (
        'b3', 'tinh.toan.vat.tu', NEW.id,
        NEW.period_id, NEW.company_id, NEW.month_key, NEW.ma_sap,
        NULL, NULL, NULL, NEW.qty, NULL,
        NULL, NEW.ten_sap, NULL, NEW.ma_effect, NEW.don_vi_tinh,
        NEW.do_day, NEW.kho_1, NEW.kho_2, NEW.trong_luong_kg_tam, NEW.sl_dinh_muc,
        NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
    )
    ON CONFLICT (source_model, source_res_id) DO UPDATE SET
        step_code = EXCLUDED.step_code,
        period_id = EXCLUDED.period_id,
        company_id = EXCLUDED.company_id,
        month_key = EXCLUDED.month_key,
        ma_sap = EXCLUDED.ma_sap,
        qty = EXCLUDED.qty,
        ten_sap = EXCLUDED.ten_sap,
        ma_effect = EXCLUDED.ma_effect,
        don_vi_tinh = EXCLUDED.don_vi_tinh,
        do_day = EXCLUDED.do_day,
        kho_1 = EXCLUDED.kho_1,
        kho_2 = EXCLUDED.kho_2,
        trong_luong_kg_tam = EXCLUDED.trong_luong_kg_tam,
        sl_dinh_muc = EXCLUDED.sl_dinh_muc,
        write_uid = EXCLUDED.write_uid,
        write_date = EXCLUDED.write_date;
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
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'tong.hop.vat.tu' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;
    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, company_id, month_key, ma_sap,
        nganh_hang_id, dong_hang_id, ma_hang_id, qty, note,
        ma_tp, ten_sap, ma_nvl, ma_effect, don_vi_tinh,
        do_day, kho_1, kho_2, trong_luong_kg_tam, sl_dinh_muc,
        ma_dat_hang, chung_loai, ton_dau, ve_du_kien, vt_can_dung, ton_cuoi,
        so_luong_du_phong, so_luong_thieu, so_luong_can_mua, ghi_chu,
        tong_ton_nvl_sl, tong_hang_di_duong_sl, tong_sl_vt_can_dung,
        sl_du_tru_toi_thieu, sl_can_mua_theo_moq, sl_dat_mua_de_xuat,
        sl_dat_mua_chot, sl_ton_kho, so_ngay_vong_quay_ton, don_gia_ton_kho, gia_tri_ton_kho,
        create_uid, create_date, write_uid, write_date
    ) VALUES (
        'b4', 'tong.hop.vat.tu', NEW.id,
        NEW.period_id, NEW.company_id, NEW.month_key, NEW.ma_sap,
        NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NULL, NEW.don_vi_tinh,
        NULL, NULL, NULL, NULL, NULL,
        NEW.ma_dat_hang, NEW.chung_loai, NEW.ton_dau, NEW.ve_du_kien, NEW.vt_can_dung, NEW.ton_cuoi,
        NEW.so_luong_du_phong, NEW.so_luong_thieu, NEW.so_luong_can_mua, NEW.ghi_chu,
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
    )
    ON CONFLICT (source_model, source_res_id) DO UPDATE SET
        step_code = EXCLUDED.step_code,
        period_id = EXCLUDED.period_id,
        company_id = EXCLUDED.company_id,
        month_key = EXCLUDED.month_key,
        ma_sap = EXCLUDED.ma_sap,
        don_vi_tinh = EXCLUDED.don_vi_tinh,
        ma_dat_hang = EXCLUDED.ma_dat_hang,
        chung_loai = EXCLUDED.chung_loai,
        ton_dau = EXCLUDED.ton_dau,
        ve_du_kien = EXCLUDED.ve_du_kien,
        vt_can_dung = EXCLUDED.vt_can_dung,
        ton_cuoi = EXCLUDED.ton_cuoi,
        so_luong_du_phong = EXCLUDED.so_luong_du_phong,
        so_luong_thieu = EXCLUDED.so_luong_thieu,
        so_luong_can_mua = EXCLUDED.so_luong_can_mua,
        ghi_chu = EXCLUDED.ghi_chu,
        write_uid = EXCLUDED.write_uid,
        write_date = EXCLUDED.write_date;
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
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM du_lieu_tong_hop_vat_tu
        WHERE source_model = 'kh.dat.vat.tu' AND source_res_id = OLD.id;
        RETURN OLD;
    END IF;
    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id,
        period_id, company_id, month_key, ma_sap,
        nganh_hang_id, dong_hang_id, ma_hang_id, qty, note,
        ma_tp, ten_sap, ma_nvl, ma_effect, don_vi_tinh,
        do_day, kho_1, kho_2, trong_luong_kg_tam, sl_dinh_muc,
        ma_dat_hang, chung_loai, ton_dau, ve_du_kien, vt_can_dung, ton_cuoi,
        so_luong_du_phong, so_luong_thieu, so_luong_can_mua, ghi_chu,
        tong_ton_nvl_sl, tong_hang_di_duong_sl, tong_sl_vt_can_dung,
        sl_du_tru_toi_thieu, sl_can_mua_theo_moq, sl_dat_mua_de_xuat,
        sl_dat_mua_chot, sl_ton_kho, so_ngay_vong_quay_ton, don_gia_ton_kho, gia_tri_ton_kho,
        create_uid, create_date, write_uid, write_date
    ) VALUES (
        'b5', 'kh.dat.vat.tu', NEW.id,
        NEW.period_id, NEW.company_id, NEW.month_key, NEW.ma_sap,
        NULL, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NEW.ma_effect, NEW.don_vi_tinh,
        NULL, NULL, NULL, NULL, NULL,
        NULL, NEW.chung_loai, NULL, NULL, NULL, NULL,
        NULL, NULL, NULL, NEW.ghi_chu,
        NEW.tong_ton_nvl_sl, NEW.tong_hang_di_duong_sl, NEW.tong_sl_vt_can_dung,
        NEW.sl_du_tru_toi_thieu, NEW.sl_can_mua_theo_moq, NEW.sl_dat_mua_de_xuat,
        NEW.sl_dat_mua_chot, NEW.sl_ton_kho, NEW.so_ngay_vong_quay_ton, NEW.don_gia_ton_kho, NEW.gia_tri_ton_kho,
        NEW.create_uid, NEW.create_date, NEW.write_uid, NEW.write_date
    )
    ON CONFLICT (source_model, source_res_id) DO UPDATE SET
        step_code = EXCLUDED.step_code,
        period_id = EXCLUDED.period_id,
        company_id = EXCLUDED.company_id,
        month_key = EXCLUDED.month_key,
        ma_sap = EXCLUDED.ma_sap,
        ma_effect = EXCLUDED.ma_effect,
        don_vi_tinh = EXCLUDED.don_vi_tinh,
        chung_loai = EXCLUDED.chung_loai,
        ghi_chu = EXCLUDED.ghi_chu,
        tong_ton_nvl_sl = EXCLUDED.tong_ton_nvl_sl,
        tong_hang_di_duong_sl = EXCLUDED.tong_hang_di_duong_sl,
        tong_sl_vt_can_dung = EXCLUDED.tong_sl_vt_can_dung,
        sl_du_tru_toi_thieu = EXCLUDED.sl_du_tru_toi_thieu,
        sl_can_mua_theo_moq = EXCLUDED.sl_can_mua_theo_moq,
        sl_dat_mua_de_xuat = EXCLUDED.sl_dat_mua_de_xuat,
        sl_dat_mua_chot = EXCLUDED.sl_dat_mua_chot,
        sl_ton_kho = EXCLUDED.sl_ton_kho,
        so_ngay_vong_quay_ton = EXCLUDED.so_ngay_vong_quay_ton,
        don_gia_ton_kho = EXCLUDED.don_gia_ton_kho,
        gia_tri_ton_kho = EXCLUDED.gia_tri_ton_kho,
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
-- SYNC: md_sap_bom → bom (ORM table)
-- Khi md_sap_bom được INSERT/UPDATE, tự động UPSERT vào bảng bom.
-- Tạm thời gán company_id = 17 (SHE). Sau này sẽ mapping từ chi_nhanh.
-- =============================================================================

-- Helper: parse số SAP (xử lý dấu trừ cuối: "0.727-" → -0.727, lỗi → 0)
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
    v_sl_dm NUMERIC;
    v_existing_id INTEGER;
    -- Lấy ma_bom
    DECLARE
        v_ma_bom VARCHAR;
        v_sl_spdm NUMERIC;
    BEGIN
        -- Bỏ qua nếu thiếu mã TP hoặc mã NVL
        IF NEW.ma_tp IS NULL OR TRIM(NEW.ma_tp) = '' THEN
            RETURN NEW;
        END IF;
        IF NEW.ma_nvl IS NULL OR TRIM(NEW.ma_nvl) = '' THEN
            RETURN NEW;
        END IF;

        v_ma_bom := TRIM(COALESCE(NEW.ma_bom, ''));
        
        -- Parse sl_dm và sl_spdm
        v_sl_dm := safe_sap_numeric(NEW.sl_dm);
        v_sl_spdm := safe_sap_numeric(NEW.sl_spdm);
        IF v_sl_spdm = 0 THEN
            v_sl_spdm := 1.0;
        END IF;

        -- Kiểm tra đã tồn tại chưa (theo ma_bom + ma_tp + ma_nvl)
        SELECT id INTO v_existing_id
        FROM bom
        WHERE ma_bom = v_ma_bom
          AND ma_tp = TRIM(NEW.ma_tp)
          AND ma_nvl = TRIM(NEW.ma_nvl)
        LIMIT 1;

        IF v_existing_id IS NOT NULL THEN
            -- UPDATE dòng đã có
            UPDATE bom SET
                ten_tp = COALESCE(NULLIF(TRIM(NEW.ten_tp), ''), ten_tp),
                ten_nvl = COALESCE(NULLIF(TRIM(NEW.ten_nvl), ''), ten_nvl),
                sl_dinh_muc = COALESCE(v_sl_dm, sl_dinh_muc),
                sl_spdm = COALESCE(v_sl_spdm, sl_spdm),
                write_date = NOW() AT TIME ZONE 'UTC'
            WHERE id = v_existing_id;
        ELSE
            -- INSERT dòng mới
            INSERT INTO bom (
                ma_bom, ma_tp, ten_tp, ma_nvl, ten_nvl, sl_dinh_muc, sl_spdm,
                do_day, kho_1, kho_2,
                create_uid, create_date, write_uid, write_date
            ) VALUES (
                v_ma_bom,
                TRIM(NEW.ma_tp),
                COALESCE(NULLIF(TRIM(NEW.ten_tp), ''), TRIM(NEW.ma_tp)),
                TRIM(NEW.ma_nvl),
                COALESCE(NULLIF(TRIM(NEW.ten_nvl), ''), TRIM(NEW.ma_nvl)),
                COALESCE(v_sl_dm, 0),
                v_sl_spdm,
                0, 0, 0,  -- do_day, kho_1, kho_2 SAP không cung cấp, user import bổ sung
                1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC'
            );
        END IF;

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
        RAISE NOTICE 'Trigger trg_sync_sap_bom created on md_sap_bom';

        INSERT INTO bom (ma_bom, ma_tp, ten_tp, ma_nvl, ten_nvl,
                         sl_dinh_muc, sl_spdm, do_day, kho_1, kho_2,
                         create_uid, create_date, write_uid, write_date)
        SELECT
            d.ma_bom, d.ma_tp, d.ten_tp, d.ma_nvl, d.ten_nvl,
            d.sl_dm_num, d.sl_spdm_num,
            0, 0, 0,
            1, NOW() AT TIME ZONE 'UTC',
            1, NOW() AT TIME ZONE 'UTC'
        FROM (
            SELECT DISTINCT ON (TRIM(COALESCE(s.ma_bom, '')), TRIM(s.ma_tp), TRIM(s.ma_nvl))
                TRIM(COALESCE(s.ma_bom, '')) AS ma_bom,
                TRIM(s.ma_tp) AS ma_tp,
                COALESCE(NULLIF(TRIM(s.ten_tp), ''), TRIM(s.ma_tp)) AS ten_tp,
                TRIM(s.ma_nvl) AS ma_nvl,
                COALESCE(NULLIF(TRIM(s.ten_nvl), ''), TRIM(s.ma_nvl)) AS ten_nvl,
                safe_sap_numeric(s.sl_dm) AS sl_dm_num,
                NULLIF(safe_sap_numeric(s.sl_spdm), 0) AS sl_spdm_num
            FROM md_sap_bom s
            WHERE s.ma_tp IS NOT NULL AND TRIM(s.ma_tp) != ''
              AND s.ma_nvl IS NOT NULL AND TRIM(s.ma_nvl) != ''
            ORDER BY TRIM(COALESCE(s.ma_bom, '')), TRIM(s.ma_tp), TRIM(s.ma_nvl), s.id DESC
        ) d
        ON CONFLICT (ma_bom, ma_tp, ma_nvl) DO UPDATE SET
            ten_tp = COALESCE(NULLIF(EXCLUDED.ten_tp, ''), bom.ten_tp),
            ten_nvl = COALESCE(NULLIF(EXCLUDED.ten_nvl, ''), bom.ten_nvl),
            sl_dinh_muc = EXCLUDED.sl_dinh_muc,
            sl_spdm = COALESCE(EXCLUDED.sl_spdm, bom.sl_spdm, 1.0),
            write_date = NOW() AT TIME ZONE 'UTC';
        RAISE NOTICE 'Backfilled existing md_sap_bom data into bom table';
    ELSE
        RAISE NOTICE 'Table md_sap_bom not found, trigger will be created on next module upgrade';
    END IF;
END $$;

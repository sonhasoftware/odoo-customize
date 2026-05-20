-- ============================================================
-- B2: Sinh định mức từ bom_tinh_toan
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_sinh_dinh_muc(p_period_id INTEGER)
LANGUAGE 'plpgsql' AS $BODY$
BEGIN
    DELETE FROM dinh_muc WHERE period_id = p_period_id;

    INSERT INTO dinh_muc (
        period_id, company_id, ma_sap, ten_sap, ma_tp, ma_nvl,
        month_key, month_date, qty,
        create_uid, write_uid, create_date, write_date
    )
    SELECT
        p_period_id,
        b1.company_id,
        b1.ma_sap,
        bcu.ten_tp_goc,
        bcu.ma_tp_cha,          -- Key tra do_day/kho_1/kho_2 ở B3
        bcu.ma_con,             -- Mã NVL thực tế cuối cùng
        b1.month_key,
        COALESCE(b1.month_date, TO_DATE(b1.month_key, 'MM/YYYY')),
        b1.qty * bcu.sl_thuc_te,
        1, 1, NOW(), NOW()
    FROM ke_hoach_vat_tu_line b1
    JOIN bom_tinh_toan bcu
        ON bcu.ma_tp_goc = b1.ma_sap
       AND bcu.loai_vat_tu = 'NVL'
    WHERE b1.period_id = p_period_id;
END;
$BODY$;

-- ============================================================
-- B3: Tính toán vật tư (kg) từ định mức + trọng lượng bom
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_tinh_toan_vat_tu(p_period_id INTEGER)
LANGUAGE 'plpgsql' AS $BODY$
DECLARE
    v_uom_kg_id INTEGER;
BEGIN
    DELETE FROM tinh_toan_vat_tu WHERE period_id = p_period_id;

    SELECT res_id INTO v_uom_kg_id
    FROM ir_model_data
    WHERE module = 'uom' AND name = 'product_uom_kgm'
    LIMIT 1;

    INSERT INTO tinh_toan_vat_tu (
        period_id, company_id, ma_sap, ma_vat_tu, ten_vat_tu, ma_effect, ten_sap,
        don_vi_tinh, do_day, kho_1, kho_2, trong_luong_kg_tam,
        sl_dinh_muc, month_key, month_date, qty,
        create_uid, write_uid, create_date, write_date
    )
    SELECT
        dm.period_id,
        dm.company_id,
        dm.ma_sap,
        dm.ma_nvl                                                       AS ma_vat_tu,
        COALESCE(mh.ten_nvl, b.ten_nvl, dm.ma_nvl)                      AS ten_vat_tu,
        NULL::VARCHAR                                                   AS ma_effect,
        dm.ten_sap,
        mh.don_vi_tinh_id                                               AS don_vi_tinh,
        COALESCE(b.do_day, 0)                                           AS do_day,
        COALESCE(b.kho_1, 0)                                            AS kho_1,
        COALESCE(b.kho_2, 0)                                            AS kho_2,
        CASE
            WHEN COALESCE(b.do_day, 0) > 0
             AND COALESCE(b.kho_1, 0) > 0
             AND COALESCE(b.kho_2, 0) > 0
            THEN (b.do_day * b.kho_1 * b.kho_2 * 7.63) / 1000000.0
            ELSE 0
        END                                                             AS trong_luong_kg_tam,
        COALESCE(dm.qty, 0)                                             AS sl_dinh_muc,
        dm.month_key,
        COALESCE(dm.month_date, TO_DATE(dm.month_key, 'MM/YYYY')),
        dm.qty                                                          AS qty,
        1, 1, NOW(), NOW()
    FROM dinh_muc dm
    LEFT JOIN bom b ON b.ma_tp = dm.ma_tp AND b.ma_nvl = dm.ma_nvl
    LEFT JOIN ma_hang mh ON mh.ma_sap = dm.ma_nvl
    WHERE dm.period_id = p_period_id;
END;
$BODY$;

-- ============================================================
-- B4: Tổng hợp vật tư + tồn kho (cuốn chiếu theo tháng)
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_tong_hop_vat_tu(
    p_period_id INTEGER,
    p_ngay_dp   NUMERIC DEFAULT 15.0
)
LANGUAGE 'plpgsql' AS $BODY$
DECLARE
    v_uom_kg_id      INTEGER;
    v_ton_cuoi_cache JSONB DEFAULT '{}';
    rec              RECORD;
    v_cache_key      TEXT;
    v_comp_grp       TEXT;
    v_ton_dau        NUMERIC;
    v_ton_cuoi       NUMERIC;
    v_don_gia        NUMERIC;
    v_ve_du_kien     NUMERIC;
    v_sl_du_phong    NUMERIC;
    v_sl_thieu       NUMERIC;
    v_tcu NUMERIC; v_ttcu NUMERIC; v_tdu NUMERIC; v_ttdu NUMERIC;
BEGIN
    DELETE FROM tong_hop_vat_tu WHERE period_id = p_period_id;

    SELECT res_id INTO v_uom_kg_id
    FROM ir_model_data
    WHERE module = 'uom' AND name = 'product_uom_kgm'
    LIMIT 1;

    -- ── Bước 1: Pre-load tồn kho SAP (chạy 1 lần, dùng mãi trong loop) ──
    -- Latest record per (ma_hang, chi_nhanh), rồi group theo 3 nhóm công ty.
    -- 'BNH' → chi_nhanh LIKE '21%', 'SSP' → '22%', 'ALL' → toàn bộ.
    CREATE TEMP TABLE _tmp_ton_kho ON COMMIT DROP AS
    WITH latest AS (
        SELECT DISTINCT ON (TRIM(ma_hang), chi_nhanh)
            TRIM(ma_hang)                        AS ma_hang,
            chi_nhanh,
            safe_sap_numeric(ton_cuoi)           AS ton_cuoi,
            safe_sap_numeric(tien_ton_cuoi)      AS tien_ton_cuoi,
            safe_sap_numeric(ton_dau)            AS ton_dau,
            safe_sap_numeric(tien_ton_dau)       AS tien_ton_dau
        FROM md_sap_ton_kho
        ORDER BY TRIM(ma_hang), chi_nhanh, create_date DESC, id DESC
    )
    SELECT ma_hang, 'BNH' AS comp_grp,
           SUM(ton_cuoi) tcu, SUM(tien_ton_cuoi) ttcu,
           SUM(ton_dau)  tdu, SUM(tien_ton_dau)  ttdu
    FROM latest WHERE chi_nhanh LIKE '21%' GROUP BY ma_hang
    UNION ALL
    SELECT ma_hang, 'SSP',
           SUM(ton_cuoi), SUM(tien_ton_cuoi),
           SUM(ton_dau),  SUM(tien_ton_dau)
    FROM latest WHERE chi_nhanh LIKE '22%' GROUP BY ma_hang
    UNION ALL
    SELECT ma_hang, 'ALL',
           SUM(ton_cuoi), SUM(tien_ton_cuoi),
           SUM(ton_dau),  SUM(tien_ton_dau)
    FROM latest WHERE chi_nhanh NOT LIKE '10%' GROUP BY ma_hang;

    CREATE INDEX ON _tmp_ton_kho (ma_hang, comp_grp);

    -- ── Bước 2: Pre-load vật tư đi đường ──
    CREATE TEMP TABLE _tmp_vdd ON COMMIT DROP AS
    SELECT
        company_id,
        month_key,
        COALESCE(month_date, TO_DATE(month_key, 'MM/YYYY')) AS month_date,
        ma_sap,
        so_luong
    FROM vat_tu_di_duong;

    CREATE INDEX ON _tmp_vdd (company_id, month_date, ma_sap);

    -- ── Bước 3: Vòng lặp cuốn chiếu tồn kho ──
    FOR rec IN
        SELECT
            b3.company_id,
            c.company_code,
            b3.ma_sap,
            b3.ma_vat_tu AS material_code,
            mh.don_vi_tinh_id                  AS don_vi_tinh,
            b3.month_key,
            COALESCE(b3.month_date, TO_DATE(b3.month_key, 'MM/YYYY')) AS month_date,
            SUM(b3.qty * CASE WHEN COALESCE(b3.trong_luong_kg_tam, 0) > 0 THEN b3.trong_luong_kg_tam ELSE 1.0 END) AS vt_can_dung
        FROM tinh_toan_vat_tu b3
        JOIN res_company c ON c.id = b3.company_id
        LEFT JOIN ma_hang mh ON mh.ma_sap = b3.ma_vat_tu
        WHERE b3.period_id = p_period_id
        GROUP BY b3.company_id, c.company_code, b3.ma_sap,
                 b3.ma_vat_tu, b3.month_key,
                 COALESCE(b3.month_date, TO_DATE(b3.month_key, 'MM/YYYY')),
                 mh.don_vi_tinh_id
        ORDER BY b3.company_id, b3.ma_vat_tu, COALESCE(b3.month_date, TO_DATE(b3.month_key, 'MM/YYYY'))
    LOOP
        v_comp_grp  := CASE 
                           WHEN rec.company_code LIKE '21%' OR rec.company_code = 'BNH' THEN 'BNH'
                           WHEN rec.company_code LIKE '22%' OR rec.company_code = 'SSP' THEN 'SSP'
                           ELSE 'ALL'
                       END;
        v_cache_key := rec.company_id::TEXT || '_' || rec.material_code;
        -- Tồn đầu: cuốn chiếu từ tháng trước hoặc lấy từ temp table
        v_ton_dau := 0;
        IF v_ton_cuoi_cache ? v_cache_key THEN
            v_ton_dau := (v_ton_cuoi_cache ->> v_cache_key)::NUMERIC;
        ELSE
            SELECT COALESCE(tcu, 0) INTO v_ton_dau
            FROM _tmp_ton_kho
            WHERE ma_hang = rec.material_code AND comp_grp = v_comp_grp;
            v_ton_dau := COALESCE(v_ton_dau, 0);
        END IF;

        -- Đơn giá tồn kho
        v_tcu := 0; v_ttcu := 0; v_tdu := 0; v_ttdu := 0;
        SELECT COALESCE(tcu, 0), COALESCE(ttcu, 0),
               COALESCE(tdu, 0), COALESCE(ttdu, 0)
        INTO   v_tcu, v_ttcu, v_tdu, v_ttdu
        FROM _tmp_ton_kho
        WHERE ma_hang = rec.material_code AND comp_grp = v_comp_grp;
        v_tcu := COALESCE(v_tcu, 0);
        v_ttcu := COALESCE(v_ttcu, 0);
        v_tdu := COALESCE(v_tdu, 0);
        v_ttdu := COALESCE(v_ttdu, 0);

        v_don_gia := CASE
            WHEN v_tcu != 0 THEN v_ttcu / v_tcu
            WHEN v_tdu != 0 THEN v_ttdu / v_tdu
            ELSE 0
        END;

        -- Vật tư đi đường
        v_ve_du_kien := 0;
        SELECT COALESCE(so_luong, 0) INTO v_ve_du_kien
        FROM _tmp_vdd
        WHERE company_id = rec.company_id
          AND month_date = rec.month_date
          AND ma_sap     = rec.material_code;
        v_ve_du_kien := COALESCE(v_ve_du_kien, 0);

        v_sl_du_phong := CASE WHEN COALESCE(rec.vt_can_dung, 0) > 0
                              THEN rec.vt_can_dung / (28.0 * p_ngay_dp)
                              ELSE 0 END;
        v_ton_cuoi    := v_ton_dau + v_ve_du_kien - COALESCE(rec.vt_can_dung, 0);
        v_sl_thieu    := GREATEST(0.0, v_sl_du_phong - v_ton_cuoi);

        v_ton_cuoi_cache := jsonb_set(
            v_ton_cuoi_cache,
            ARRAY[v_cache_key]::TEXT[],
            to_jsonb(v_ton_cuoi)
        );

        INSERT INTO tong_hop_vat_tu (
            period_id, company_id, ma_dat_hang, ma_sap, chung_loai,
            don_vi_tinh, month_key, month_date,
            ton_dau, ve_du_kien, vt_can_dung, ton_cuoi,
            so_luong_du_phong, so_luong_thieu, so_luong_can_mua,
            create_uid, write_uid, create_date, write_date
        ) VALUES (
            p_period_id, rec.company_id, rec.material_code, rec.ma_sap, rec.material_code,
            rec.don_vi_tinh, rec.month_key, rec.month_date,
            v_ton_dau, COALESCE(v_ve_du_kien, 0), rec.vt_can_dung, v_ton_cuoi,
            v_sl_du_phong, v_sl_thieu, v_sl_thieu,
            1, 1, NOW(), NOW()
        );
    END LOOP;

    DROP TABLE IF EXISTS _tmp_ton_kho;
    DROP TABLE IF EXISTS _tmp_vdd;
END;
$BODY$;

-- ============================================================
-- B5: Kế hoạch đặt vật tư từ B4
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_ke_hoach_dat_vat_tu(
    p_period_id INTEGER,
    p_ngay_dt   NUMERIC DEFAULT 20.0
)
LANGUAGE 'plpgsql' AS $BODY$
DECLARE
    v_uom_kg_id INTEGER;
BEGIN
    DELETE FROM kh_dat_vat_tu WHERE period_id = p_period_id;

    SELECT res_id INTO v_uom_kg_id
    FROM ir_model_data
    WHERE module = 'uom' AND name = 'product_uom_kgm'
    LIMIT 1;

    INSERT INTO kh_dat_vat_tu (
        period_id, company_id, month_key, month_date, ma_sap, ma_effect, ma_cuon,
        don_vi_tinh,
        tong_ton_nvl_sl, tong_hang_di_duong_sl, tong_sl_vt_can_dung,
        sl_du_tru_toi_thieu, sl_can_mua_theo_moq, don_gia_ton_kho,
        sl_dat_mua_de_xuat, sl_dat_mua_chot, sl_ton_kho,
        so_ngay_vong_quay_ton, gia_tri_ton_kho, ghi_chu,
        create_uid, write_uid, create_date, write_date
    )
    WITH ton_kho_agg AS (
        SELECT
            ma_hang,
            CASE WHEN chi_nhanh LIKE '21%' THEN 'BNH'
                 WHEN chi_nhanh LIKE '22%' THEN 'SSP'
                 ELSE 'ALL'
            END                        AS comp_grp,
            SUM(ton_cuoi)              AS tcu,
            SUM(tien_ton_cuoi)         AS ttcu,
            SUM(ton_dau)               AS tdu,
            SUM(tien_ton_dau)          AS ttdu
        FROM (
            SELECT DISTINCT ON (REGEXP_REPLACE(TRIM(ma_hang), '^0+', ''), chi_nhanh)
                REGEXP_REPLACE(TRIM(ma_hang), '^0+', '') AS ma_hang,
                chi_nhanh,
                safe_sap_numeric(ton_cuoi)           AS ton_cuoi,
                safe_sap_numeric(tien_ton_cuoi)      AS tien_ton_cuoi,
                safe_sap_numeric(ton_dau)            AS ton_dau,
                safe_sap_numeric(tien_ton_dau)       AS tien_ton_dau
            FROM md_sap_ton_kho
            WHERE chi_nhanh NOT LIKE '10%'
            ORDER BY REGEXP_REPLACE(TRIM(ma_hang), '^0+', ''), chi_nhanh, create_date DESC, id DESC
        ) latest
        GROUP BY ma_hang, comp_grp
    )
    SELECT
        final_b5.period_id, final_b5.company_id, final_b5.month_key, final_b5.month_date,
        final_b5.ma_sap, final_b5.ma_effect, final_b5.ma_cuon, final_b5.don_vi_tinh,
        final_b5.ton_dau, final_b5.ve_du_kien, final_b5.vt_can_dung,
        final_b5.sl_du_tru_toi_thieu, final_b5.sl_can_mua_theo_moq, final_b5.don_gia_ton_kho,
        final_b5.sl_dat_mua_de_xuat,
        (CASE WHEN final_b5.sl_dat_mua_de_xuat > 0 THEN 0.0 ELSE -final_b5.sl_dat_mua_de_xuat END) AS sl_dat_mua_chot,
        final_b5.sl_ton_kho,
        (CASE WHEN final_b5.vt_can_dung > 0 THEN (final_b5.sl_ton_kho / final_b5.vt_can_dung * 30.0) ELSE 0.0 END) AS so_ngay_vong_quay_ton,
        (final_b5.sl_ton_kho * final_b5.don_gia_ton_kho) AS gia_tri_ton_kho,
        final_b5.ghi_chu,
        1, 1, NOW(), NOW()
    FROM (
        SELECT
            b4.period_id,
            b4.company_id,
            b4.month_key,
            COALESCE(b4.month_date, TO_DATE(b4.month_key, 'MM/YYYY')) AS month_date,
            b4.ma_sap,
            NULL::VARCHAR                            AS ma_effect,
            NULL::VARCHAR                            AS ma_cuon,
            b4.don_vi_tinh                           AS don_vi_tinh,
            b4.ton_dau,
            b4.ve_du_kien,
            COALESCE(b4.vt_can_dung, 0)              AS vt_can_dung,
            CASE WHEN COALESCE(b4.vt_can_dung, 0) > 0
                 THEN b4.vt_can_dung / (28.0 * p_ngay_dt)
                 ELSE 0 END                           AS sl_du_tru_toi_thieu,
            NULL::NUMERIC                             AS sl_can_mua_theo_moq,
            CASE
                WHEN COALESCE(tk.tcu, 0) != 0 THEN tk.ttcu / tk.tcu
                WHEN COALESCE(tk.tdu, 0) != 0 THEN tk.ttdu / tk.tdu
                ELSE 0
            END                                       AS don_gia_ton_kho,
            (b4.ton_dau - COALESCE(b4.vt_can_dung, 0) + b4.ve_du_kien - (CASE WHEN COALESCE(b4.vt_can_dung, 0) > 0 THEN b4.vt_can_dung / (28.0 * p_ngay_dt) ELSE 0 END)) AS sl_dat_mua_de_xuat,
            (b4.ton_dau - COALESCE(b4.vt_can_dung, 0) + b4.ve_du_kien + 0) AS sl_ton_kho,
            b4.ghi_chu
        FROM tong_hop_vat_tu b4
        JOIN res_company c ON c.id = b4.company_id
        LEFT JOIN ton_kho_agg tk
            ON  tk.ma_hang   = COALESCE(b4.ma_dat_hang, b4.ma_sap)
            AND tk.comp_grp  = CASE 
                                   WHEN c.company_code LIKE '21%' OR c.company_code = 'BNH' THEN 'BNH'
                                   WHEN c.company_code LIKE '22%' OR c.company_code = 'SSP' THEN 'SSP'
                                   ELSE 'ALL'
                               END
        WHERE b4.period_id = p_period_id
    ) final_b5;
END;
$BODY$;

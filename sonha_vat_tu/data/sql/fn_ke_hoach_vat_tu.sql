-- ============================================================
-- B2: Sinh dinh muc tu bom_tinh_toan
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_sinh_dinh_muc(p_period_id INTEGER)
LANGUAGE 'plpgsql' AS $BODY$
BEGIN
    DELETE FROM dinh_muc WHERE period_id = p_period_id;

    INSERT INTO dinh_muc (
        period_id, company_id, ma_sap, ten_sap, ma_tp, ten_tp, ma_nvl, ten_nvl,
        qty_kinh_doanh_t0, qty_kinh_doanh_t1, qty_kinh_doanh_t2, qty_kinh_doanh_t3,
        qty_san_xuat_t0, qty_san_xuat_t1, qty_san_xuat_t2, qty_san_xuat_t3,
        qty_chenh_lech_t0, qty_chenh_lech_t1, qty_chenh_lech_t2, qty_chenh_lech_t3,
        qty_t0, qty_t1, qty_t2, qty_t3,
        create_uid, write_uid, create_date, write_date
    )
    SELECT
        b1.period_id,
        b1.company_id,
        b1.ma_sap,
        bcu.ten_tp_goc,
        bcu.ma_tp_cha,
        bcu.ten_tp_cha,
        bcu.ma_con,
        bcu.ten_con,
        COALESCE(b1.qty_kd_t0, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_kd_t1, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_kd_t2, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_kd_t3, 0) * bcu.sl_thuc_te,
        COALESCE(b1.qty_sx_t0, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_sx_t1, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_sx_t2, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_sx_t3, 0) * bcu.sl_thuc_te,
        COALESCE(b1.qty_cl_t0, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_cl_t1, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_cl_t2, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_cl_t3, 0) * bcu.sl_thuc_te,
        COALESCE(b1.qty_t0, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_t1, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_t2, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_t3, 0) * bcu.sl_thuc_te,
        1, 1, NOW(), NOW()
    FROM ke_hoach_vat_tu_line b1
    JOIN bom_tinh_toan bcu
        ON bcu.ma_tp_goc = b1.ma_sap
       AND bcu.loai_vat_tu = 'NVL'
    WHERE b1.period_id = p_period_id;
END;
$BODY$;

-- ============================================================
-- B3: Tinh toan vat tu tu ke hoach kinh doanh (theo don vi KD)
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_tinh_toan_vat_tu(p_period_id INTEGER)
LANGUAGE 'plpgsql' AS $BODY$
DECLARE
    v_prod_company_id INTEGER;
BEGIN
    DELETE FROM tinh_toan_vat_tu WHERE period_id = p_period_id;

    SELECT MIN(company_id) INTO v_prod_company_id
    FROM ke_hoach_vat_tu_line
    WHERE period_id = p_period_id AND company_id IS NOT NULL;

    IF v_prod_company_id IS NULL THEN
        SELECT MIN(company_id) INTO v_prod_company_id
        FROM ke_hoach_san_xuat
        WHERE period_id = p_period_id AND company_id IS NOT NULL;
    END IF;

    INSERT INTO tinh_toan_vat_tu (
        period_id, company_id, don_vi_kd_id, don_vi_kd_code, ma_sap, ma_vat_tu, ten_vat_tu, ten_sap,
        ma_effect, don_vi_tinh, do_day, kho_1, kho_2, trong_luong_kg_tam,
        sl_dinh_muc, qty_t0, qty_t1, qty_t2, qty_t3,
        create_uid, write_uid, create_date, write_date
    )
    SELECT
        agg.period_id,
        v_prod_company_id,
        agg.don_vi_kd_id,
        COALESCE(NULLIF(TRIM(dv.company_code), ''), dv.name)     AS don_vi_kd_code,
        agg.ma_sap_rep,
        agg.ma_vat_tu,
        COALESCE(mh.ten_hang, agg.ma_vat_tu)                     AS ten_vat_tu,
        agg.ten_sap_rep                                          AS ten_sap,
        COALESCE(NULLIF(TRIM(mh.ma_mdm), ''), mh.ma_sap, agg.ma_vat_tu) AS ma_effect,
        mh.don_vi_tinh_id                                        AS don_vi_tinh,
        0::NUMERIC, 0::NUMERIC, 0::NUMERIC, 0::NUMERIC,
        agg.sl_dinh_muc,
        agg.qty_t0, agg.qty_t1, agg.qty_t2, agg.qty_t3,
        1, 1, NOW(), NOW()
    FROM (
        SELECT
            kd.period_id,
            kd.company_id                                            AS don_vi_kd_id,
            bcu.ma_con                                               AS ma_vat_tu,
            MIN(kd.ma_sap)                                           AS ma_sap_rep,
            MIN(bcu.ten_tp_goc)                                      AS ten_sap_rep,
            MAX(COALESCE(bcu.sl_thuc_te, 0))::NUMERIC               AS sl_dinh_muc,
            SUM(COALESCE(kd.qty_t0, 0) * COALESCE(bcu.sl_thuc_te, 0)) AS qty_t0,
            SUM(COALESCE(kd.qty_t1, 0) * COALESCE(bcu.sl_thuc_te, 0)) AS qty_t1,
            SUM(COALESCE(kd.qty_t2, 0) * COALESCE(bcu.sl_thuc_te, 0)) AS qty_t2,
            SUM(COALESCE(kd.qty_t3, 0) * COALESCE(bcu.sl_thuc_te, 0)) AS qty_t3
        FROM ke_hoach_kinh_doanh kd
        JOIN bom_tinh_toan bcu
            ON bcu.ma_tp_goc = kd.ma_sap
           AND bcu.loai_vat_tu = 'NVL'
        WHERE kd.period_id = p_period_id
          AND kd.ma_sap IS NOT NULL
          AND TRIM(kd.ma_sap) <> ''
          AND kd.company_id IS NOT NULL
        GROUP BY kd.period_id, kd.company_id, bcu.ma_con
    ) agg
    JOIN res_company dv ON dv.id = agg.don_vi_kd_id
    LEFT JOIN ma_hang mh ON mh.ma_sap = agg.ma_vat_tu;
END;
$BODY$;

-- ============================================================
-- B4: Tong hop vat tu - Tinh don luy ke theo Excel
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_tong_hop_vat_tu(
    p_period_id INTEGER,
    p_ngay_dp   NUMERIC DEFAULT 15.0
)
LANGUAGE 'plpgsql' AS $BODY$
DECLARE
    v_ton_cuoi_cache JSONB DEFAULT '{}';
    v_seen_cache     JSONB DEFAULT '{}';
    rec              RECORD;
    v_cache_key      TEXT;
    v_comp_grp       TEXT;
    v_ton_dau        NUMERIC;
    v_ve_du_kien_t0  NUMERIC;
    v_ve_du_kien_t1  NUMERIC;
    v_ve_du_kien_t2  NUMERIC;
    v_ve_du_kien_t3  NUMERIC;
    v_ve_du_kien_don_vi_t0  NUMERIC;
    v_ve_du_kien_don_vi_t1  NUMERIC;
    v_ve_du_kien_don_vi_t2  NUMERIC;
    v_ve_du_kien_don_vi_t3  NUMERIC;
    v_tong_di_duong  NUMERIC;
    v_tong_di_duong_don_vi  NUMERIC;
    v_ton_cuoi_t0    NUMERIC;
    v_ton_cuoi_t1    NUMERIC;
    v_ton_cuoi_t2    NUMERIC;
    v_ton_cuoi_t3    NUMERIC;
    v_du_phong       NUMERIC;
    v_thieu          NUMERIC;
    v_period_month   TEXT;
    v_month_t0       TEXT;
    v_month_t1       TEXT;
    v_month_t2       TEXT;
    v_month_t3       TEXT;
BEGIN
    DELETE FROM tong_hop_vat_tu WHERE period_id = p_period_id;

    SELECT period_month INTO v_period_month FROM ke_hoach_vat_tu WHERE id = p_period_id;
    v_month_t0 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY'), 'MM/YYYY');
    v_month_t1 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY') + INTERVAL '1 month', 'MM/YYYY');
    v_month_t2 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY') + INTERVAL '2 month', 'MM/YYYY');
    v_month_t3 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY') + INTERVAL '3 month', 'MM/YYYY');

    -- Buoc 1: Pre-load ton kho SAP
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

    -- Buoc 2: Pre-load vat tu di duong (BCU = tinh toan, don_vi = doi chieu)
    CREATE TEMP TABLE _tmp_vdd_bcu ON COMMIT DROP AS
    SELECT
        b3.company_id,
        b3.ma_vat_tu AS ma_nvl,
        SUM(CASE WHEN vdd.month_key = v_month_t0 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t0,
        SUM(CASE WHEN vdd.month_key = v_month_t1 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t1,
        SUM(CASE WHEN vdd.month_key = v_month_t2 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t2,
        SUM(CASE WHEN vdd.month_key = v_month_t3 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t3,
        SUM(COALESCE(vdd.so_luong, 0)) AS qty_total
    FROM (
        SELECT DISTINCT company_id, ma_vat_tu FROM tinh_toan_vat_tu WHERE period_id = p_period_id
    ) b3
    LEFT JOIN vat_tu_di_duong vdd
        ON  vdd.company_id = b3.company_id
        AND vdd.ma_nvl = b3.ma_vat_tu
        AND vdd.nguon = 'bcu'
    GROUP BY
        b3.company_id,
        b3.ma_vat_tu;

    CREATE TEMP TABLE _tmp_vdd_don_vi ON COMMIT DROP AS
    SELECT
        b3.company_id,
        b3.ma_vat_tu AS ma_nvl,
        SUM(CASE WHEN vdd.month_key = v_month_t0 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t0,
        SUM(CASE WHEN vdd.month_key = v_month_t1 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t1,
        SUM(CASE WHEN vdd.month_key = v_month_t2 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t2,
        SUM(CASE WHEN vdd.month_key = v_month_t3 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t3,
        SUM(COALESCE(vdd.so_luong, 0)) AS qty_total
    FROM (
        SELECT DISTINCT company_id, ma_vat_tu FROM tinh_toan_vat_tu WHERE period_id = p_period_id
    ) b3
    LEFT JOIN vat_tu_di_duong vdd
        ON  vdd.company_id = b3.company_id
        AND vdd.ma_nvl = b3.ma_vat_tu
        AND vdd.nguon = 'don_vi'
    GROUP BY
        b3.company_id,
        b3.ma_vat_tu;

    CREATE INDEX ON _tmp_vdd_bcu (company_id, ma_nvl);
    CREATE INDEX ON _tmp_vdd_don_vi (company_id, ma_nvl);

    -- Buoc 3: Vong lap tung vat tu
    FOR rec IN
        SELECT
            b3.company_id,
            c.company_code,
            b3.ma_vat_tu AS material_code,
            b3.ten_vat_tu AS material_name,
            mh.don_vi_tinh_id                  AS don_vi_tinh,
            SUM(COALESCE(b3.qty_t0, 0)) AS qty_t0,
            SUM(COALESCE(b3.qty_t1, 0)) AS qty_t1,
            SUM(COALESCE(b3.qty_t2, 0)) AS qty_t2,
            SUM(COALESCE(b3.qty_t3, 0)) AS qty_t3
        FROM tinh_toan_vat_tu b3
        JOIN res_company c ON c.id = b3.company_id
        LEFT JOIN ma_hang mh ON mh.ma_sap = b3.ma_vat_tu
        WHERE b3.period_id = p_period_id
        GROUP BY b3.company_id, c.company_code,
                 b3.ma_vat_tu, b3.ten_vat_tu, mh.don_vi_tinh_id
    LOOP
        v_comp_grp  := CASE 
                           WHEN rec.company_code LIKE '21%' OR rec.company_code = 'BNH' THEN 'BNH'
                           WHEN rec.company_code LIKE '22%' OR rec.company_code = 'SSP' THEN 'SSP'
                           ELSE 'ALL'
                       END;
        v_cache_key := rec.company_id::TEXT || '_' || rec.material_code;
        
        -- Ton dau: lay tu cache hoac tu SAP
        v_ton_dau := 0;
        IF v_ton_cuoi_cache ? v_cache_key THEN
            v_ton_dau := (v_ton_cuoi_cache ->> v_cache_key)::NUMERIC;
        ELSE
            SELECT COALESCE(tcu, 0) INTO v_ton_dau
            FROM _tmp_ton_kho
            WHERE ma_hang = rec.material_code AND comp_grp = v_comp_grp;
            v_ton_dau := COALESCE(v_ton_dau, 0);
        END IF;

        -- Hang di duong BCU (dung tinh ton cuoi / B5)
        v_ve_du_kien_t0 := 0; v_ve_du_kien_t1 := 0; v_ve_du_kien_t2 := 0; v_ve_du_kien_t3 := 0;
        v_ve_du_kien_don_vi_t0 := 0; v_ve_du_kien_don_vi_t1 := 0; v_ve_du_kien_don_vi_t2 := 0; v_ve_du_kien_don_vi_t3 := 0;
        v_tong_di_duong := 0;
        IF NOT (v_seen_cache ? v_cache_key) THEN
            SELECT
                COALESCE(qty_t0, 0), COALESCE(qty_t1, 0), COALESCE(qty_t2, 0), COALESCE(qty_t3, 0), COALESCE(qty_total, 0)
            INTO
                v_ve_du_kien_t0, v_ve_du_kien_t1, v_ve_du_kien_t2, v_ve_du_kien_t3, v_tong_di_duong
            FROM _tmp_vdd_bcu
            WHERE company_id = rec.company_id AND ma_nvl = rec.material_code;

            v_ve_du_kien_t0 := COALESCE(v_ve_du_kien_t0, 0);
            v_ve_du_kien_t1 := COALESCE(v_ve_du_kien_t1, 0);
            v_ve_du_kien_t2 := COALESCE(v_ve_du_kien_t2, 0);
            v_ve_du_kien_t3 := COALESCE(v_ve_du_kien_t3, 0);
            v_tong_di_duong := COALESCE(v_tong_di_duong, 0);

            IF v_tong_di_duong > (v_ve_du_kien_t0 + v_ve_du_kien_t1 + v_ve_du_kien_t2 + v_ve_du_kien_t3) THEN
                v_ve_du_kien_t0 := v_ve_du_kien_t0 + (v_tong_di_duong - (v_ve_du_kien_t0 + v_ve_du_kien_t1 + v_ve_du_kien_t2 + v_ve_du_kien_t3));
            END IF;

            SELECT
                COALESCE(qty_t0, 0), COALESCE(qty_t1, 0), COALESCE(qty_t2, 0), COALESCE(qty_t3, 0), COALESCE(qty_total, 0)
            INTO
                v_ve_du_kien_don_vi_t0, v_ve_du_kien_don_vi_t1, v_ve_du_kien_don_vi_t2, v_ve_du_kien_don_vi_t3, v_tong_di_duong_don_vi
            FROM _tmp_vdd_don_vi
            WHERE company_id = rec.company_id AND ma_nvl = rec.material_code;

            v_ve_du_kien_don_vi_t0 := COALESCE(v_ve_du_kien_don_vi_t0, 0);
            v_ve_du_kien_don_vi_t1 := COALESCE(v_ve_du_kien_don_vi_t1, 0);
            v_ve_du_kien_don_vi_t2 := COALESCE(v_ve_du_kien_don_vi_t2, 0);
            v_ve_du_kien_don_vi_t3 := COALESCE(v_ve_du_kien_don_vi_t3, 0);
            v_tong_di_duong_don_vi := COALESCE(v_tong_di_duong_don_vi, 0);

            IF v_tong_di_duong_don_vi > (v_ve_du_kien_don_vi_t0 + v_ve_du_kien_don_vi_t1 + v_ve_du_kien_don_vi_t2 + v_ve_du_kien_don_vi_t3) THEN
                v_ve_du_kien_don_vi_t0 := v_ve_du_kien_don_vi_t0 + (v_tong_di_duong_don_vi - (v_ve_du_kien_don_vi_t0 + v_ve_du_kien_don_vi_t1 + v_ve_du_kien_don_vi_t2 + v_ve_du_kien_don_vi_t3));
            END IF;

            v_seen_cache := jsonb_set(v_seen_cache, ARRAY[v_cache_key]::TEXT[], to_jsonb(TRUE));
        END IF;

        -- Tinh ton cuoi don luy ke (theo Excel):
        -- Ton cuoi T0 = Ton dau + Tong di duong - Can dung T0
        v_ton_cuoi_t0 := v_ton_dau + v_tong_di_duong - COALESCE(rec.qty_t0, 0);
        -- Ton cuoi T1 = Ton cuoi T0 - Can dung T1
        v_ton_cuoi_t1 := v_ton_cuoi_t0 - COALESCE(rec.qty_t1, 0);
        -- Ton cuoi T2 = Ton cuoi T1 - Can dung T2
        v_ton_cuoi_t2 := v_ton_cuoi_t1 - COALESCE(rec.qty_t2, 0);
        -- Ton cuoi T3 = Ton cuoi T2 - Can dung T3
        v_ton_cuoi_t3 := v_ton_cuoi_t2 - COALESCE(rec.qty_t3, 0);

        -- Du phong cuoi ky = Can dung T0 / 28 * so ngay du phong
        v_du_phong := CASE WHEN COALESCE(rec.qty_t0, 0) > 0 THEN rec.qty_t0 / 28.0 * p_ngay_dp ELSE 0 END;
        -- Thieu cuoi ky = Du phong - Ton cuoi T3 (neu am thi thieu)
        v_thieu := GREATEST(0.0, v_du_phong - v_ton_cuoi_t3);

        -- Cache ton cuoi cho lan tiep theo (khong cong v_thieu nua de giong Excel)
        v_ton_cuoi_cache := jsonb_set(
            v_ton_cuoi_cache,
            ARRAY[v_cache_key]::TEXT[],
            to_jsonb(v_ton_cuoi_t3)
        );

        INSERT INTO tong_hop_vat_tu (
            period_id, company_id, ma_dat_hang, ma_sap, ten_nvl, chung_loai, don_vi_tinh,
            ton_dau,
            ve_du_kien_don_vi_t0, ve_du_kien_don_vi_t1, ve_du_kien_don_vi_t2, ve_du_kien_don_vi_t3,
            ve_du_kien_t0, ve_du_kien_t1, ve_du_kien_t2, ve_du_kien_t3,
            vt_can_dung_t0, vt_can_dung_t1, vt_can_dung_t2, vt_can_dung_t3,
            ton_cuoi_t0, ton_cuoi_t1, ton_cuoi_t2, ton_cuoi_t3,
            so_luong_du_phong, so_luong_thieu, so_luong_can_mua,
            create_uid, write_uid, create_date, write_date
        ) VALUES (
            p_period_id, rec.company_id, NULL, rec.material_code, rec.material_name, NULL, rec.don_vi_tinh,
            v_ton_dau,
            v_ve_du_kien_don_vi_t0, v_ve_du_kien_don_vi_t1, v_ve_du_kien_don_vi_t2, v_ve_du_kien_don_vi_t3,
            v_ve_du_kien_t0, v_ve_du_kien_t1, v_ve_du_kien_t2, v_ve_du_kien_t3,
            rec.qty_t0, rec.qty_t1, rec.qty_t2, rec.qty_t3,
            v_ton_cuoi_t0, v_ton_cuoi_t1, v_ton_cuoi_t2, v_ton_cuoi_t3,
            v_du_phong, v_thieu, v_thieu,
            1, 1, NOW(), NOW()
        );
    END LOOP;

    DROP TABLE IF EXISTS _tmp_ton_kho;
    DROP TABLE IF EXISTS _tmp_vdd_bcu;
    DROP TABLE IF EXISTS _tmp_vdd_don_vi;
END;
$BODY$;

-- ============================================================
-- B5: Ke hoach dat vat tu tu B4 (cau truc moi)
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_ke_hoach_dat_vat_tu(
    p_period_id INTEGER,
    p_ngay_dt   NUMERIC DEFAULT 20.0
)
LANGUAGE 'plpgsql' AS $BODY$
BEGIN
    DELETE FROM kh_dat_vat_tu WHERE period_id = p_period_id;

    INSERT INTO kh_dat_vat_tu (
        period_id, company_id, ma_sap, ten_nvl, chung_loai, don_vi_tinh,
        tong_ton_nvl_sl,
        tong_sl_vt_can_dung_t0, tong_sl_vt_can_dung_t1, tong_sl_vt_can_dung_t2, tong_sl_vt_can_dung_t3,
        tong_vt_can_dung,
        tong_hang_di_duong_sl_t0, tong_hang_di_duong_sl_t1, tong_hang_di_duong_sl_t2, tong_hang_di_duong_sl_t3,
        tong_hang_di_duong,
        sl_du_tru_toi_thieu,
        sl_dat_mua_de_xuat,
        sl_dat_mua_chot,
        sl_ton_kho_cuoi_ky,
        so_ngay_vong_quay_ton,
        don_gia_ton_kho,
        don_gia_ton_kho_cuoi_ky,
        gia_tri_ton_kho_cuoi_ky,
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
    ),
    b4_data AS (
        SELECT
            b4.period_id, b4.company_id, b4.ma_sap, b4.ten_nvl, b4.chung_loai, b4.don_vi_tinh,
            b4.ton_dau,
            COALESCE(b4.vt_can_dung_t0, 0) AS cd_t0,
            COALESCE(b4.vt_can_dung_t1, 0) AS cd_t1,
            COALESCE(b4.vt_can_dung_t2, 0) AS cd_t2,
            COALESCE(b4.vt_can_dung_t3, 0) AS cd_t3,
            (COALESCE(b4.vt_can_dung_t0, 0) + COALESCE(b4.vt_can_dung_t1, 0) + 
             COALESCE(b4.vt_can_dung_t2, 0) + COALESCE(b4.vt_can_dung_t3, 0)) AS tcd,
            COALESCE(b4.ve_du_kien_t0, 0) AS dd_t0,
            COALESCE(b4.ve_du_kien_t1, 0) AS dd_t1,
            COALESCE(b4.ve_du_kien_t2, 0) AS dd_t2,
            COALESCE(b4.ve_du_kien_t3, 0) AS dd_t3,
            (COALESCE(b4.ve_du_kien_t0, 0) + COALESCE(b4.ve_du_kien_t1, 0) + 
             COALESCE(b4.ve_du_kien_t2, 0) + COALESCE(b4.ve_du_kien_t3, 0)) AS tdd,
            CASE
                WHEN COALESCE(tk.tdu, 0) != 0 THEN tk.ttdu / tk.tdu
                ELSE 0
            END AS don_gia_ton_kho
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
    )
    SELECT
        period_id, company_id, ma_sap, ten_nvl, chung_loai, don_vi_tinh,
        ton_dau,
        cd_t0, cd_t1, cd_t2, cd_t3,
        tcd,
        dd_t0, dd_t1, dd_t2, dd_t3,
        tdd,
        -- Du tru toi thieu = cd_t0 / 28 * p_ngay_dt
        CASE WHEN cd_t0 > 0 THEN (cd_t0 / 28.0) * p_ngay_dt ELSE 0.0 END AS sl_du_tru,
        -- De xuat
        (ton_dau - tcd + tdd - CASE WHEN cd_t0 > 0 THEN (cd_t0 / 28.0) * p_ngay_dt ELSE 0.0 END) AS sl_de_xuat,
        -- Chot
        CASE WHEN (ton_dau - tcd + tdd - CASE WHEN cd_t0 > 0 THEN (cd_t0 / 28.0) * p_ngay_dt ELSE 0.0 END) > 0 THEN 0.0 
             ELSE -(ton_dau - tcd + tdd - CASE WHEN cd_t0 > 0 THEN (cd_t0 / 28.0) * p_ngay_dt ELSE 0.0 END) 
        END AS sl_chot,
        -- Ton kho cuoi ky (neu chua co MOQ) = ton_dau - tcd + tdd
        (ton_dau - tcd + tdd) AS sl_ton_kho,
        -- Vong quay = Ton cuoi * 30 / (tcd / 4.0)
        CASE WHEN tcd > 0 THEN ((ton_dau - tcd + tdd) * 30.0) / (tcd / 4.0) ELSE 0.0 END AS so_ngay_vq,
        don_gia_ton_kho,
        don_gia_ton_kho,
        -- Gia tri ton = Ton cuoi * don gia
        (ton_dau - tcd + tdd) * don_gia_ton_kho AS gia_tri_ton,
        1, 1, NOW(), NOW()
    FROM b4_data;
END;
$BODY$;

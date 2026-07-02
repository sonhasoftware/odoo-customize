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
-- B4 bulk sync flat table (goi tu fn_tong_hop_vat_tu, thay trigger row-by-row)
-- ============================================================
CREATE OR REPLACE FUNCTION public.dlthvt_bulk_sync_b4_period(p_period_id INTEGER)
RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_period_month TEXT;
    v_period_code  TEXT;
    v_owner_company_id INTEGER;
BEGIN
    SELECT code, period_month, company_id
      INTO v_period_code, v_period_month, v_owner_company_id
      FROM ke_hoach_vat_tu
     WHERE id = p_period_id;

    PERFORM set_config('app.dlthvt_bulk', '1', true);

    INSERT INTO du_lieu_tong_hop_vat_tu (
        step_code, source_model, source_res_id, period_id,
        period_code, period_month, owner_company_id,
        company_id, company_code, period_company_id, period_company_code,
        month_key, month_date, ma_sap, ma_nvl,
        ten_nvl, ten_vat_tu, don_vi_tinh, ma_dat_hang, chung_loai,
        ton_dau, ve_du_kien_don_vi, ve_du_kien, vt_can_dung, ton_cuoi,
        so_luong_du_phong, so_luong_thieu, so_luong_can_mua,
        ghi_chu,
        create_uid, create_date, write_uid, write_date
    )
    SELECT
        'b4',
        'tong.hop.vat.tu',
        th.id,
        th.period_id,
        v_period_code,
        v_period_month,
        v_owner_company_id,
        th.company_id,
        rc_sx.company_code,
        th.don_vi_kd_id,
        rc_kd.company_code,
        TO_CHAR(
            (TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE,
            'MM/YYYY'
        ),
        (TO_DATE(v_period_month, 'MM/YYYY') + (m.i || ' month')::INTERVAL)::DATE,
        th.ma_sap,
        th.ma_sap,
        th.ten_nvl,
        th.ten_nvl,
        th.don_vi_tinh,
        th.ma_dat_hang,
        th.chung_loai,
        th.ton_dau,
        CASE m.i
            WHEN 0 THEN th.ve_du_kien_don_vi_t0
            WHEN 1 THEN th.ve_du_kien_don_vi_t1
            WHEN 2 THEN th.ve_du_kien_don_vi_t2
            WHEN 3 THEN th.ve_du_kien_don_vi_t3
        END,
        CASE m.i
            WHEN 0 THEN th.ve_du_kien_t0
            WHEN 1 THEN th.ve_du_kien_t1
            WHEN 2 THEN th.ve_du_kien_t2
            WHEN 3 THEN th.ve_du_kien_t3
        END,
        CASE m.i
            WHEN 0 THEN th.vt_can_dung_t0
            WHEN 1 THEN th.vt_can_dung_t1
            WHEN 2 THEN th.vt_can_dung_t2
            WHEN 3 THEN th.vt_can_dung_t3
        END,
        CASE m.i
            WHEN 0 THEN th.ton_cuoi_t0
            WHEN 1 THEN th.ton_cuoi_t1
            WHEN 2 THEN th.ton_cuoi_t2
            WHEN 3 THEN th.ton_cuoi_t3
        END,
        CASE WHEN m.i = 3 THEN th.so_luong_du_phong ELSE 0 END,
        CASE WHEN m.i = 3 THEN th.so_luong_thieu ELSE 0 END,
        CASE WHEN m.i = 3 THEN th.so_luong_can_mua ELSE 0 END,
        th.ghi_chu,
        th.create_uid,
        th.create_date,
        th.write_uid,
        th.write_date
    FROM tong_hop_vat_tu th
    CROSS JOIN generate_series(0, 3) AS m(i)
    LEFT JOIN res_company rc_sx ON rc_sx.id = th.company_id
    LEFT JOIN res_company rc_kd ON rc_kd.id = th.don_vi_kd_id
    WHERE th.period_id = p_period_id
    ON CONFLICT (source_model, source_res_id, month_key) DO UPDATE SET
        step_code = EXCLUDED.step_code,
        period_id = EXCLUDED.period_id,
        period_code = EXCLUDED.period_code,
        period_month = EXCLUDED.period_month,
        owner_company_id = EXCLUDED.owner_company_id,
        company_id = EXCLUDED.company_id,
        company_code = EXCLUDED.company_code,
        period_company_id = EXCLUDED.period_company_id,
        period_company_code = EXCLUDED.period_company_code,
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
END;
$$;

-- ============================================================
-- B4: Tong hop vat tu - Tinh don luy ke theo Excel (set-based)
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_tong_hop_vat_tu(
    p_period_id INTEGER,
    p_ngay_dp   NUMERIC DEFAULT 15.0
)
LANGUAGE 'plpgsql' AS $BODY$
DECLARE
    v_period_month TEXT;
    v_month_t0     TEXT;
    v_month_t1     TEXT;
    v_month_t2     TEXT;
    v_month_t3     TEXT;
BEGIN
    SELECT period_month INTO v_period_month FROM ke_hoach_vat_tu WHERE id = p_period_id;
    v_month_t0 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY'), 'MM/YYYY');
    v_month_t1 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY') + INTERVAL '1 month', 'MM/YYYY');
    v_month_t2 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY') + INTERVAL '2 month', 'MM/YYYY');
    v_month_t3 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY') + INTERVAL '3 month', 'MM/YYYY');

    -- Xoa flat B4 theo kỳ (1 lan) thay vi trigger DELETE tung dong
    DELETE FROM du_lieu_tong_hop_vat_tu
     WHERE step_code = 'b4' AND period_id = p_period_id;

    ALTER TABLE tong_hop_vat_tu DISABLE TRIGGER trg_dlthvt_b4;
    BEGIN
        DELETE FROM tong_hop_vat_tu WHERE period_id = p_period_id;

        CREATE TEMP TABLE _tmp_period_nvl ON COMMIT DROP AS
    SELECT DISTINCT ma_vat_tu
    FROM tinh_toan_vat_tu
    WHERE period_id = p_period_id;

    CREATE INDEX ON _tmp_period_nvl (ma_vat_tu);

    -- Ton kho SAP: chi ma NVL cua ky (khong quet full bang)
    CREATE TEMP TABLE _tmp_ton_kho ON COMMIT DROP AS
    WITH latest AS (
        SELECT DISTINCT ON (TRIM(mtk.ma_hang), mtk.chi_nhanh)
            TRIM(mtk.ma_hang)                   AS ma_hang,
            mtk.chi_nhanh,
            safe_sap_numeric(mtk.ton_cuoi)        AS ton_cuoi,
            safe_sap_numeric(mtk.tien_ton_cuoi)   AS tien_ton_cuoi,
            safe_sap_numeric(mtk.ton_dau)         AS ton_dau,
            safe_sap_numeric(mtk.tien_ton_dau)    AS tien_ton_dau
        FROM md_sap_ton_kho mtk
        WHERE EXISTS (
            SELECT 1 FROM _tmp_period_nvl n WHERE n.ma_vat_tu = TRIM(mtk.ma_hang)
        )
        ORDER BY TRIM(mtk.ma_hang), mtk.chi_nhanh, mtk.create_date DESC, mtk.id DESC
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
    GROUP BY b3.company_id, b3.ma_vat_tu;

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
    GROUP BY b3.company_id, b3.ma_vat_tu;

    CREATE INDEX ON _tmp_vdd_bcu (company_id, ma_nvl);
    CREATE INDEX ON _tmp_vdd_don_vi (company_id, ma_nvl);

    -- Dong gop B4 (don_vi_kd_id NULL): ton / di duong / can doi
    INSERT INTO tong_hop_vat_tu (
        period_id, company_id, don_vi_kd_id, ma_dat_hang, ma_sap, ten_nvl, chung_loai, don_vi_tinh,
        ton_dau,
        ve_du_kien_don_vi_t0, ve_du_kien_don_vi_t1, ve_du_kien_don_vi_t2, ve_du_kien_don_vi_t3,
        ve_du_kien_t0, ve_du_kien_t1, ve_du_kien_t2, ve_du_kien_t3,
        vt_can_dung_t0, vt_can_dung_t1, vt_can_dung_t2, vt_can_dung_t3,
        ton_cuoi_t0, ton_cuoi_t1, ton_cuoi_t2, ton_cuoi_t3,
        so_luong_du_phong, so_luong_thieu, so_luong_can_mua,
        create_uid, write_uid, create_date, write_date
    )
    SELECT
        p_period_id,
        agg.company_id,
        NULL,
        NULL,
        agg.material_code,
        agg.material_name,
        NULL,
        agg.don_vi_tinh,
        agg.ton_dau,
        agg.ve_du_kien_don_vi_t0,
        agg.ve_du_kien_don_vi_t1,
        agg.ve_du_kien_don_vi_t2,
        agg.ve_du_kien_don_vi_t3,
        agg.ve_du_kien_t0,
        agg.ve_du_kien_t1,
        agg.ve_du_kien_t2,
        agg.ve_du_kien_t3,
        agg.qty_t0,
        agg.qty_t1,
        agg.qty_t2,
        agg.qty_t3,
        agg.ton_cuoi_t0,
        agg.ton_cuoi_t1,
        agg.ton_cuoi_t2,
        agg.ton_cuoi_t3,
        agg.so_luong_du_phong,
        agg.so_luong_thieu,
        agg.so_luong_thieu,
        1, 1, NOW(), NOW()
    FROM (
        SELECT
            b3.company_id,
            b3.ma_vat_tu                                              AS material_code,
            b3.ten_vat_tu                                             AS material_name,
            mh.don_vi_tinh_id                                         AS don_vi_tinh,
            SUM(COALESCE(b3.qty_t0, 0))                               AS qty_t0,
            SUM(COALESCE(b3.qty_t1, 0))                               AS qty_t1,
            SUM(COALESCE(b3.qty_t2, 0))                               AS qty_t2,
            SUM(COALESCE(b3.qty_t3, 0))                               AS qty_t3,
            COALESCE(tk.tcu, 0)                                       AS ton_dau,
            COALESCE(vdd_dv.qty_t0_adj, 0)                            AS ve_du_kien_don_vi_t0,
            COALESCE(vdd_dv.qty_t1, 0)                                AS ve_du_kien_don_vi_t1,
            COALESCE(vdd_dv.qty_t2, 0)                                AS ve_du_kien_don_vi_t2,
            COALESCE(vdd_dv.qty_t3, 0)                                AS ve_du_kien_don_vi_t3,
            COALESCE(vdd.qty_t0_adj, 0)                               AS ve_du_kien_t0,
            COALESCE(vdd.qty_t1, 0)                                   AS ve_du_kien_t1,
            COALESCE(vdd.qty_t2, 0)                                   AS ve_du_kien_t2,
            COALESCE(vdd.qty_t3, 0)                                   AS ve_du_kien_t3,
            COALESCE(vdd.qty_total, 0)                                AS tong_di_duong,
            COALESCE(tk.tcu, 0) + COALESCE(vdd.qty_total, 0)
                - SUM(COALESCE(b3.qty_t0, 0))                         AS ton_cuoi_t0,
            COALESCE(tk.tcu, 0) + COALESCE(vdd.qty_total, 0)
                - SUM(COALESCE(b3.qty_t0, 0))
                - SUM(COALESCE(b3.qty_t1, 0))                         AS ton_cuoi_t1,
            COALESCE(tk.tcu, 0) + COALESCE(vdd.qty_total, 0)
                - SUM(COALESCE(b3.qty_t0, 0))
                - SUM(COALESCE(b3.qty_t1, 0))
                - SUM(COALESCE(b3.qty_t2, 0))                         AS ton_cuoi_t2,
            COALESCE(tk.tcu, 0) + COALESCE(vdd.qty_total, 0)
                - SUM(COALESCE(b3.qty_t0, 0))
                - SUM(COALESCE(b3.qty_t1, 0))
                - SUM(COALESCE(b3.qty_t2, 0))
                - SUM(COALESCE(b3.qty_t3, 0))                         AS ton_cuoi_t3,
            CASE
                WHEN SUM(COALESCE(b3.qty_t0, 0)) > 0
                THEN SUM(COALESCE(b3.qty_t0, 0)) / 28.0 * p_ngay_dp
                ELSE 0
            END                                                       AS so_luong_du_phong,
            GREATEST(
                0.0,
                CASE
                    WHEN SUM(COALESCE(b3.qty_t0, 0)) > 0
                    THEN SUM(COALESCE(b3.qty_t0, 0)) / 28.0 * p_ngay_dp
                    ELSE 0
                END
                - (
                    COALESCE(tk.tcu, 0) + COALESCE(vdd.qty_total, 0)
                    - SUM(COALESCE(b3.qty_t0, 0))
                    - SUM(COALESCE(b3.qty_t1, 0))
                    - SUM(COALESCE(b3.qty_t2, 0))
                    - SUM(COALESCE(b3.qty_t3, 0))
                )
            )                                                         AS so_luong_thieu
        FROM tinh_toan_vat_tu b3
        JOIN res_company c ON c.id = b3.company_id
        LEFT JOIN ma_hang mh ON mh.ma_sap = b3.ma_vat_tu
        LEFT JOIN _tmp_ton_kho tk
            ON  tk.ma_hang = b3.ma_vat_tu
            AND tk.comp_grp = CASE
                WHEN c.company_code LIKE '21%' OR c.company_code = 'BNH' THEN 'BNH'
                WHEN c.company_code LIKE '22%' OR c.company_code = 'SSP' THEN 'SSP'
                ELSE 'ALL'
            END
        LEFT JOIN LATERAL (
            SELECT
                CASE
                    WHEN COALESCE(v.qty_total, 0) > (
                        COALESCE(v.qty_t0, 0) + COALESCE(v.qty_t1, 0)
                        + COALESCE(v.qty_t2, 0) + COALESCE(v.qty_t3, 0)
                    )
                    THEN COALESCE(v.qty_t0, 0) + COALESCE(v.qty_total, 0) - (
                        COALESCE(v.qty_t0, 0) + COALESCE(v.qty_t1, 0)
                        + COALESCE(v.qty_t2, 0) + COALESCE(v.qty_t3, 0)
                    )
                    ELSE COALESCE(v.qty_t0, 0)
                END AS qty_t0_adj,
                COALESCE(v.qty_t1, 0) AS qty_t1,
                COALESCE(v.qty_t2, 0) AS qty_t2,
                COALESCE(v.qty_t3, 0) AS qty_t3,
                COALESCE(v.qty_total, 0) AS qty_total
            FROM _tmp_vdd_bcu v
            WHERE v.company_id = b3.company_id AND v.ma_nvl = b3.ma_vat_tu
        ) vdd ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                CASE
                    WHEN COALESCE(v.qty_total, 0) > (
                        COALESCE(v.qty_t0, 0) + COALESCE(v.qty_t1, 0)
                        + COALESCE(v.qty_t2, 0) + COALESCE(v.qty_t3, 0)
                    )
                    THEN COALESCE(v.qty_t0, 0) + COALESCE(v.qty_total, 0) - (
                        COALESCE(v.qty_t0, 0) + COALESCE(v.qty_t1, 0)
                        + COALESCE(v.qty_t2, 0) + COALESCE(v.qty_t3, 0)
                    )
                    ELSE COALESCE(v.qty_t0, 0)
                END AS qty_t0_adj,
                COALESCE(v.qty_t1, 0) AS qty_t1,
                COALESCE(v.qty_t2, 0) AS qty_t2,
                COALESCE(v.qty_t3, 0) AS qty_t3
            FROM _tmp_vdd_don_vi v
            WHERE v.company_id = b3.company_id AND v.ma_nvl = b3.ma_vat_tu
        ) vdd_dv ON TRUE
        WHERE b3.period_id = p_period_id
        GROUP BY
            b3.company_id, c.company_code,
            b3.ma_vat_tu, b3.ten_vat_tu, mh.don_vi_tinh_id,
            tk.tcu, vdd.qty_t0_adj, vdd.qty_t1, vdd.qty_t2, vdd.qty_t3, vdd.qty_total,
            vdd_dv.qty_t0_adj, vdd_dv.qty_t1, vdd_dv.qty_t2, vdd_dv.qty_t3
    ) agg;

    -- Chi tiet B4 theo don vi dat hang (KD): chi vt_can_dung, phuc vu bao cao
    INSERT INTO tong_hop_vat_tu (
        period_id, company_id, don_vi_kd_id, ma_dat_hang, ma_sap, ten_nvl, chung_loai, don_vi_tinh,
        ton_dau,
        ve_du_kien_don_vi_t0, ve_du_kien_don_vi_t1, ve_du_kien_don_vi_t2, ve_du_kien_don_vi_t3,
        ve_du_kien_t0, ve_du_kien_t1, ve_du_kien_t2, ve_du_kien_t3,
        vt_can_dung_t0, vt_can_dung_t1, vt_can_dung_t2, vt_can_dung_t3,
        ton_cuoi_t0, ton_cuoi_t1, ton_cuoi_t2, ton_cuoi_t3,
        so_luong_du_phong, so_luong_thieu, so_luong_can_mua,
        create_uid, write_uid, create_date, write_date
    )
    SELECT
        p_period_id,
        b3.company_id,
        b3.don_vi_kd_id,
        NULL,
        b3.ma_vat_tu,
        b3.ten_vat_tu,
        NULL,
        mh.don_vi_tinh_id,
        0,
        0, 0, 0, 0,
        0, 0, 0, 0,
        SUM(COALESCE(b3.qty_t0, 0)),
        SUM(COALESCE(b3.qty_t1, 0)),
        SUM(COALESCE(b3.qty_t2, 0)),
        SUM(COALESCE(b3.qty_t3, 0)),
        0, 0, 0, 0,
        0, 0, 0,
        1, 1, NOW(), NOW()
    FROM tinh_toan_vat_tu b3
    LEFT JOIN ma_hang mh ON mh.ma_sap = b3.ma_vat_tu
    WHERE b3.period_id = p_period_id
      AND b3.don_vi_kd_id IS NOT NULL
    GROUP BY
        b3.company_id, b3.don_vi_kd_id,
        b3.ma_vat_tu, b3.ten_vat_tu, mh.don_vi_tinh_id;

        PERFORM dlthvt_bulk_sync_b4_period(p_period_id);
    EXCEPTION
        WHEN OTHERS THEN
            ALTER TABLE tong_hop_vat_tu ENABLE TRIGGER trg_dlthvt_b4;
            RAISE;
    END;
    ALTER TABLE tong_hop_vat_tu ENABLE TRIGGER trg_dlthvt_b4;
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
          AND b4.don_vi_kd_id IS NULL
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


CREATE OR REPLACE FUNCTION public.fn_md_sap_ton_kho_month_key(
    p_from_date   TEXT,
    p_to_date     TEXT,
    p_tu_ngay     TEXT,
    p_den_ngay    TEXT,
    p_create_date TIMESTAMP
) RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_raw TEXT;
    v_dt  DATE;
BEGIN
    FOREACH v_raw IN ARRAY ARRAY[
        NULLIF(TRIM(p_from_date), ''),
        NULLIF(TRIM(p_to_date), ''),
        NULLIF(TRIM(p_tu_ngay), ''),
        NULLIF(TRIM(p_den_ngay), '')
    ] LOOP
        IF v_raw IS NULL THEN
            CONTINUE;
        END IF;
        BEGIN
            IF v_raw ~ '^\d{8}$' THEN
                v_dt := TO_DATE(v_raw, 'YYYYMMDD');
            ELSIF v_raw ~ '^\d{2}\.\d{2}\.\d{4}$' THEN
                v_dt := TO_DATE(v_raw, 'DD.MM.YYYY');
            ELSIF v_raw ~ '^\d{4}-\d{2}-\d{2}' THEN
                v_dt := LEFT(v_raw, 10)::date;
            ELSE
                CONTINUE;
            END IF;
            RETURN TO_CHAR(v_dt, 'MM/YYYY');
        EXCEPTION WHEN OTHERS THEN
            CONTINUE;
        END;
    END LOOP;
    RETURN TO_CHAR(date_trunc('month', COALESCE(p_create_date, NOW()))::date, 'MM/YYYY');
END;
$$;

-- ============================================================
-- B2: Sinh dinh muc tu bom_tinh_toan
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_sinh_dinh_muc(p_period_id INTEGER)
LANGUAGE 'plpgsql' AS $BODY$
BEGIN
    ALTER TABLE dinh_muc DISABLE TRIGGER trg_dlthvt_b2;
    BEGIN
        DELETE FROM dinh_muc WHERE period_id = p_period_id;

        -- Lookup bom_sale_id theo ma_nvl: quét MDM 1 lần, tránh LATERAL N×/dòng BOM.
        CREATE TEMP TABLE _tmp_mdm_bom_sale ON COMMIT DROP AS
        SELECT DISTINCT ON (TRIM(l.ma_dv))
            TRIM(l.ma_dv) AS ma_nvl,
            l.bom_sale      AS bom_sale_id
        FROM mdm_tong_hop_line l
        WHERE l.ma_dv IS NOT NULL
          AND TRIM(l.ma_dv) <> ''
        ORDER BY TRIM(l.ma_dv), l.id;

        CREATE INDEX ON _tmp_mdm_bom_sale (ma_nvl);

        INSERT INTO dinh_muc (
        period_id, company_id, ma_sap, ten_sap, ma_tp, ten_tp, ma_nvl, ten_nvl, sl_dinh_muc, bom_sale_id,
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
        COALESCE(bcu.sl_thuc_te, 0),
        mdm_bs.bom_sale_id,
        COALESCE(b1.qty_kd_t0, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_kd_t1, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_kd_t2, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_kd_t3, 0) * bcu.sl_thuc_te,
        COALESCE(b1.qty_sx_t0, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_sx_t1, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_sx_t2, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_sx_t3, 0) * bcu.sl_thuc_te,
        COALESCE(b1.qty_cl_t0, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_cl_t1, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_cl_t2, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_cl_t3, 0) * bcu.sl_thuc_te,
        COALESCE(b1.qty_t0, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_t1, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_t2, 0) * bcu.sl_thuc_te, COALESCE(b1.qty_t3, 0) * bcu.sl_thuc_te,
        1, 1, NOW(), NOW()
    FROM ke_hoach_vat_tu_line b1
    JOIN bom_tinh_toan bcu
        ON bcu.ma_tp_goc = b1.ma_sap
       AND bcu.loai_vat_tu = 'NVL'
    LEFT JOIN _tmp_mdm_bom_sale mdm_bs
        ON mdm_bs.ma_nvl = TRIM(bcu.ma_con)
    WHERE b1.period_id = p_period_id;

        PERFORM dlthvt_bulk_sync_b2_period(p_period_id);
    EXCEPTION
        WHEN OTHERS THEN
            ALTER TABLE dinh_muc ENABLE TRIGGER trg_dlthvt_b2;
            RAISE;
    END;
    ALTER TABLE dinh_muc ENABLE TRIGGER trg_dlthvt_b2;
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

    ALTER TABLE tinh_toan_vat_tu DISABLE TRIGGER trg_dlthvt_b3;
    BEGIN
        DELETE FROM tinh_toan_vat_tu WHERE period_id = p_period_id;

        INSERT INTO tinh_toan_vat_tu (
        period_id, company_id, don_vi_kd_id, don_vi_kd_code, ma_vat_tu, ten_vat_tu,
        don_vi_tinh, do_day, kho_1, kho_2, trong_luong_kg_tam,
        qty_t0, qty_t1, qty_t2, qty_t3,
        create_uid, write_uid, create_date, write_date
    )
    SELECT
        agg.period_id,
        v_prod_company_id,
        agg.don_vi_kd_id,
        COALESCE(NULLIF(TRIM(dv.company_code), ''), dv.name)     AS don_vi_kd_code,
        agg.ma_vat_tu,
        COALESCE(agg.ten_vat_tu_rep, agg.ma_vat_tu)                AS ten_vat_tu,
        mdm.dvt                                                  AS don_vi_tinh,
        0::NUMERIC, 0::NUMERIC, 0::NUMERIC, 0::NUMERIC,
        agg.qty_t0, agg.qty_t1, agg.qty_t2, agg.qty_t3,
        1, 1, NOW(), NOW()
    FROM (
        SELECT
            kd.period_id,
            kd.company_id                                            AS don_vi_kd_id,
            bcu.ma_con                                               AS ma_vat_tu,
            MIN(NULLIF(TRIM(bcu.ten_con), ''))                       AS ten_vat_tu_rep,
            SUM(COALESCE(kd.qty_t0, 0) * COALESCE(bcu.sl_thuc_te, 0)) AS qty_t0,
            SUM(COALESCE(kd.qty_t1, 0) * COALESCE(bcu.sl_thuc_te, 0)) AS qty_t1,
            SUM(COALESCE(kd.qty_t2, 0) * COALESCE(bcu.sl_thuc_te, 0)) AS qty_t2,
            SUM(COALESCE(kd.qty_t3, 0) * COALESCE(bcu.sl_thuc_te, 0)) AS qty_t3
        FROM ke_hoach_kinh_doanh kd
        JOIN bom_tinh_toan bcu
            ON bcu.ma_tp_goc = kd.ma_sap
           AND bcu.loai_vat_tu = 'NVL'
        -- INNER JOIN (
        --     SELECT DISTINCT TRIM(dm.ma_nvl) AS ma_nvl
        --     FROM dinh_muc dm
        --     INNER JOIN bom_sale bs ON bs.id = dm.bom_sale_id AND bs.ma = '1C'
        --     WHERE dm.period_id = p_period_id
        -- ) dm_nvl ON TRIM(dm_nvl.ma_nvl) = TRIM(bcu.ma_con)
        WHERE kd.period_id = p_period_id
          AND kd.ma_sap IS NOT NULL
          AND TRIM(kd.ma_sap) <> ''
          AND kd.company_id IS NOT NULL
        GROUP BY kd.period_id, kd.company_id, bcu.ma_con
    ) agg
    JOIN res_company dv ON dv.id = agg.don_vi_kd_id
    LEFT JOIN LATERAL (
        SELECT l.dvt
        FROM mdm_tong_hop_line l
        WHERE TRIM(l.ma_dv) = TRIM(agg.ma_vat_tu)
        ORDER BY l.id
        LIMIT 1
    ) mdm ON TRUE;

        PERFORM dlthvt_bulk_sync_b3_period(p_period_id);
    EXCEPTION
        WHEN OTHERS THEN
            ALTER TABLE tinh_toan_vat_tu ENABLE TRIGGER trg_dlthvt_b3;
            RAISE;
    END;
    ALTER TABLE tinh_toan_vat_tu ENABLE TRIGGER trg_dlthvt_b3;
END;
$BODY$;

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

    ALTER TABLE tong_hop_vat_tu DISABLE TRIGGER trg_dlthvt_b4;
    BEGIN
        -- Giu BCU da import truoc khi xoa tong_hop_vat_tu
        CREATE TEMP TABLE _tmp_vdd_bcu ON COMMIT DROP AS
        SELECT
            th.company_id,
            th.ma_sap AS ma_nvl,
            COALESCE(th.ve_du_kien_t0, 0) AS qty_t0,
            COALESCE(th.ve_du_kien_t1, 0) AS qty_t1,
            COALESCE(th.ve_du_kien_t2, 0) AS qty_t2,
            COALESCE(th.ve_du_kien_t3, 0) AS qty_t3,
            COALESCE(th.ve_du_kien_t0, 0) + COALESCE(th.ve_du_kien_t1, 0)
                + COALESCE(th.ve_du_kien_t2, 0) + COALESCE(th.ve_du_kien_t3, 0) AS qty_total
        FROM tong_hop_vat_tu th
        WHERE th.period_id = p_period_id
          AND th.don_vi_kd_id IS NULL;

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

    CREATE TEMP TABLE _tmp_vdd_don_vi ON COMMIT DROP AS
    SELECT
        b3.company_id,
        b3.ma_vat_tu AS ma_nvl,
        SUM(CASE WHEN vdd.month_key = v_month_t0 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t0,
        SUM(CASE WHEN vdd.month_key = v_month_t1 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t1,
        SUM(CASE WHEN vdd.month_key = v_month_t2 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t2,
        SUM(CASE WHEN vdd.month_key = v_month_t3 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t3,
        SUM(CASE WHEN vdd.month_key IN (v_month_t0, v_month_t1, v_month_t2, v_month_t3)
                 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_total
    FROM (
        SELECT DISTINCT company_id, don_vi_kd_id, ma_vat_tu
        FROM tinh_toan_vat_tu
        WHERE period_id = p_period_id
          AND don_vi_kd_id IS NOT NULL
    ) b3
    LEFT JOIN vat_tu_di_duong vdd
        ON  vdd.company_id = b3.don_vi_kd_id
        AND vdd.ma_nvl = b3.ma_vat_tu
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
            MAX(b3.don_vi_tinh)                                       AS don_vi_tinh,
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
            COALESCE(vdd_dv.qty_total, 0)                            AS tong_di_duong,
            COALESCE(tk.tcu, 0) + COALESCE(vdd_dv.qty_total, 0)
                - SUM(COALESCE(b3.qty_t0, 0))                         AS ton_cuoi_t0,
            COALESCE(tk.tcu, 0) + COALESCE(vdd_dv.qty_total, 0)
                - SUM(COALESCE(b3.qty_t0, 0))
                - SUM(COALESCE(b3.qty_t1, 0))                         AS ton_cuoi_t1,
            COALESCE(tk.tcu, 0) + COALESCE(vdd_dv.qty_total, 0)
                - SUM(COALESCE(b3.qty_t0, 0))
                - SUM(COALESCE(b3.qty_t1, 0))
                - SUM(COALESCE(b3.qty_t2, 0))                         AS ton_cuoi_t2,
            COALESCE(tk.tcu, 0) + COALESCE(vdd_dv.qty_total, 0)
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
                    COALESCE(tk.tcu, 0) + COALESCE(vdd_dv.qty_total, 0)
                    - SUM(COALESCE(b3.qty_t0, 0))
                    - SUM(COALESCE(b3.qty_t1, 0))
                    - SUM(COALESCE(b3.qty_t2, 0))
                    - SUM(COALESCE(b3.qty_t3, 0))
                )
            )                                                         AS so_luong_thieu
        FROM tinh_toan_vat_tu b3
        JOIN res_company c ON c.id = b3.company_id
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
                COALESCE(v.qty_t3, 0) AS qty_t3,
                COALESCE(v.qty_total, 0) AS qty_total
            FROM _tmp_vdd_don_vi v
            WHERE v.company_id = b3.company_id AND v.ma_nvl = b3.ma_vat_tu
        ) vdd_dv ON TRUE
        WHERE b3.period_id = p_period_id
        GROUP BY
            b3.company_id, c.company_code,
            b3.ma_vat_tu, b3.ten_vat_tu,
            tk.tcu, vdd.qty_t0_adj, vdd.qty_t1, vdd.qty_t2, vdd.qty_t3, vdd.qty_total,
            vdd_dv.qty_t0_adj, vdd_dv.qty_t1, vdd_dv.qty_t2, vdd_dv.qty_t3, vdd_dv.qty_total
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
        MAX(b3.don_vi_tinh),
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
    WHERE b3.period_id = p_period_id
      AND b3.don_vi_kd_id IS NOT NULL
    GROUP BY
        b3.company_id, b3.don_vi_kd_id,
        b3.ma_vat_tu, b3.ten_vat_tu;

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
DECLARE
    v_month_price TEXT;
BEGIN
    SELECT TO_CHAR(TO_DATE(period_month, 'MM/YYYY') - INTERVAL '1 month', 'MM/YYYY')
      INTO v_month_price
      FROM ke_hoach_vat_tu
     WHERE id = p_period_id;

    ALTER TABLE kh_dat_vat_tu DISABLE TRIGGER trg_dlthvt_b5;
    BEGIN
        DELETE FROM kh_dat_vat_tu WHERE period_id = p_period_id;

        CREATE TEMP TABLE _tmp_period_nvl_b5 ON COMMIT DROP AS
        SELECT DISTINCT COALESCE(NULLIF(TRIM(ma_dat_hang), ''), TRIM(ma_sap)) AS ma_hang
          FROM tong_hop_vat_tu
         WHERE period_id = p_period_id
           AND don_vi_kd_id IS NULL;

        CREATE INDEX ON _tmp_period_nvl_b5 (ma_hang);

        CREATE TEMP TABLE _tmp_ton_kho_price ON COMMIT DROP AS
        WITH latest AS (
            SELECT DISTINCT ON (TRIM(mtk.ma_hang), mtk.chi_nhanh)
                TRIM(mtk.ma_hang) AS ma_hang,
                mtk.chi_nhanh,
                safe_sap_numeric(mtk.ton_dau) AS ton_dau,
                safe_sap_numeric(mtk.tien_ton_dau) AS tien_ton_dau
            FROM md_sap_ton_kho mtk
            WHERE EXISTS (
                SELECT 1 FROM _tmp_period_nvl_b5 n WHERE n.ma_hang = TRIM(mtk.ma_hang)
            )
              AND fn_md_sap_ton_kho_month_key(
                      mtk.from_date, mtk.to_date, mtk.tu_ngay, mtk.den_ngay, mtk.create_date
                  ) = v_month_price
              AND (
                  safe_sap_numeric(mtk.ton_dau) <> 0
                  OR safe_sap_numeric(mtk.tien_ton_dau) <> 0
              )
            ORDER BY TRIM(mtk.ma_hang), mtk.chi_nhanh, mtk.create_date DESC, mtk.id DESC
        )
        SELECT ma_hang, 'BNH' AS comp_grp,
               SUM(ton_dau) AS tdu, SUM(tien_ton_dau) AS ttdu
          FROM latest WHERE chi_nhanh LIKE '21%' GROUP BY ma_hang
        UNION ALL
        SELECT ma_hang, 'SSP', SUM(ton_dau), SUM(tien_ton_dau)
          FROM latest WHERE chi_nhanh LIKE '22%' GROUP BY ma_hang
        UNION ALL
        SELECT ma_hang, 'ALL', SUM(ton_dau), SUM(tien_ton_dau)
          FROM latest WHERE chi_nhanh NOT LIKE '10%' GROUP BY ma_hang;

        CREATE INDEX ON _tmp_ton_kho_price (ma_hang, comp_grp);

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
        sl_can_mua_theo_moq,
        sl_ton_kho_cuoi_ky,
        so_ngay_vong_quay_ton,
        don_gia_ton_kho,
        don_gia_ton_kho_cuoi_ky,
        gia_tri_ton_kho_cuoi_ky,
        create_uid, write_uid, create_date, write_date
        )
        WITH b4_data AS (
        SELECT
            b4.period_id, b4.company_id, b4.ma_sap, b4.ten_nvl, b4.chung_loai, b4.don_vi_tinh,
            b4.ton_dau,
            COALESCE(b4.vt_can_dung_t0, 0) AS cd_t0,
            COALESCE(b4.vt_can_dung_t1, 0) AS cd_t1,
            COALESCE(b4.vt_can_dung_t2, 0) AS cd_t2,
            COALESCE(b4.vt_can_dung_t3, 0) AS cd_t3,
            (COALESCE(b4.vt_can_dung_t0, 0) + COALESCE(b4.vt_can_dung_t1, 0) + 
             COALESCE(b4.vt_can_dung_t2, 0) + COALESCE(b4.vt_can_dung_t3, 0)) AS tcd,
            COALESCE(b4.ve_du_kien_don_vi_t0, 0) AS dd_t0,
            COALESCE(b4.ve_du_kien_don_vi_t1, 0) AS dd_t1,
            COALESCE(b4.ve_du_kien_don_vi_t2, 0) AS dd_t2,
            COALESCE(b4.ve_du_kien_don_vi_t3, 0) AS dd_t3,
            (COALESCE(b4.ve_du_kien_don_vi_t0, 0) + COALESCE(b4.ve_du_kien_don_vi_t1, 0) + 
             COALESCE(b4.ve_du_kien_don_vi_t2, 0) + COALESCE(b4.ve_du_kien_don_vi_t3, 0)) AS tdd,
            CASE
                WHEN COALESCE(tg.tdu, 0) != 0 THEN COALESCE(tg.ttdu, 0) / tg.tdu
                ELSE 0
            END AS don_gia_ton_kho,
            -- Gia tri tồn đầu = SL tồn (B4) x don gia thang n-1 (Excel R = K x Q)
            b4.ton_dau * CASE
                WHEN COALESCE(tg.tdu, 0) != 0 THEN COALESCE(tg.ttdu, 0) / tg.tdu
                ELSE 0
            END AS gia_tri_ton_dau
        FROM tong_hop_vat_tu b4
        JOIN res_company c ON c.id = b4.company_id
        LEFT JOIN _tmp_ton_kho_price tg
            ON  tg.ma_hang  = COALESCE(NULLIF(TRIM(b4.ma_dat_hang), ''), TRIM(b4.ma_sap))
            AND tg.comp_grp = CASE 
                                   WHEN c.company_code LIKE '21%' OR c.company_code = 'BNH' THEN 'BNH'
                                   WHEN c.company_code LIKE '22%' OR c.company_code = 'SSP' THEN 'SSP'
                                   ELSE 'ALL'
                               END
        WHERE b4.period_id = p_period_id
          AND b4.don_vi_kd_id IS NULL
    ),
    calc AS (
        SELECT
            b.*,
            CASE WHEN cd_t0 > 0 THEN (cd_t0 / 28.0) * p_ngay_dt ELSE 0.0 END AS sl_du_tru,
            0.0 AS sl_moq,
            (ton_dau - tcd + tdd + 0.0) AS sl_ton_kho,
            CASE
                WHEN (ton_dau + tdd + 0.0) > 0
                THEN gia_tri_ton_dau / (ton_dau + tdd + 0.0)
                ELSE 0.0
            END AS don_gia_cuoi
        FROM b4_data b
    )
    SELECT
        period_id, company_id, ma_sap, ten_nvl, chung_loai, don_vi_tinh,
        ton_dau,
        cd_t0, cd_t1, cd_t2, cd_t3,
        tcd,
        dd_t0, dd_t1, dd_t2, dd_t3,
        tdd,
        sl_du_tru,
        (ton_dau - tcd + tdd - sl_du_tru) AS sl_de_xuat,
        CASE WHEN (ton_dau - tcd + tdd - sl_du_tru) > 0 THEN 0.0
             ELSE -(ton_dau - tcd + tdd - sl_du_tru)
        END AS sl_chot,
        sl_moq,
        sl_ton_kho,
        CASE
            WHEN tcd > 0 AND (
                (CASE WHEN cd_t0 > 0 THEN 1 ELSE 0 END) +
                (CASE WHEN cd_t1 > 0 THEN 1 ELSE 0 END) +
                (CASE WHEN cd_t2 > 0 THEN 1 ELSE 0 END) +
                (CASE WHEN cd_t3 > 0 THEN 1 ELSE 0 END)
            ) > 0
            THEN (sl_ton_kho * 30.0) / (
                tcd / (
                    (CASE WHEN cd_t0 > 0 THEN 1 ELSE 0 END) +
                    (CASE WHEN cd_t1 > 0 THEN 1 ELSE 0 END) +
                    (CASE WHEN cd_t2 > 0 THEN 1 ELSE 0 END) +
                    (CASE WHEN cd_t3 > 0 THEN 1 ELSE 0 END)
                )::numeric
            )
            ELSE 0.0
        END AS so_ngay_vq,
        don_gia_ton_kho,
        don_gia_cuoi,
        don_gia_cuoi * sl_ton_kho AS gia_tri_cuoi,
        1, 1, NOW(), NOW()
        FROM calc;

        PERFORM dlthvt_bulk_sync_b5_period(p_period_id);
    EXCEPTION
        WHEN OTHERS THEN
            ALTER TABLE kh_dat_vat_tu ENABLE TRIGGER trg_dlthvt_b5;
            RAISE;
    END;
    ALTER TABLE kh_dat_vat_tu ENABLE TRIGGER trg_dlthvt_b5;
END;
$BODY$;

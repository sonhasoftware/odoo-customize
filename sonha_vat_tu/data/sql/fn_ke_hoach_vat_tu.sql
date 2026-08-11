
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

-- Index hỗ trợ lọc theo mã NVL
CREATE INDEX IF NOT EXISTS idx_md_sap_ton_kho_ma_hang_trim
    ON md_sap_ton_kho ((TRIM(BOTH FROM ma_hang)));

-- ============================================================
-- B2: Sinh dinh muc — nguồn lọc ma.hang (các bước sau ăn theo dinh_muc)
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_sinh_dinh_muc(p_period_id INTEGER)
LANGUAGE 'plpgsql' AS $BODY$
BEGIN
        -- Trigger mức câu lệnh tự đồng bộ bảng phẳng; không tắt/bật gì cả.
        DROP TABLE IF EXISTS _tmp_dm_override;
        CREATE TEMP TABLE _tmp_dm_override ON COMMIT DROP AS
        SELECT
            b.company_id,
            TRIM(b.ma_tp) AS ma_sap,
            TRIM(b.ma_nvl) AS ma_nvl,
            b.sl_dinh_muc_thay_doi,
            TRUE AS co_sl_dinh_muc_override
        FROM bom_dinh_muc b
        WHERE b.sl_dinh_muc_thay_doi IS NOT NULL
          AND b.sl_dinh_muc_thay_doi <> 0;

        DELETE FROM dinh_muc WHERE period_id = p_period_id;

        -- Chỉ lấy BOM NVL của mã TP trong kỳ.
        DROP TABLE IF EXISTS _tmp_period_tp;
        CREATE TEMP TABLE _tmp_period_tp ON COMMIT DROP AS
        SELECT DISTINCT TRIM(ma_sap) AS ma_tp_goc
        FROM ke_hoach_vat_tu_line
        WHERE period_id = p_period_id
          AND ma_sap IS NOT NULL
          AND TRIM(ma_sap) <> '';

        CREATE INDEX ON _tmp_period_tp (ma_tp_goc);

        -- NVL thuộc BOM kỳ này (trước khi lọc ma.hang).
        DROP TABLE IF EXISTS _tmp_period_nvl_bom;
        CREATE TEMP TABLE _tmp_period_nvl_bom ON COMMIT DROP AS
        SELECT DISTINCT TRIM(b.ma_con) AS ma_sap
        FROM bom_tinh_toan b
        WHERE b.loai_vat_tu = 'NVL'
          AND b.ma_tp_goc IN (SELECT ma_tp_goc FROM _tmp_period_tp)
          AND b.ma_con IS NOT NULL
          AND TRIM(b.ma_con) <> '';

        CREATE INDEX ON _tmp_period_nvl_bom (ma_sap);

        -- Chỉ NVL có trong danh mục ma.hang VÀ thuộc BOM kỳ (không quét cả catalog).
        DROP TABLE IF EXISTS _tmp_ma_hang_sap;
        CREATE TEMP TABLE _tmp_ma_hang_sap ON COMMIT DROP AS
        SELECT DISTINCT TRIM(mh.ma_sap) AS ma_sap
        FROM ma_hang mh
        INNER JOIN _tmp_period_nvl_bom n ON n.ma_sap = TRIM(mh.ma_sap)
        WHERE mh.ma_sap IS NOT NULL
          AND TRIM(mh.ma_sap) <> '';

        CREATE INDEX ON _tmp_ma_hang_sap (ma_sap);

        DROP TABLE IF EXISTS _tmp_bom_nvl_period;
        CREATE TEMP TABLE _tmp_bom_nvl_period ON COMMIT DROP AS
        SELECT
            b.ma_tp_goc,
            b.ten_tp_goc,
            b.ma_tp_cha,
            b.ten_tp_cha,
            TRIM(b.ma_con) AS ma_con,
            b.ten_con,
            b.sl_thuc_te
        FROM bom_tinh_toan b
        INNER JOIN _tmp_ma_hang_sap mh
            ON mh.ma_sap = TRIM(b.ma_con)
        WHERE b.loai_vat_tu = 'NVL'
          AND b.ma_tp_goc IN (SELECT ma_tp_goc FROM _tmp_period_tp)
          AND b.ma_con IS NOT NULL
          AND TRIM(b.ma_con) <> '';

        CREATE INDEX ON _tmp_bom_nvl_period (ma_tp_goc);

        INSERT INTO dinh_muc (
        period_id, company_id, ma_sap, ten_sap, ma_tp, ten_tp, ma_nvl, ten_nvl, sl_dinh_muc,
        sl_dinh_muc_thay_doi, co_sl_dinh_muc_override,
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
        CASE WHEN o.co_sl_dinh_muc_override THEN o.sl_dinh_muc_thay_doi ELSE NULL END,
        COALESCE(o.co_sl_dinh_muc_override, FALSE),
        COALESCE(b1.qty_kd_t0, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_kd_t1, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_kd_t2, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_kd_t3, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_sx_t0, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_sx_t1, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_sx_t2, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_sx_t3, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_cl_t0, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_cl_t1, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_cl_t2, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_cl_t3, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_t0, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_t1, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_t2, 0) * eff.sl_ap_dung,
        COALESCE(b1.qty_t3, 0) * eff.sl_ap_dung,
        1, 1, NOW(), NOW()
    FROM ke_hoach_vat_tu_line b1
    JOIN _tmp_bom_nvl_period bcu
        ON bcu.ma_tp_goc = TRIM(b1.ma_sap)
    LEFT JOIN _tmp_dm_override o
        ON  o.company_id = b1.company_id
        AND o.ma_sap = TRIM(b1.ma_sap)
        AND o.ma_nvl = bcu.ma_con
    CROSS JOIN LATERAL (
        SELECT CASE
            WHEN o.co_sl_dinh_muc_override THEN COALESCE(o.sl_dinh_muc_thay_doi, 0)
            ELSE COALESCE(bcu.sl_thuc_te, 0)
        END AS sl_ap_dung
    ) eff
    WHERE b1.period_id = p_period_id;
END;
$BODY$;

-- ============================================================
-- B3: Tính toán vật tư — CHỈ đọc dinh_muc (B2), không join bom_tinh_toan
-- Ghi bảng chi tiết (audit) rồi SUM ra tinh_toan_vat_tu.
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_tinh_toan_vat_tu(p_period_id INTEGER)
LANGUAGE 'plpgsql' AS $BODY$
DECLARE
    v_prod_company_id INTEGER;
    v_now TIMESTAMP := clock_timestamp();
BEGIN
    SELECT company_sx_id INTO v_prod_company_id
    FROM ke_hoach_vat_tu
    WHERE id = p_period_id;

    IF v_prod_company_id IS NULL THEN
        RAISE EXCEPTION 'Ky % chua co nha may san xuat. Hay tao ke hoach vat tu truoc.', p_period_id;
    END IF;

    -- B3 đọc từ dinh_muc (B2) — chỉ NVL đã lọc ma.hang, giữ override định mức.
    DROP TABLE IF EXISTS _tmp_period_nvl;
    CREATE TEMP TABLE _tmp_period_nvl ON COMMIT DROP AS
    SELECT DISTINCT TRIM(ma_nvl) AS ma_nvl
    FROM dinh_muc
    WHERE period_id = p_period_id
      AND ma_nvl IS NOT NULL
      AND TRIM(ma_nvl) <> '';

    CREATE INDEX ON _tmp_period_nvl (ma_nvl);

    DROP TABLE IF EXISTS _tmp_mdm_dvt;
    CREATE TEMP TABLE _tmp_mdm_dvt ON COMMIT DROP AS
    SELECT DISTINCT ON (TRIM(l.ma_dv))
        TRIM(l.ma_dv) AS ma_nvl,
        l.dvt
    FROM mdm_tong_hop_line l
    INNER JOIN _tmp_period_nvl n ON n.ma_nvl = TRIM(l.ma_dv)
    ORDER BY TRIM(l.ma_dv), l.id;

    CREATE INDEX ON _tmp_mdm_dvt (ma_nvl);

    -- 1 lần đọc dinh_muc (B2) × KHVT → temp; insert chi tiết + B3 đều đọc từ temp
    DROP TABLE IF EXISTS tmp_b3_nvl_detail;
    CREATE TEMP TABLE tmp_b3_nvl_detail ON COMMIT DROP AS
    SELECT
        dm.period_id,
        v_prod_company_id AS company_id,
        dm.company_id AS don_vi_kd_id,
        COALESCE(NULLIF(TRIM(dv.company_code), ''), dv.name) AS don_vi_kd_code,
        TRIM(dm.ma_sap) AS ma,
        NULLIF(TRIM(khvt.ma_hang), '') AS ma_hang,
        NULLIF(TRIM(khvt.ten_hang), '') AS ten_kh,
        NULLIF(TRIM(dm.ma_tp), '') AS ma_tp_cha,
        NULLIF(TRIM(dm.ten_tp), '') AS ten_tp_cha,
        TRIM(dm.ma_nvl) AS ma_nvl,
        NULLIF(TRIM(dm.ten_nvl), '') AS ten_nvl,
        CASE
            WHEN dm.co_sl_dinh_muc_override THEN COALESCE(dm.sl_dinh_muc_thay_doi, 0)
            ELSE COALESCE(dm.sl_dinh_muc, 0)
        END AS sl_thuc_te,
        NULL::INTEGER AS cap_bom,
        COALESCE(khvt.qty_t0, 0) AS qty_kh_t0,
        COALESCE(khvt.qty_t1, 0) AS qty_kh_t1,
        COALESCE(khvt.qty_t2, 0) AS qty_kh_t2,
        COALESCE(khvt.qty_t3, 0) AS qty_kh_t3,
        COALESCE(dm.qty_t0, 0) AS qty_nvl_t0,
        COALESCE(dm.qty_t1, 0) AS qty_nvl_t1,
        COALESCE(dm.qty_t2, 0) AS qty_nvl_t2,
        COALESCE(dm.qty_t3, 0) AS qty_nvl_t3
    FROM dinh_muc dm
    JOIN res_company dv ON dv.id = dm.company_id
    LEFT JOIN ke_hoach_vat_tu_line khvt
        ON  khvt.period_id = dm.period_id
        AND khvt.company_id = dm.company_id
        AND TRIM(khvt.ma_sap) = TRIM(dm.ma_sap)
    WHERE dm.period_id = p_period_id
      AND dm.company_id IS NOT NULL;

    CREATE INDEX ON tmp_b3_nvl_detail (don_vi_kd_id, ma_nvl);
    CREATE INDEX ON tmp_b3_nvl_detail (ma_nvl);

    DELETE FROM tinh_toan_vat_tu_chi_tiet WHERE period_id = p_period_id;

        DELETE FROM tinh_toan_vat_tu WHERE period_id = p_period_id;

        INSERT INTO tinh_toan_vat_tu_chi_tiet (
            period_id, company_id, don_vi_kd_id, don_vi_kd_code,
            ma, ma_hang, ten_kh,
            ma_tp_cha, ten_tp_cha,
            ma_nvl, ten_nvl,
            sl_thuc_te, cap_bom,
            qty_kh_t0, qty_kh_t1, qty_kh_t2, qty_kh_t3,
            qty_nvl_t0, qty_nvl_t1, qty_nvl_t2, qty_nvl_t3,
            create_uid, write_uid, create_date, write_date
        )
        SELECT
            period_id, company_id, don_vi_kd_id, don_vi_kd_code,
            ma, ma_hang, ten_kh,
            ma_tp_cha, ten_tp_cha,
            ma_nvl, ten_nvl,
            sl_thuc_te, cap_bom,
            qty_kh_t0, qty_kh_t1, qty_kh_t2, qty_kh_t3,
            qty_nvl_t0, qty_nvl_t1, qty_nvl_t2, qty_nvl_t3,
            1, 1, v_now, v_now
        FROM tmp_b3_nvl_detail;

        -- Aggregate trước, lookup ĐVT từ temp MDM (không LATERAL từng dòng)
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
            agg.don_vi_kd_code,
            agg.ma_nvl,
            COALESCE(agg.ten_nvl, agg.ma_nvl),
            mdm.dvt,
            0::NUMERIC, 0::NUMERIC, 0::NUMERIC, 0::NUMERIC,
            agg.qty_t0, agg.qty_t1, agg.qty_t2, agg.qty_t3,
            1, 1, v_now, v_now
        FROM (
            SELECT
                t.period_id,
                t.don_vi_kd_id,
                t.don_vi_kd_code,
                t.ma_nvl,
                MIN(NULLIF(TRIM(t.ten_nvl), '')) AS ten_nvl,
                SUM(t.qty_nvl_t0) AS qty_t0,
                SUM(t.qty_nvl_t1) AS qty_t1,
                SUM(t.qty_nvl_t2) AS qty_t2,
                SUM(t.qty_nvl_t3) AS qty_t3
            FROM tmp_b3_nvl_detail t
            GROUP BY t.period_id, t.don_vi_kd_id, t.don_vi_kd_code, t.ma_nvl
        ) agg
        LEFT JOIN _tmp_mdm_dvt mdm ON mdm.ma_nvl = agg.ma_nvl;
END;
$BODY$;

-- ============================================================
-- B4: Tổng hợp vật tư — CHỈ đọc tinh_toan_vat_tu (B3)
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_tong_hop_vat_tu(
    p_period_id INTEGER,
    p_ngay_dp   NUMERIC DEFAULT 15.0
)
LANGUAGE 'plpgsql' AS $BODY$
DECLARE
    v_period_month TEXT;
    v_month_price  TEXT;  -- tháng T-1: nguồn tồn đầu (cùng công thức B5)
    v_month_t0     TEXT;
    v_month_t1     TEXT;
    v_month_t2     TEXT;
    v_month_t3     TEXT;
BEGIN
    SELECT period_month INTO v_period_month FROM ke_hoach_vat_tu WHERE id = p_period_id;
    v_month_price := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY') - INTERVAL '1 month', 'MM/YYYY');
    v_month_t0 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY'), 'MM/YYYY');
    v_month_t1 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY') + INTERVAL '1 month', 'MM/YYYY');
    v_month_t2 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY') + INTERVAL '2 month', 'MM/YYYY');
    v_month_t3 := TO_CHAR(TO_DATE(v_period_month, 'MM/YYYY') + INTERVAL '3 month', 'MM/YYYY');

        DELETE FROM tong_hop_vat_tu WHERE period_id = p_period_id;

        DROP TABLE IF EXISTS _tmp_period_nvl;
        CREATE TEMP TABLE _tmp_period_nvl ON COMMIT DROP AS
    SELECT DISTINCT TRIM(ma_vat_tu) AS ma_vat_tu
    FROM tinh_toan_vat_tu
    WHERE period_id = p_period_id
      AND ma_vat_tu IS NOT NULL
      AND TRIM(ma_vat_tu) <> '';

    CREATE INDEX ON _tmp_period_nvl (ma_vat_tu);

    -- B3 qty thuần × (1 + phần trăm mua dư từ ma_hang_phan_tram) → vt_can_dung B4
    DROP TABLE IF EXISTS _tmp_b3_adj;
    CREATE TEMP TABLE _tmp_b3_adj ON COMMIT DROP AS
    SELECT
        b3.id,
        b3.period_id,
        b3.company_id,
        b3.don_vi_kd_id,
        b3.don_vi_kd_code,
        b3.ma_vat_tu,
        b3.ten_vat_tu,
        b3.don_vi_tinh,
        COALESCE(b3.qty_t0, 0) * (
            1 + COALESCE(NULLIF(pt.phan_tram, 0), 0) / 100.0
        ) AS qty_t0,
        COALESCE(b3.qty_t1, 0) * (
            1 + COALESCE(NULLIF(pt.phan_tram, 0), 0) / 100.0
        ) AS qty_t1,
        COALESCE(b3.qty_t2, 0) * (
            1 + COALESCE(NULLIF(pt.phan_tram, 0), 0) / 100.0
        ) AS qty_t2,
        COALESCE(b3.qty_t3, 0) * (
            1 + COALESCE(NULLIF(pt.phan_tram, 0), 0) / 100.0
        ) AS qty_t3
    FROM tinh_toan_vat_tu b3
    LEFT JOIN (
        SELECT
            p.company_id,
            TRIM(mh.ma_sap) AS ma_sap,
            p.phan_tram
        FROM ma_hang_phan_tram p
        INNER JOIN ma_hang mh ON mh.id = p.ma_nvl_id
    ) pt
        ON  pt.company_id = b3.don_vi_kd_id
        AND pt.ma_sap = TRIM(b3.ma_vat_tu)
    WHERE b3.period_id = p_period_id;

    CREATE INDEX ON _tmp_b3_adj (company_id, ma_vat_tu);
    CREATE INDEX ON _tmp_b3_adj (don_vi_kd_id, ma_vat_tu);

    -- Tồn đầu kỳ T = ton_cuoi SAP tháng T-1; đơn giá = tien_ton_dau/ton_dau cùng tháng.
    DROP TABLE IF EXISTS _tmp_ton_kho;
    CREATE TEMP TABLE _tmp_ton_kho ON COMMIT DROP AS
    WITH sap_rows AS (
        SELECT
            TRIM(mtk.ma_hang) AS ma_hang,
            mtk.chi_nhanh,
            mtk.create_date,
            mtk.id,
            safe_sap_numeric(mtk.ton_cuoi) AS ton_cuoi,
            safe_sap_numeric(mtk.ton_dau) AS ton_dau,
            safe_sap_numeric(mtk.tien_ton_dau) AS tien_ton_dau
        FROM md_sap_ton_kho mtk
        INNER JOIN _tmp_period_nvl n ON n.ma_vat_tu = TRIM(mtk.ma_hang)
        WHERE fn_md_sap_ton_kho_month_key(
                  mtk.from_date, mtk.to_date, mtk.tu_ngay, mtk.den_ngay, mtk.create_date
              ) = v_month_price
          AND (
              safe_sap_numeric(mtk.ton_cuoi) <> 0
              OR safe_sap_numeric(mtk.ton_dau) <> 0
              OR safe_sap_numeric(mtk.tien_ton_dau) <> 0
          )
    ),
    latest AS (
        SELECT DISTINCT ON (ma_hang, chi_nhanh)
            ma_hang, chi_nhanh, ton_cuoi, ton_dau, tien_ton_dau
        FROM sap_rows
        ORDER BY ma_hang, chi_nhanh, create_date DESC, id DESC
    )
    SELECT ma_hang, 'BNH' AS comp_grp,
           SUM(ton_cuoi) AS tdu,
           SUM(ton_dau) AS sl_dau,
           SUM(tien_ton_dau) AS ttdu
    FROM latest WHERE chi_nhanh LIKE '21%' GROUP BY ma_hang
    UNION ALL
    SELECT ma_hang, 'SSP', SUM(ton_cuoi), SUM(ton_dau), SUM(tien_ton_dau)
    FROM latest WHERE chi_nhanh LIKE '22%' GROUP BY ma_hang
    UNION ALL
    SELECT ma_hang, 'ALL', SUM(ton_cuoi), SUM(ton_dau), SUM(tien_ton_dau)
    FROM latest WHERE chi_nhanh NOT LIKE '10%' GROUP BY ma_hang;

    CREATE INDEX ON _tmp_ton_kho (ma_hang, comp_grp);

    DROP TABLE IF EXISTS _tmp_vdd_don_vi;
    CREATE TEMP TABLE _tmp_vdd_don_vi ON COMMIT DROP AS
    SELECT
        b3.company_id,
        b3.ma_vat_tu AS ma_nvl,
        SUM(CASE WHEN vdd.month_key = v_month_t0 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t0,
        SUM(CASE WHEN vdd.month_key = v_month_t1 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t1,
        SUM(CASE WHEN vdd.month_key = v_month_t2 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t2,
        SUM(CASE WHEN vdd.month_key = v_month_t3 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t3,
        SUM(CASE WHEN vdd.month_key IN (v_month_t0, v_month_t1, v_month_t2, v_month_t3)
                 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_total,
        SUM(CASE WHEN vdd.month_key = v_month_t0 THEN COALESCE(vdd.gia_tri, vdd.so_luong * vdd.don_gia, 0) ELSE 0 END) AS gt_t0,
        SUM(CASE WHEN vdd.month_key = v_month_t1 THEN COALESCE(vdd.gia_tri, vdd.so_luong * vdd.don_gia, 0) ELSE 0 END) AS gt_t1,
        SUM(CASE WHEN vdd.month_key = v_month_t2 THEN COALESCE(vdd.gia_tri, vdd.so_luong * vdd.don_gia, 0) ELSE 0 END) AS gt_t2,
        SUM(CASE WHEN vdd.month_key = v_month_t3 THEN COALESCE(vdd.gia_tri, vdd.so_luong * vdd.don_gia, 0) ELSE 0 END) AS gt_t3,
        SUM(CASE WHEN vdd.month_key IN (v_month_t0, v_month_t1, v_month_t2, v_month_t3)
                 THEN COALESCE(vdd.gia_tri, vdd.so_luong * vdd.don_gia, 0) ELSE 0 END) AS gt_total
    FROM (
        SELECT DISTINCT company_id, don_vi_kd_id, ma_vat_tu
        FROM tinh_toan_vat_tu
        WHERE period_id = p_period_id
          AND don_vi_kd_id IS NOT NULL
    ) b3
    LEFT JOIN vat_tu_di_duong vdd
        ON  vdd.company_id = b3.don_vi_kd_id
        AND TRIM(vdd.ma_nvl) = TRIM(b3.ma_vat_tu)
        AND COALESCE(vdd.loai, 'don_vi') = 'don_vi'
    GROUP BY b3.company_id, b3.ma_vat_tu;

    CREATE INDEX ON _tmp_vdd_don_vi (company_id, ma_nvl);

    -- Dong gop B4 (don_vi_kd_id NULL): ton / di duong / can doi
    INSERT INTO tong_hop_vat_tu (
        period_id, company_id, don_vi_kd_id, ma_dat_hang, ma_sap, ten_nvl, chung_loai, don_vi_tinh,
        ton_dau, don_gia_ton_kho,
        ve_du_kien_don_vi_t0, ve_du_kien_don_vi_t1, ve_du_kien_don_vi_t2, ve_du_kien_don_vi_t3,
        ve_du_kien_don_gia_t0, ve_du_kien_don_gia_t1, ve_du_kien_don_gia_t2, ve_du_kien_don_gia_t3,
        ve_du_kien_gia_tri_t0, ve_du_kien_gia_tri_t1, ve_du_kien_gia_tri_t2, ve_du_kien_gia_tri_t3,
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
        agg.don_gia_ton_kho,
        agg.ve_du_kien_don_vi_t0,
        agg.ve_du_kien_don_vi_t1,
        agg.ve_du_kien_don_vi_t2,
        agg.ve_du_kien_don_vi_t3,
        agg.ve_du_kien_don_gia_t0,
        agg.ve_du_kien_don_gia_t1,
        agg.ve_du_kien_don_gia_t2,
        agg.ve_du_kien_don_gia_t3,
        agg.ve_du_kien_gia_tri_t0,
        agg.ve_du_kien_gia_tri_t1,
        agg.ve_du_kien_gia_tri_t2,
        agg.ve_du_kien_gia_tri_t3,
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
            COALESCE(tk.tdu, 0)                                       AS ton_dau,
            CASE
                WHEN COALESCE(tk.sl_dau, 0) != 0 THEN COALESCE(tk.ttdu, 0) / tk.sl_dau
                ELSE 0
            END                                                       AS don_gia_ton_kho,
            COALESCE(vdd_dv.qty_t0_adj, 0)                            AS ve_du_kien_don_vi_t0,
            COALESCE(vdd_dv.qty_t1, 0)                                AS ve_du_kien_don_vi_t1,
            COALESCE(vdd_dv.qty_t2, 0)                                AS ve_du_kien_don_vi_t2,
            COALESCE(vdd_dv.qty_t3, 0)                                AS ve_du_kien_don_vi_t3,
            CASE WHEN COALESCE(vdd_dv.qty_t0_adj, 0) > 0
                 THEN COALESCE(vdd_dv.gt_t0, 0) / vdd_dv.qty_t0_adj ELSE 0 END AS ve_du_kien_don_gia_t0,
            CASE WHEN COALESCE(vdd_dv.qty_t1, 0) > 0
                 THEN COALESCE(vdd_dv.gt_t1, 0) / vdd_dv.qty_t1 ELSE 0 END AS ve_du_kien_don_gia_t1,
            CASE WHEN COALESCE(vdd_dv.qty_t2, 0) > 0
                 THEN COALESCE(vdd_dv.gt_t2, 0) / vdd_dv.qty_t2 ELSE 0 END AS ve_du_kien_don_gia_t2,
            CASE WHEN COALESCE(vdd_dv.qty_t3, 0) > 0
                 THEN COALESCE(vdd_dv.gt_t3, 0) / vdd_dv.qty_t3 ELSE 0 END AS ve_du_kien_don_gia_t3,
            COALESCE(vdd_dv.gt_t0, 0)                                 AS ve_du_kien_gia_tri_t0,
            COALESCE(vdd_dv.gt_t1, 0)                                 AS ve_du_kien_gia_tri_t1,
            COALESCE(vdd_dv.gt_t2, 0)                                 AS ve_du_kien_gia_tri_t2,
            COALESCE(vdd_dv.gt_t3, 0)                                 AS ve_du_kien_gia_tri_t3,
            COALESCE(vdd_dv.qty_total, 0)                            AS tong_di_duong,
            COALESCE(tk.tdu, 0) + COALESCE(vdd_dv.qty_total, 0)
                - SUM(COALESCE(b3.qty_t0, 0))                         AS ton_cuoi_t0,
            COALESCE(tk.tdu, 0) + COALESCE(vdd_dv.qty_total, 0)
                - SUM(COALESCE(b3.qty_t0, 0))
                - SUM(COALESCE(b3.qty_t1, 0))                         AS ton_cuoi_t1,
            COALESCE(tk.tdu, 0) + COALESCE(vdd_dv.qty_total, 0)
                - SUM(COALESCE(b3.qty_t0, 0))
                - SUM(COALESCE(b3.qty_t1, 0))
                - SUM(COALESCE(b3.qty_t2, 0))                         AS ton_cuoi_t2,
            COALESCE(tk.tdu, 0) + COALESCE(vdd_dv.qty_total, 0)
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
                    COALESCE(tk.tdu, 0) + COALESCE(vdd_dv.qty_total, 0)
                    - SUM(COALESCE(b3.qty_t0, 0))
                    - SUM(COALESCE(b3.qty_t1, 0))
                    - SUM(COALESCE(b3.qty_t2, 0))
                    - SUM(COALESCE(b3.qty_t3, 0))
                )
            )                                                         AS so_luong_thieu
        FROM _tmp_b3_adj b3
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
                COALESCE(v.qty_total, 0) AS qty_total,
                COALESCE(v.gt_t0, 0) AS gt_t0,
                COALESCE(v.gt_t1, 0) AS gt_t1,
                COALESCE(v.gt_t2, 0) AS gt_t2,
                COALESCE(v.gt_t3, 0) AS gt_t3
            FROM _tmp_vdd_don_vi v
            WHERE v.company_id = b3.company_id AND v.ma_nvl = b3.ma_vat_tu
        ) vdd_dv ON TRUE
        WHERE b3.period_id = p_period_id
        GROUP BY
            b3.company_id, c.company_code,
            b3.ma_vat_tu, b3.ten_vat_tu,
            tk.tdu, tk.sl_dau, tk.ttdu,
            vdd_dv.qty_t0_adj, vdd_dv.qty_t1, vdd_dv.qty_t2, vdd_dv.qty_t3, vdd_dv.qty_total,
            vdd_dv.gt_t0, vdd_dv.gt_t1, vdd_dv.gt_t2, vdd_dv.gt_t3
    ) agg;

    -- Chi tiet B4 theo don vi dat hang (KD): chi vt_can_dung, phuc vu bao cao
    INSERT INTO tong_hop_vat_tu (
        period_id, company_id, don_vi_kd_id, ma_dat_hang, ma_sap, ten_nvl, chung_loai, don_vi_tinh,
        ton_dau, don_gia_ton_kho,
        ve_du_kien_don_vi_t0, ve_du_kien_don_vi_t1, ve_du_kien_don_vi_t2, ve_du_kien_don_vi_t3,
        ve_du_kien_don_gia_t0, ve_du_kien_don_gia_t1, ve_du_kien_don_gia_t2, ve_du_kien_don_gia_t3,
        ve_du_kien_gia_tri_t0, ve_du_kien_gia_tri_t1, ve_du_kien_gia_tri_t2, ve_du_kien_gia_tri_t3,
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
        0, 0,
        0, 0, 0, 0,
        0, 0, 0, 0,
        0, 0, 0, 0,
        SUM(COALESCE(b3.qty_t0, 0)),
        SUM(COALESCE(b3.qty_t1, 0)),
        SUM(COALESCE(b3.qty_t2, 0)),
        SUM(COALESCE(b3.qty_t3, 0)),
        0, 0, 0, 0,
        0, 0, 0,
        1, 1, NOW(), NOW()
    FROM _tmp_b3_adj b3
    WHERE b3.don_vi_kd_id IS NOT NULL
    GROUP BY
        b3.company_id, b3.don_vi_kd_id,
        b3.ma_vat_tu, b3.ten_vat_tu;
END;
$BODY$;

-- ============================================================
-- B5: Kế hoạch đặt vật tư — CHỈ đọc tong_hop_vat_tu gộp (B4, don_vi_kd_id NULL)
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
        tong_hang_di_duong_dg_t0, tong_hang_di_duong_dg_t1, tong_hang_di_duong_dg_t2, tong_hang_di_duong_dg_t3,
        tong_hang_di_duong_gt_t0, tong_hang_di_duong_gt_t1, tong_hang_di_duong_gt_t2, tong_hang_di_duong_gt_t3,
        tong_hang_di_duong, tong_gia_tri_di_duong,
        sl_du_tru_toi_thieu,
        sl_dat_mua_de_xuat,
        sl_dat_mua_chot,
        sl_can_mua_theo_moq,
        don_gia_mua,
        gia_tri_mua_hang,
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
            COALESCE(b4.ve_du_kien_don_gia_t0, 0) AS dd_dg_t0,
            COALESCE(b4.ve_du_kien_don_gia_t1, 0) AS dd_dg_t1,
            COALESCE(b4.ve_du_kien_don_gia_t2, 0) AS dd_dg_t2,
            COALESCE(b4.ve_du_kien_don_gia_t3, 0) AS dd_dg_t3,
            COALESCE(b4.ve_du_kien_gia_tri_t0, 0) AS dd_gt_t0,
            COALESCE(b4.ve_du_kien_gia_tri_t1, 0) AS dd_gt_t1,
            COALESCE(b4.ve_du_kien_gia_tri_t2, 0) AS dd_gt_t2,
            COALESCE(b4.ve_du_kien_gia_tri_t3, 0) AS dd_gt_t3,
            (COALESCE(b4.ve_du_kien_don_vi_t0, 0) + COALESCE(b4.ve_du_kien_don_vi_t1, 0) + 
             COALESCE(b4.ve_du_kien_don_vi_t2, 0) + COALESCE(b4.ve_du_kien_don_vi_t3, 0)) AS tdd,
            (COALESCE(b4.ve_du_kien_gia_tri_t0, 0) + COALESCE(b4.ve_du_kien_gia_tri_t1, 0) +
             COALESCE(b4.ve_du_kien_gia_tri_t2, 0) + COALESCE(b4.ve_du_kien_gia_tri_t3, 0)) AS tdd_gt,
            COALESCE(b4.don_gia_ton_kho, 0) AS don_gia_ton_kho,
            COALESCE(b4.ton_dau, 0) * COALESCE(b4.don_gia_ton_kho, 0) AS gia_tri_ton_dau
        FROM tong_hop_vat_tu b4
        WHERE b4.period_id = p_period_id
          AND b4.don_vi_kd_id IS NULL
    ),
    calc AS (
        SELECT
            b.*,
            CASE WHEN cd_t0 > 0 THEN (cd_t0 / 28.0) * p_ngay_dt ELSE 0.0 END AS sl_du_tru
        FROM b4_data b
    ),
    calc_moq AS (
        SELECT
            c.*,
            (ton_dau - tcd + tdd - sl_du_tru) AS sl_de_xuat,
            CASE WHEN (ton_dau - tcd + tdd - sl_du_tru) > 0 THEN 0.0
                 ELSE -(ton_dau - tcd + tdd - sl_du_tru)
            END AS sl_chot
        FROM calc c
    ),
    calc_final AS (
        SELECT
            m.*,
            sl_chot AS sl_moq,
            0.0 AS don_gia_mua_val,
            0.0 AS gia_tri_mua,
            (ton_dau - tcd + tdd + sl_chot) AS sl_ton_kho,
            CASE
                WHEN (ton_dau + tdd + sl_chot) > 0
                THEN (gia_tri_ton_dau + 0.0) / (ton_dau + tdd + sl_chot)
                ELSE 0.0
            END AS don_gia_cuoi
        FROM calc_moq m
    )
    SELECT
        period_id, company_id, ma_sap, ten_nvl, chung_loai, don_vi_tinh,
        ton_dau,
        cd_t0, cd_t1, cd_t2, cd_t3,
        tcd,
        dd_t0, dd_t1, dd_t2, dd_t3,
        dd_dg_t0, dd_dg_t1, dd_dg_t2, dd_dg_t3,
        dd_gt_t0, dd_gt_t1, dd_gt_t2, dd_gt_t3,
        tdd, tdd_gt,
        sl_du_tru,
        sl_de_xuat,
        sl_chot,
        sl_moq,
        don_gia_mua_val,
        gia_tri_mua,
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
        FROM calc_final;
END;
$BODY$;

-- ============================================================
-- B6: Tổng hợp kế hoạch vật tư BCU — copy B5 + đi đường BCU
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_ke_hoach_dat_vat_tu_bcu(
    p_period_id INTEGER
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

    DELETE FROM kh_dat_vat_tu_bcu WHERE period_id = p_period_id;

    INSERT INTO kh_dat_vat_tu_bcu (
        period_id, company_id, ma_sap, ten_nvl, chung_loai, don_vi_tinh,
        tong_ton_nvl_sl, don_gia_ton_kho,
        tong_sl_vt_can_dung_t0, tong_sl_vt_can_dung_t1, tong_sl_vt_can_dung_t2, tong_sl_vt_can_dung_t3,
        tong_vt_can_dung,
        tong_hang_di_duong_sl_t0, tong_hang_di_duong_sl_t1, tong_hang_di_duong_sl_t2, tong_hang_di_duong_sl_t3,
        tong_hang_di_duong_dg_t0, tong_hang_di_duong_dg_t1, tong_hang_di_duong_dg_t2, tong_hang_di_duong_dg_t3,
        tong_hang_di_duong_gt_t0, tong_hang_di_duong_gt_t1, tong_hang_di_duong_gt_t2, tong_hang_di_duong_gt_t3,
        tong_hang_di_duong, tong_gia_tri_di_duong,
        ve_du_kien_bcu_t0, ve_du_kien_bcu_t1, ve_du_kien_bcu_t2, ve_du_kien_bcu_t3,
        ve_du_kien_bcu_dg_t0, ve_du_kien_bcu_dg_t1, ve_du_kien_bcu_dg_t2, ve_du_kien_bcu_dg_t3,
        ve_du_kien_bcu_gt_t0, ve_du_kien_bcu_gt_t1, ve_du_kien_bcu_gt_t2, ve_du_kien_bcu_gt_t3,
        tong_ve_du_kien_bcu, tong_gia_tri_bcu,
        sl_du_tru_toi_thieu, sl_dat_mua_de_xuat, sl_dat_mua_chot, sl_can_mua_theo_moq,
        don_gia_mua,
        create_uid, write_uid, create_date, write_date
    )
    SELECT
        b5.period_id, b5.company_id, b5.ma_sap, b5.ten_nvl, b5.chung_loai, b5.don_vi_tinh,
        b5.tong_ton_nvl_sl, b5.don_gia_ton_kho,
        b5.tong_sl_vt_can_dung_t0, b5.tong_sl_vt_can_dung_t1, b5.tong_sl_vt_can_dung_t2, b5.tong_sl_vt_can_dung_t3,
        b5.tong_vt_can_dung,
        b5.tong_hang_di_duong_sl_t0, b5.tong_hang_di_duong_sl_t1, b5.tong_hang_di_duong_sl_t2, b5.tong_hang_di_duong_sl_t3,
        b5.tong_hang_di_duong_dg_t0, b5.tong_hang_di_duong_dg_t1, b5.tong_hang_di_duong_dg_t2, b5.tong_hang_di_duong_dg_t3,
        b5.tong_hang_di_duong_gt_t0, b5.tong_hang_di_duong_gt_t1, b5.tong_hang_di_duong_gt_t2, b5.tong_hang_di_duong_gt_t3,
        b5.tong_hang_di_duong, b5.tong_gia_tri_di_duong,
        COALESCE(vbcu.qty_t0, 0), COALESCE(vbcu.qty_t1, 0), COALESCE(vbcu.qty_t2, 0), COALESCE(vbcu.qty_t3, 0),
        CASE WHEN COALESCE(vbcu.qty_t0, 0) > 0 THEN COALESCE(vbcu.gt_t0, 0) / vbcu.qty_t0 ELSE 0 END,
        CASE WHEN COALESCE(vbcu.qty_t1, 0) > 0 THEN COALESCE(vbcu.gt_t1, 0) / vbcu.qty_t1 ELSE 0 END,
        CASE WHEN COALESCE(vbcu.qty_t2, 0) > 0 THEN COALESCE(vbcu.gt_t2, 0) / vbcu.qty_t2 ELSE 0 END,
        CASE WHEN COALESCE(vbcu.qty_t3, 0) > 0 THEN COALESCE(vbcu.gt_t3, 0) / vbcu.qty_t3 ELSE 0 END,
        COALESCE(vbcu.gt_t0, 0), COALESCE(vbcu.gt_t1, 0), COALESCE(vbcu.gt_t2, 0), COALESCE(vbcu.gt_t3, 0),
        COALESCE(vbcu.qty_total, 0), COALESCE(vbcu.gt_total, 0),
        b5.sl_du_tru_toi_thieu, b5.sl_dat_mua_de_xuat, b5.sl_dat_mua_chot, b5.sl_can_mua_theo_moq,
        b5.don_gia_mua,
        1, 1, NOW(), NOW()
    FROM kh_dat_vat_tu b5
    LEFT JOIN LATERAL (
        SELECT
            SUM(CASE WHEN vdd.month_key = v_month_t0 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t0,
            SUM(CASE WHEN vdd.month_key = v_month_t1 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t1,
            SUM(CASE WHEN vdd.month_key = v_month_t2 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t2,
            SUM(CASE WHEN vdd.month_key = v_month_t3 THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_t3,
            SUM(CASE WHEN vdd.month_key IN (v_month_t0, v_month_t1, v_month_t2, v_month_t3)
                     THEN COALESCE(vdd.so_luong, 0) ELSE 0 END) AS qty_total,
            SUM(CASE WHEN vdd.month_key = v_month_t0 THEN COALESCE(vdd.gia_tri, vdd.so_luong * vdd.don_gia, 0) ELSE 0 END) AS gt_t0,
            SUM(CASE WHEN vdd.month_key = v_month_t1 THEN COALESCE(vdd.gia_tri, vdd.so_luong * vdd.don_gia, 0) ELSE 0 END) AS gt_t1,
            SUM(CASE WHEN vdd.month_key = v_month_t2 THEN COALESCE(vdd.gia_tri, vdd.so_luong * vdd.don_gia, 0) ELSE 0 END) AS gt_t2,
            SUM(CASE WHEN vdd.month_key = v_month_t3 THEN COALESCE(vdd.gia_tri, vdd.so_luong * vdd.don_gia, 0) ELSE 0 END) AS gt_t3,
            SUM(CASE WHEN vdd.month_key IN (v_month_t0, v_month_t1, v_month_t2, v_month_t3)
                     THEN COALESCE(vdd.gia_tri, vdd.so_luong * vdd.don_gia, 0) ELSE 0 END) AS gt_total
        FROM vat_tu_di_duong vdd
        WHERE vdd.loai = 'bcu'
          AND TRIM(vdd.ma_nvl) = TRIM(b5.ma_sap)
          AND vdd.company_id = b5.company_id
    ) vbcu ON TRUE
    WHERE b5.period_id = p_period_id;
END;
$BODY$;

-- ============================================================
-- B7: Phê duyệt kế hoạch vật tư
-- ============================================================
CREATE OR REPLACE PROCEDURE public.fn_phe_duyet_kh_vat_tu(
    p_period_id INTEGER
)
LANGUAGE 'plpgsql' AS $BODY$
DECLARE
    v_ngay_co_so DATE;
BEGIN
    DELETE FROM phe_duyet_kh_vat_tu WHERE period_id = p_period_id;

    SELECT TO_DATE(period_month, 'MM/YYYY') INTO v_ngay_co_so
    FROM ke_hoach_vat_tu WHERE id = p_period_id;

    INSERT INTO phe_duyet_kh_vat_tu (
        period_id, company_id, ma_sap, ten_nvl, don_vi_tinh,
        khoi_luong_don_vi_dat, khoi_luong_bcu_dat,
        ngay_co_so,
        create_uid, write_uid, create_date, write_date
    )
    SELECT
        p_period_id,
        COALESCE(kh.company_id, bcu.company_id),
        COALESCE(kh.ma_sap, bcu.ma_sap),
        COALESCE(kh.ten_nvl, bcu.ten_nvl),
        COALESCE(kh.don_vi_tinh, bcu.don_vi_tinh),
        COALESCE(kh.sl_dat_mua_chot, 0),
        COALESCE(bcu.sl_dat_mua_chot, 0),
        v_ngay_co_so,
        1, 1, NOW(), NOW()
    FROM kh_dat_vat_tu kh
    FULL OUTER JOIN kh_dat_vat_tu_bcu bcu
        ON  kh.period_id = bcu.period_id
        AND kh.company_id = bcu.company_id
        AND TRIM(kh.ma_sap) = TRIM(bcu.ma_sap)
    WHERE COALESCE(kh.period_id, bcu.period_id) = p_period_id
      AND (
          COALESCE(kh.sl_dat_mua_chot, 0) > 0
          OR COALESCE(bcu.sl_dat_mua_chot, 0) > 0
      );
END;
$BODY$;

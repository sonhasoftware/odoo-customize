CREATE TABLE IF NOT EXISTS bom_tinh_toan (
    id SERIAL PRIMARY KEY,
    ma_tp_goc VARCHAR,
    ten_tp_goc VARCHAR,
    ma_tp_cha VARCHAR,
    ten_tp_cha VARCHAR,
    ma_con VARCHAR,
    ten_con VARCHAR,
    cap_bom INTEGER,
    sl_dm NUMERIC,
    sl_spdm NUMERIC,
    sl_1sp NUMERIC,
    phe_lieu_cung_cap NUMERIC,
    sl_tinh_toan NUMERIC,
    sl_thuc_te NUMERIC,
    loai_vat_tu VARCHAR,
    cay_bom VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_bom_tinh_toan_tp_loai
    ON bom_tinh_toan (ma_tp_goc, loai_vat_tu);

CREATE INDEX IF NOT EXISTS idx_bom_tinh_toan_nvl_ma_tp
    ON bom_tinh_toan (ma_tp_goc)
    WHERE loai_vat_tu = 'NVL';

CREATE OR REPLACE PROCEDURE public.fn_bom_chuoi_cung_ung()
LANGUAGE 'plpgsql'
AS $BODY$
BEGIN

    -- Xóa dữ liệu cũ
    TRUNCATE TABLE bom_tinh_toan;

    -- Insert dữ liệu mới từ CTE
    INSERT INTO bom_tinh_toan (
        ma_tp_goc, ten_tp_goc, ma_tp_cha, ten_tp_cha, ma_con, ten_con,
        cap_bom, sl_dm, sl_spdm, sl_1sp, phe_lieu_cung_cap, sl_tinh_toan, sl_thuc_te,
        loai_vat_tu, cay_bom
    )
    WITH RECURSIVE

    -------------------------------------------------------------
    -- LOẠI BỎ DỮ LIỆU TRÙNG
    -------------------------------------------------------------
    raw_bom1 AS
    (
        SELECT
            *,
            ROW_NUMBER() OVER
            (
                PARTITION BY ma_tp, ma_nvl
                ORDER BY den_ngay DESC
            ) AS rn
        FROM md_sap_bom
        WHERE den_ngay IS NOT NULL
          AND den_ngay <> ''
          AND den_ngay ~ '^\d{2}\.\d{2}\.\d{4}$'
          AND TO_DATE(den_ngay,'DD.MM.YYYY') > CURRENT_DATE
    ),
    raw_bom AS
    (
        SELECT * FROM raw_bom1 WHERE rn = 1
    ),

    -------------------------------------------------------------
    -- BOM GỐC
    -------------------------------------------------------------
    bom_goc AS
    (
        SELECT
            ma_tp,
            ten_tp,
            ma_nvl,
            ten_nvl,

            -------------------------------------------------------------
            -- SL ĐỊNH MỨC
            -------------------------------------------------------------
            CASE
                WHEN sl_dm LIKE '%-'
                    THEN -1 * REPLACE(sl_dm,'-','')::numeric
                ELSE sl_dm::numeric
            END AS sl_dm,

            -------------------------------------------------------------
            -- SL SP ĐỊNH MỨC
            -------------------------------------------------------------
            CASE
                WHEN sl_spdm::numeric = 0
                    THEN 1
                ELSE sl_spdm::numeric
            END AS sl_spdm,

            -------------------------------------------------------------
            -- ĐỊNH MỨC CHO 1 SP
            -------------------------------------------------------------
            (
                CASE
                    WHEN sl_dm LIKE '%-'
                        THEN -1 * REPLACE(sl_dm,'-','')::numeric
                    ELSE sl_dm::numeric
                END
                /
                CASE
                    WHEN sl_spdm::numeric = 0
                        THEN 1
                    ELSE sl_spdm::numeric
                END
            ) AS sl_1sp,

            den_ngay

        FROM raw_bom

        WHERE den_ngay IS NOT NULL
          AND den_ngay <> ''
          AND den_ngay ~ '^\d{2}\.\d{2}\.\d{4}$'
          AND TO_DATE(den_ngay,'DD.MM.YYYY') > CURRENT_DATE
          AND rn = 1
    ),

    -------------------------------------------------------------
    -- DANH SÁCH TP/BTP
    -------------------------------------------------------------
    bom_tp AS
    (
        SELECT DISTINCT ma_tp
        FROM bom_goc
    ),

    -------------------------------------------------------------
    -- TỔNG PHẾ LIỆU
    -------------------------------------------------------------
    phe_lieu AS
    (
        SELECT
            ma_tp,
            ABS(SUM(sl_1sp)) AS tong_phe_lieu
        FROM bom_goc
        WHERE sl_1sp < 0
        GROUP BY ma_tp
    ),

    -------------------------------------------------------------
    -- BOM RECURSIVE
    -------------------------------------------------------------
    bom_cte AS
    (
        -------------------------------------------------------------
        -- LEVEL 1
        -------------------------------------------------------------
        SELECT
            b.ma_tp                    AS ma_tp_goc,
            b.ten_tp                   AS ten_tp_goc,

            b.ma_tp                    AS ma_tp_cha,
            b.ten_tp                   AS ten_tp_cha,

            b.ma_nvl                   AS ma_con,
            b.ten_nvl                  AS ten_con,

            1                          AS cap_bom,

            b.sl_dm,
            b.sl_spdm,
            b.sl_1sp,

            COALESCE(p.tong_phe_lieu,0) AS phe_lieu_cung_cap,

            -------------------------------------------------------------
            -- SL TÍNH TOÁN
            -------------------------------------------------------------
            (
                ABS(b.sl_1sp)
                +
                COALESCE(p.tong_phe_lieu,0)
            ) AS sl_tinh_toan,

            -------------------------------------------------------------
            -- SL THỰC TẾ
            -- (sl_1sp + phế liệu) * SL CHA
            -------------------------------------------------------------
            (
                ABS(b.sl_1sp)
                +
                COALESCE(p.tong_phe_lieu,0)
            ) AS sl_thuc_te,

            -------------------------------------------------------------
            -- LOẠI VẬT TƯ
            -------------------------------------------------------------
            CASE
                WHEN x.ma_tp IS NOT NULL
                    THEN 'BTP'
                ELSE 'NVL'
            END AS loai_vat_tu,

            -------------------------------------------------------------
            -- CÂY BOM
            -------------------------------------------------------------
            b.ma_tp || ' -> ' || b.ma_nvl AS cay_bom

        FROM bom_goc b

        LEFT JOIN phe_lieu p
               ON b.ma_tp = p.ma_tp

        LEFT JOIN bom_tp x
               ON b.ma_nvl = x.ma_tp

        UNION ALL

        -------------------------------------------------------------
        -- LEVEL SAU
        -------------------------------------------------------------
        SELECT
            c.ma_tp_goc,
            c.ten_tp_goc,

            b.ma_tp                    AS ma_tp_cha,
            b.ten_tp                   AS ten_tp_cha,

            b.ma_nvl                   AS ma_con,
            b.ten_nvl                  AS ten_con,

            c.cap_bom + 1              AS cap_bom,

            b.sl_dm,
            b.sl_spdm,
            b.sl_1sp,

            COALESCE(p.tong_phe_lieu,0) AS phe_lieu_cung_cap,

            -------------------------------------------------------------
            -- SL TÍNH TOÁN
            -------------------------------------------------------------
            (
                (
                    ABS(b.sl_1sp)
                    +
                    COALESCE(p.tong_phe_lieu,0)
                )
                *
                c.sl_thuc_te
            ) AS sl_tinh_toan,

            -------------------------------------------------------------
            -- SL THỰC TẾ
            -- (sl_1sp + phế liệu) * SL THỰC TẾ CHA
            -------------------------------------------------------------
            (
                (
                    ABS(b.sl_1sp)
                    +
                    COALESCE(p.tong_phe_lieu,0)
                )
                *
                c.sl_thuc_te
            ) AS sl_thuc_te,

            -------------------------------------------------------------
            -- LOẠI VẬT TƯ
            -------------------------------------------------------------
            CASE
                WHEN x.ma_tp IS NOT NULL
                    THEN 'BTP'
                ELSE 'NVL'
            END AS loai_vat_tu,

            -------------------------------------------------------------
            -- CÂY BOM
            -------------------------------------------------------------
            c.cay_bom || ' -> ' || b.ma_nvl AS cay_bom

        FROM bom_cte c

        INNER JOIN bom_goc b
            ON c.ma_con = b.ma_tp

        LEFT JOIN phe_lieu p
            ON b.ma_tp = p.ma_tp

        LEFT JOIN bom_tp x
            ON b.ma_nvl = x.ma_tp

        -------------------------------------------------------------
        -- CHỐNG LOOP BOM
        -------------------------------------------------------------
        WHERE c.cay_bom NOT LIKE '%' || b.ma_nvl || '%'

          -------------------------------------------------------------
          -- GIỚI HẠN LEVEL
          -------------------------------------------------------------
          AND c.cap_bom < 20
    )

    -------------------------------------------------------------
    -- RESULT
    -------------------------------------------------------------
    SELECT
        ma_tp_goc,
        ten_tp_goc,

        ma_tp_cha,
        ten_tp_cha,

        ma_con,
        ten_con,

        cap_bom,

        sl_dm,
        sl_spdm,

        ROUND(sl_1sp,6) AS sl_1sp,

        ROUND(phe_lieu_cung_cap,6) AS phe_lieu_cung_cap,

        ROUND(sl_tinh_toan,6) AS sl_tinh_toan,

        ROUND(sl_thuc_te,6) AS sl_thuc_te,

        loai_vat_tu,

        cay_bom

    FROM bom_cte
    WHERE sl_1sp > 0
    ORDER BY cay_bom;

END;
$BODY$;

CALL public.fn_bom_chuoi_cung_ung();

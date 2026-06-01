-- ============================================================
-- Demo multi-month cho bao cao nhu cau vat tu / pivot
-- Chung tu: KHVT_SHE_0001
-- Don vi lap nhu cau: SHE
-- Don vi san xuat demo: SSP (fallback BNH neu khong co SSP)
-- ============================================================

-- 0. Xoa du lieu demo cu theo chung tu, de script chay lai duoc nhieu lan.
WITH demo_period AS (
    SELECT id
      FROM ke_hoach_vat_tu
     WHERE code = 'KHVT_SHE_0001'
        OR (company_id = 17 AND period_month IN ('05/2026', '06/2026'))
)
DELETE FROM du_lieu_tong_hop_vat_tu
 WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id
      FROM ke_hoach_vat_tu
     WHERE code = 'KHVT_SHE_0001'
        OR (company_id = 17 AND period_month IN ('05/2026', '06/2026'))
)
DELETE FROM kh_dat_vat_tu
 WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id
      FROM ke_hoach_vat_tu
     WHERE code = 'KHVT_SHE_0001'
        OR (company_id = 17 AND period_month IN ('05/2026', '06/2026'))
)
DELETE FROM tong_hop_vat_tu
 WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id
      FROM ke_hoach_vat_tu
     WHERE code = 'KHVT_SHE_0001'
        OR (company_id = 17 AND period_month IN ('05/2026', '06/2026'))
)
DELETE FROM tinh_toan_vat_tu
 WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id
      FROM ke_hoach_vat_tu
     WHERE code = 'KHVT_SHE_0001'
        OR (company_id = 17 AND period_month IN ('05/2026', '06/2026'))
)
DELETE FROM dinh_muc
 WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id
      FROM ke_hoach_vat_tu
     WHERE code = 'KHVT_SHE_0001'
        OR (company_id = 17 AND period_month IN ('05/2026', '06/2026'))
)
DELETE FROM ke_hoach_vat_tu_line
 WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id
      FROM ke_hoach_vat_tu
     WHERE code = 'KHVT_SHE_0001'
        OR (company_id = 17 AND period_month IN ('05/2026', '06/2026'))
)
DELETE FROM ke_hoach_san_xuat
 WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id
      FROM ke_hoach_vat_tu
     WHERE code = 'KHVT_SHE_0001'
        OR (company_id = 17 AND period_month IN ('05/2026', '06/2026'))
)
DELETE FROM ke_hoach_kinh_doanh
 WHERE period_id IN (SELECT id FROM demo_period);

DELETE FROM ke_hoach_vat_tu
 WHERE code = 'KHVT_SHE_0001'
    OR (company_id = 17 AND period_month IN ('05/2026', '06/2026'));

DELETE FROM vat_tu_di_duong
 WHERE month_key IN ('06/2026', '07/2026', '08/2026')
   AND ma_sap IN ('20000026', '20000094', '20000177', '20000178', '20000253', '20000335');

-- 1. Master nganh/dong demo.
INSERT INTO nganh_hang (code, name, create_uid, write_uid, create_date, write_date)
VALUES ('DEMO_BNN', 'Binh nuoc nong (Demo)', 1, 1, NOW(), NOW())
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    write_uid = EXCLUDED.write_uid,
    write_date = NOW();

UPDATE dong_hang
   SET name = 'Dong GT (Demo)',
       nganh_hang_id = (SELECT id FROM nganh_hang WHERE code = 'DEMO_BNN' LIMIT 1),
       write_uid = 1,
       write_date = NOW()
 WHERE code = 'DEMO_GT';

INSERT INTO dong_hang (code, name, nganh_hang_id, create_uid, write_uid, create_date, write_date)
SELECT
    'DEMO_GT',
    'Dong GT (Demo)',
    (SELECT id FROM nganh_hang WHERE code = 'DEMO_BNN' LIMIT 1),
    1, 1, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM dong_hang WHERE code = 'DEMO_GT'
);

-- 2. Danh muc thanh pham demo: 3 ma de test pivot 06-08/2026.
WITH demo_products(ma_sap, fallback_name) AS (
    VALUES
        ('10008225', 'Binh nuoc nong GT Lumix dung 20L'),
        ('10006140', 'BNN GT Bravis - Son Ha ngang 15L SHB15N'),
        ('10006141', 'BNN GT Bravis - Son Ha ngang 20L SHB20N')
),
product_names AS (
    SELECT
        p.ma_sap,
        COALESCE(MAX(b.ten_tp_goc), MAX(mb.ten_tp), MAX(p.fallback_name)) AS ten_tp
    FROM demo_products p
    LEFT JOIN bom_tinh_toan b ON b.ma_tp_goc = p.ma_sap
    LEFT JOIN md_sap_bom mb ON mb.ma_tp = p.ma_sap
    GROUP BY p.ma_sap
)
INSERT INTO ma_hang (
    code, ma_sap, ma_nvl, ten_nvl,
    dong_hang_id, nganh_hang_id, don_vi_tinh_id,
    create_uid, write_uid, create_date, write_date
)
SELECT
    'DEMO_MH_' || ma_sap,
    ma_sap,
    ma_sap,
    ten_tp || ' (Demo)',
    (SELECT id FROM dong_hang WHERE code = 'DEMO_GT' LIMIT 1),
    (SELECT id FROM nganh_hang WHERE code = 'DEMO_BNN' LIMIT 1),
    1,
    1, 1, NOW(), NOW()
FROM product_names
ON CONFLICT (ma_sap) DO UPDATE SET
    code = EXCLUDED.code,
    ma_nvl = EXCLUDED.ma_nvl,
    ten_nvl = EXCLUDED.ten_nvl,
    dong_hang_id = EXCLUDED.dong_hang_id,
    nganh_hang_id = EXCLUDED.nganh_hang_id,
    don_vi_tinh_id = EXCLUDED.don_vi_tinh_id,
    write_uid = EXCLUDED.write_uid,
    write_date = NOW();

-- 3. Danh muc NVL union tu BOM cua 3 thanh pham.
WITH nvl_list AS (
    SELECT DISTINCT
        b.ma_con,
        MAX(b.ten_con) AS ten_con
    FROM bom_tinh_toan b
    WHERE b.ma_tp_goc IN ('10008225', '10006140', '10006141')
      AND b.loai_vat_tu = 'NVL'
    GROUP BY b.ma_con
)
INSERT INTO ma_hang (
    code, ma_sap, ma_nvl, ten_nvl,
    don_vi_tinh_id, nganh_hang_id, dong_hang_id,
    create_uid, write_uid, create_date, write_date
)
SELECT
    'NVL_' || ma_con,
    ma_con,
    ma_con,
    ten_con,
    CASE
        WHEN ma_con IN ('20005260', '20005327', '20002660')
          OR ten_con ILIKE '%chat bao on%' THEN 12
        WHEN ten_con ILIKE '%vit%'
          OR ten_con ILIKE '%bu long%'
          OR ten_con ILIKE '%no %'
          OR ten_con ILIKE '%tem%' THEN 13
        WHEN ten_con ILIKE '%day%'
          OR ten_con ILIKE '%ong%' THEN 5
        ELSE 1
    END,
    (SELECT id FROM nganh_hang WHERE code = 'DEMO_BNN' LIMIT 1),
    (SELECT id FROM dong_hang WHERE code = 'DEMO_GT' LIMIT 1),
    1, 1, NOW(), NOW()
FROM nvl_list
ON CONFLICT (ma_sap) DO UPDATE SET
    code = EXCLUDED.code,
    ma_nvl = EXCLUDED.ma_nvl,
    ten_nvl = EXCLUDED.ten_nvl,
    don_vi_tinh_id = EXCLUDED.don_vi_tinh_id,
    nganh_hang_id = EXCLUDED.nganh_hang_id,
    dong_hang_id = EXCLUDED.dong_hang_id,
    write_uid = EXCLUDED.write_uid,
    write_date = NOW();

-- 4. Ky ke hoach SHE bat dau tu thang 06/2026.
INSERT INTO ke_hoach_vat_tu (code, period_month, state, company_id, create_uid, write_uid, create_date, write_date)
VALUES ('KHVT_SHE_0001', '06/2026', 'ke_hoach', 17, 1, 1, NOW(), NOW());

-- 5. Ke hoach kinh doanh multi-month.
WITH demand(ma_sap, month_key, month_date, qty) AS (
    VALUES
        ('10008225', '06/2026', DATE '2026-06-01', 1000.0),
        ('10006140', '07/2026', DATE '2026-07-01', 800.0),
        ('10006141', '08/2026', DATE '2026-08-01', 1200.0)
)
INSERT INTO ke_hoach_kinh_doanh (
    period_id, nganh_hang_id, dong_hang_id,
    ma_hang_id, ma_sap, month_key, month_date, qty,
    create_uid, write_uid, create_date, write_date
)
SELECT
    (SELECT id FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001' LIMIT 1),
    mh.nganh_hang_id,
    mh.dong_hang_id,
    mh.id,
    d.ma_sap,
    d.month_key,
    d.month_date,
    d.qty,
    1, 1, NOW(), NOW()
FROM demand d
JOIN ma_hang mh ON mh.ma_sap = d.ma_sap;

-- 6. Ke hoach san xuat demo mirror tu kinh doanh, san xuat boi SSP/BNH.
INSERT INTO ke_hoach_san_xuat (
    period_id, company_id, nganh_hang_id, dong_hang_id,
    ma_hang_id, ma_sap, month_key, month_date, qty,
    create_uid, write_uid, create_date, write_date
)
SELECT
    kd.period_id,
    COALESCE(
        (SELECT id FROM res_company WHERE company_code = 'SSP' LIMIT 1),
        (SELECT id FROM res_company WHERE company_code = 'BNH' LIMIT 1),
        p.company_id
    ),
    kd.nganh_hang_id,
    kd.dong_hang_id,
    kd.ma_hang_id,
    kd.ma_sap,
    kd.month_key,
    kd.month_date,
    kd.qty,
    1, 1, NOW(), NOW()
FROM ke_hoach_kinh_doanh kd
JOIN ke_hoach_vat_tu p ON p.id = kd.period_id
WHERE p.code = 'KHVT_SHE_0001';

-- Dung tai day: demo chi nap ke hoach kinh doanh va ke hoach san xuat.
-- Cac buoc B1-B5 de nguoi dung tu bam nut tren UI de kiem thu dung luong nghiep vu.

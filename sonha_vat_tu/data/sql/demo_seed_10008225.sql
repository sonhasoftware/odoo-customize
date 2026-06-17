-- ============================================================
-- Demo multi-month cho báo cáo nhu cầu vật tư / pivot
-- Chứng từ: KHVT_SHE_0001
-- Đơn vị lập nhu cầu: SHE
-- Đơn vị sản xuất demo: SSP (fallback BNH nếu không có SSP)
-- Script chỉ nạp kế hoạch kinh doanh và kế hoạch sản xuất.
-- Các bước B1-B5 để người dùng tự bấm nút trên UI.
-- ============================================================

WITH demo_period AS (
    SELECT id FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001'
)
DELETE FROM du_lieu_tong_hop_vat_tu WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001'
)
DELETE FROM kh_dat_vat_tu WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001'
)
DELETE FROM tong_hop_vat_tu WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001'
)
DELETE FROM tinh_toan_vat_tu WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001'
)
DELETE FROM dinh_muc WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001'
)
DELETE FROM ke_hoach_vat_tu_line WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001'
)
DELETE FROM ke_hoach_san_xuat WHERE period_id IN (SELECT id FROM demo_period);

WITH demo_period AS (
    SELECT id FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001'
)
DELETE FROM ke_hoach_kinh_doanh WHERE period_id IN (SELECT id FROM demo_period);

DELETE FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001';

-- Kỳ kế hoạch SHE bắt đầu từ tháng 06/2026.
INSERT INTO ke_hoach_vat_tu (
    code, period_month, state, approval_state, approval_current_sequence,
    company_id, create_uid, write_uid, create_date, write_date
)
SELECT
    'KHVT_SHE_0001',
    '06/2026',
    'ke_hoach',
    'draft',
    0,
    c.id,
    1, 1, NOW(), NOW()
FROM res_company c
WHERE c.company_code = 'SHE'
LIMIT 1;

-- Kế hoạch kinh doanh multi-month.
WITH demand(ma_sap, dong_hang, month_key, month_date, qty) AS (
    VALUES
        ('10002685', 'Dong SSP 22 (Demo)', '06/2026', DATE '2026-06-01', 1000.0),
        ('10003848', 'Dong SSP 22 (Demo)', '07/2026', DATE '2026-07-01', 800.0),
        ('10003998', 'Dong SSP 22 (Demo)', '08/2026', DATE '2026-08-01', 1200.0)
)
INSERT INTO ke_hoach_kinh_doanh (
    period_id, nganh_hang, dong_hang, ma_hang_id, ma_sap,
    month_key, month_date, qty, create_uid, write_uid, create_date, write_date
)
SELECT
    p.id,
    COALESCE(mh.nganh_hang, 'Binh nuoc nong (Demo)'),
    d.dong_hang,
    mh.id,
    d.ma_sap,
    d.month_key,
    d.month_date,
    d.qty,
    1, 1, NOW(), NOW()
FROM demand d
JOIN ke_hoach_vat_tu p ON p.code = 'KHVT_SHE_0001'
JOIN ma_hang mh ON mh.ma_sap = d.ma_sap;

-- Kế hoạch sản xuất demo mirror từ kinh doanh, sản xuất bởi SSP/BNH.
INSERT INTO ke_hoach_san_xuat (
    period_id, company_id, nganh_hang, dong_hang, ma_hang_id, ma_sap,
    month_key, month_date, qty, create_uid, write_uid, create_date, write_date
)
SELECT
    kd.period_id,
    COALESCE(ssp.id, bnh.id, p.company_id),
    kd.nganh_hang,
    kd.dong_hang,
    kd.ma_hang_id,
    kd.ma_sap,
    kd.month_key,
    kd.month_date,
    kd.qty,
    1, 1, NOW(), NOW()
FROM ke_hoach_kinh_doanh kd
JOIN ke_hoach_vat_tu p ON p.id = kd.period_id
LEFT JOIN res_company ssp ON ssp.company_code = 'SSP'
LEFT JOIN res_company bnh ON bnh.company_code = 'BNH'
WHERE p.code = 'KHVT_SHE_0001';

-- Vật tư đi đường demo cho các mã NVL sinh ra từ BOM của bộ demo.
-- Bước 4 sẽ match theo công ty sản xuất và mã NVL.
WITH demo_vdd_keys(ma_nvl, month_key) AS (
    VALUES
        ('20000026', '06/2026'),
        ('20000026', '07/2026'),
        ('20000026', '08/2026'),
        ('20000038', '06/2026'),
        ('20000094', '06/2026'),
        ('20000094', '07/2026'),
        ('20000177', '06/2026'),
        ('20000177', '08/2026'),
        ('11002356', '06/2026'),
        ('11002360', '06/2026'),
        ('25000038', '06/2026'),
        ('11002495', '07/2026'),
        ('11002498', '07/2026'),
        ('25000038', '07/2026'),
        ('11002889', '08/2026'),
        ('11002890', '08/2026'),
        ('25000033', '08/2026')
)
DELETE FROM vat_tu_di_duong v
USING res_company c, demo_vdd_keys d
WHERE v.company_id = c.id
  AND c.company_code = 'SSP'
  AND v.ma_nvl = d.ma_nvl
  AND v.month_key = d.month_key;

WITH demo_vdd(company_code, pr_number, ma_nvl, month_key, month_date, so_luong) AS (
    VALUES
        ('SSP', 'PR-DEMO-0626', '11002356', '06/2026', DATE '2026-06-01', 100.0),
        ('SSP', 'PR-DEMO-0626', '11002360', '06/2026', DATE '2026-06-01', 200.0),
        ('SSP', 'PR-DEMO-0626', '25000038', '06/2026', DATE '2026-06-01', 300.0),
        ('SSP', 'PR-DEMO-0726', '11002495', '07/2026', DATE '2026-07-01', 150.0),
        ('SSP', 'PR-DEMO-0726', '11002498', '07/2026', DATE '2026-07-01', 250.0),
        ('SSP', 'PR-DEMO-0726', '25000038', '07/2026', DATE '2026-07-01', 100.0),
        ('SSP', 'PR-DEMO-0826', '11002889', '08/2026', DATE '2026-08-01', 80.0),
        ('SSP', 'PR-DEMO-0826', '11002890', '08/2026', DATE '2026-08-01', 120.0),
        ('SSP', 'PR-DEMO-0826', '25000033', '08/2026', DATE '2026-08-01', 60.0)
)
INSERT INTO vat_tu_di_duong (
    company_id, pr_number, ma_nvl, ten_nvl, month_key, month_date,
    so_luong, create_uid, write_uid, create_date, write_date
)
SELECT
    c.id,
    d.pr_number,
    d.ma_nvl,
    mh.ten_hang,
    d.month_key,
    d.month_date,
    d.so_luong,
    1, 1, NOW(), NOW()
FROM demo_vdd d
JOIN res_company c ON c.company_code = d.company_code
LEFT JOIN ma_hang mh ON mh.ma_sap = d.ma_nvl
ON CONFLICT (company_id, ma_nvl, month_key, pr_number) DO UPDATE SET
    pr_number = EXCLUDED.pr_number,
    ten_nvl = EXCLUDED.ten_nvl,
    month_date = EXCLUDED.month_date,
    so_luong = EXCLUDED.so_luong,
    write_uid = EXCLUDED.write_uid,
    write_date = EXCLUDED.write_date;

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

-- Đồng bộ cache mã hàng từ MDM để các dòng demo và các bước tính toán có đủ tên/đơn vị tính.
INSERT INTO ma_hang (
    mdm_line_id, mdm_id, ma_mdm, ma_sap, ten_hang,
    don_vi_tinh_id, bom_sale_id, company_id, nganh_hang,
    active, create_uid, write_uid, create_date, write_date
)
SELECT
    l.id,
    l.tong_hop_id,
    l.ma_mdm,
    TRIM(l.ma_dv),
    th.ten,
    l.dvt,
    l.bom_sale,
    l.dvcs,
    nh.ten,
    TRUE,
    1, 1, NOW(), NOW()
FROM mdm_tong_hop_line l
LEFT JOIN mdm_tong_hop th ON th.id = l.tong_hop_id
LEFT JOIN mdm_nganh_hang nh ON nh.id = th.nganh_hang
WHERE l.ma_dv IS NOT NULL
  AND TRIM(l.ma_dv) != ''
ON CONFLICT (ma_sap) DO UPDATE SET
    mdm_line_id = EXCLUDED.mdm_line_id,
    mdm_id = EXCLUDED.mdm_id,
    ma_mdm = EXCLUDED.ma_mdm,
    ten_hang = EXCLUDED.ten_hang,
    don_vi_tinh_id = EXCLUDED.don_vi_tinh_id,
    bom_sale_id = EXCLUDED.bom_sale_id,
    company_id = EXCLUDED.company_id,
    nganh_hang = EXCLUDED.nganh_hang,
    active = TRUE,
    write_uid = 1,
    write_date = NOW();

-- Kỳ kế hoạch SHE bắt đầu từ tháng 06/2026.
INSERT INTO ke_hoach_vat_tu (code, period_month, state, company_id, create_uid, write_uid, create_date, write_date)
SELECT
    'KHVT_SHE_0001',
    '06/2026',
    'ke_hoach',
    c.id,
    1, 1, NOW(), NOW()
FROM res_company c
WHERE c.company_code = 'SHE'
LIMIT 1;

-- Kế hoạch kinh doanh multi-month.
WITH demand(ma_sap, dong_hang, month_key, month_date, qty) AS (
    VALUES
        ('10008225', 'Dong GT (Demo)', '06/2026', DATE '2026-06-01', 1000.0),
        ('10006140', 'Dong GT (Demo)', '07/2026', DATE '2026-07-01', 800.0),
        ('10006141', 'Dong GT (Demo)', '08/2026', DATE '2026-08-01', 1200.0)
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

-- ============================================================
-- SCRIPT NẠP DỮ LIỆU DEMO ĐẦY ĐỦ CHO MÃ SAP 10008225
-- Bình nước nóng GT Lumix đứng 20L
-- ============================================================

-- ============================================================
-- PHẦN 1: Nạp Dữ liệu Master Data cơ bản (Ngành, Dòng, Kỳ)
-- ============================================================

-- 0. Xóa dữ liệu cũ theo thứ tự để tránh lỗi Khóa ngoại (Foreign Key)
DELETE FROM vat_tu_di_duong WHERE ma_sap IN ('10008225', '20005260') AND month_key = '05/2026';
DELETE FROM ke_hoach_vat_tu_line WHERE ma_sap = '10008225' AND month_key = '05/2026';
DELETE FROM ke_hoach_san_xuat WHERE ma_sap = '10008225' AND month_key = '05/2026';
DELETE FROM ke_hoach_kinh_doanh WHERE ma_sap = '10008225' AND month_key = '05/2026';
DELETE FROM ke_hoach_vat_tu
WHERE period_month = '05/2026'
  AND (code IN ('KHVT_BNH_0001', 'KHVT_SHE_0001') OR company_id = 5);

-- Xóa toàn bộ mã hàng NVL thuộc cây 10008225 trước khi xóa dòng hàng
DELETE FROM ma_hang WHERE ma_sap IN (
    SELECT DISTINCT ma_con FROM bom_tinh_toan 
    WHERE ma_tp_goc = '10008225' AND loai_vat_tu = 'NVL'
);

-- Xóa mã gốc và Danh mục
DELETE FROM ma_hang WHERE code = 'DEMO_MH_10008225';
DELETE FROM dong_hang WHERE code = 'DEMO_GT';
DELETE FROM nganh_hang WHERE code = 'DEMO_BNN';
-- 1. Ngành Hàng
INSERT INTO nganh_hang (code, name, create_uid, write_uid, create_date, write_date)
VALUES ('DEMO_BNN', 'Bình nước nóng (Demo)', 1, 1, NOW(), NOW());

-- 2. Dòng Hàng
INSERT INTO dong_hang (code, name, nganh_hang_id, create_uid, write_uid, create_date, write_date)
VALUES ('DEMO_GT', 'Dòng GT (Demo)', (SELECT id FROM nganh_hang WHERE code = 'DEMO_BNN' LIMIT 1), 1, 1, NOW(), NOW());

-- 3. Mã Hàng Thành Phẩm Gốc
INSERT INTO ma_hang (code, ma_sap, ma_nvl, ten_nvl, dong_hang_id, nganh_hang_id, don_vi_tinh_id, create_uid, write_uid, create_date, write_date)
VALUES (
    'DEMO_MH_10008225', '10008225', '10008225', 'Bình nước nóng GT Lumix đứng 20L (Demo)', 
    (SELECT id FROM dong_hang WHERE code = 'DEMO_GT' LIMIT 1), 
    (SELECT id FROM nganh_hang WHERE code = 'DEMO_BNN' LIMIT 1),
    1, 1, 1, NOW(), NOW()
);

-- 4. Kỳ Kế Hoạch & Kế hoạch thành phẩm
INSERT INTO ke_hoach_vat_tu (code, period_month, state, company_id, create_uid, write_uid, create_date, write_date)
VALUES ('KHVT_SHE_0001', '05/2026', 'ke_hoach', 17, 1, 1, NOW(), NOW());

INSERT INTO ke_hoach_kinh_doanh (
    period_id, nganh_hang_id, dong_hang_id,
    ma_hang_id, ma_sap, month_key, month_date, qty,
    create_uid, write_uid, create_date, write_date
)
VALUES (
    (SELECT id FROM ke_hoach_vat_tu WHERE code = 'KHVT_SHE_0001' AND period_month = '05/2026' LIMIT 1),
    (SELECT id FROM nganh_hang WHERE code = 'DEMO_BNN' LIMIT 1),
    (SELECT id FROM dong_hang WHERE code = 'DEMO_GT' LIMIT 1),
    (SELECT id FROM ma_hang WHERE code = 'DEMO_MH_10008225' LIMIT 1),
    '10008225', '05/2026', DATE '2026-05-01', 1000,
    1, 1, NOW(), NOW()
);



-- 5. Vật tư đi đường
INSERT INTO vat_tu_di_duong (company_id, ma_sap, month_key, month_date, so_luong, create_uid, write_uid, create_date, write_date)
VALUES (5, '10008225', '05/2026', DATE '2026-05-01', 500, 1, 1, NOW(), NOW());


-- ============================================================
-- PHẦN 2: Nạp đầy đủ ma_hang cho 62 mã NVL
-- ============================================================
-- Insert đầy đủ 62 mã NVL
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
        -- Thép, Men, Chất bảo ôn → kg (12)
        WHEN ma_con IN ('20005260','20005327','20002660') OR ten_con ILIKE '%chất bảo ôn%' THEN 12
        -- Ốc vít, bulong, nở, tem → g (13)
        WHEN ten_con ILIKE '%vít%' OR ten_con ILIKE '%bu lông%' OR ten_con ILIKE '%nở%' OR ten_con ILIKE '%tem%' THEN 13
        -- Dây điện, ống → m (5)
        WHEN ten_con ILIKE '%dây%' OR ten_con ILIKE '%ống%' THEN 5
        -- Còn lại (Nắp, Xốp, Thùng, Phiếu, Van...) → Đơn vị (1)
        ELSE 1
    END,
    (SELECT nganh_hang_id FROM ma_hang WHERE ma_sap = '10008225' LIMIT 1), -- Kế thừa Ngành hàng
    (SELECT dong_hang_id FROM ma_hang WHERE ma_sap = '10008225' LIMIT 1),  -- Kế thừa Dòng hàng
    1, 1, NOW(), NOW()
FROM (
    SELECT DISTINCT ma_con, ten_con 
    FROM bom_tinh_toan 
    WHERE ma_tp_goc = '10008225' 
      AND loai_vat_tu = 'NVL'
) nvl_list
WHERE ma_con NOT IN (SELECT ma_sap FROM ma_hang);


-- ============================================================
-- PHẦN 3: Cập nhật do_day, kho_1, kho_2 trong bảng bom
-- ============================================================
-- 1. Cập nhật số chuẩn cho các mã kim loại
UPDATE bom SET do_day = 1.5, kho_1 = 985, kho_2 = 1000 WHERE ma_nvl = '20005260';
UPDATE bom SET do_day = 1.5, kho_1 = 945, kho_2 = 1000 WHERE ma_nvl = '20005327';
UPDATE bom SET do_day = 0.8, kho_1 = 25, kho_2 = 130 WHERE ma_nvl = '20009770';
UPDATE bom SET do_day = 0.8, kho_1 = 25, kho_2 = 120 WHERE ma_nvl = '20000772';

-- 2. Đổ random kích thước cho TẤT CẢ các mã còn lại (cho đẹp đội hình demo)
UPDATE bom 
SET do_day = ROUND((RANDOM() * 2 + 0.1)::numeric, 2), -- từ 0.1 đến 2.1
    kho_1 = FLOOR(RANDOM() * 100 + 10),               -- từ 10 đến 110
    kho_2 = FLOOR(RANDOM() * 100 + 10)
WHERE ma_tp IN (SELECT DISTINCT ma_tp_cha FROM bom_tinh_toan WHERE ma_tp_goc = '10008225')
  AND do_day = 0; -- Chỉ update những thằng đang bằng 0

-- ============================================================
-- Danh muc ma hang: MDM bom_sale 1C (menu + validate import/tạo KHKD/KHSX).
-- ============================================================

DROP TRIGGER IF EXISTS trg_mdm_parent_sync_ma_hang_au ON mdm_tong_hop;
DROP TRIGGER IF EXISTS trg_mdm_line_sync_ma_hang_aiu ON mdm_tong_hop_line;
DROP FUNCTION IF EXISTS trg_sync_ma_hang_from_mdm_parent();
DROP FUNCTION IF EXISTS trg_sync_ma_hang_from_mdm_line();

DROP VIEW IF EXISTS ma_hang CASCADE;
DROP TABLE IF EXISTS ma_hang CASCADE;

CREATE OR REPLACE VIEW ma_hang AS
SELECT
    l.id                                    AS id,
    l.id                                    AS mdm_line_id,
    l.tong_hop_id                           AS mdm_id,
    l.ma_mdm                                AS ma_mdm,
    TRIM(l.ma_dv)                           AS ma_sap,
    COALESCE(l.ten, th.ten)                 AS ten_hang,
    l.dvt                                   AS don_vi_tinh_id,
    l.bom_sale                              AS bom_sale_id,
    l.dvcs                                  AS company_id,
    nh.ten                                  AS nganh_hang,
    nh.id                                   AS nganh_hang_id,
    TRUE                                    AS active,
    COALESCE(l.create_uid, 1)               AS create_uid,
    COALESCE(l.write_uid, 1)               AS write_uid,
    COALESCE(l.create_date, NOW() AT TIME ZONE 'UTC') AS create_date,
    COALESCE(l.write_date, NOW() AT TIME ZONE 'UTC')  AS write_date
FROM mdm_tong_hop_line l
INNER JOIN mdm_tong_hop th ON th.id = l.tong_hop_id
INNER JOIN bom_sale bs ON bs.id = l.bom_sale AND bs.ma = '1C'
LEFT JOIN mdm_nganh_hang nh ON nh.id = th.nganh_hang
WHERE l.ma_dv IS NOT NULL
  AND TRIM(l.ma_dv) <> '';

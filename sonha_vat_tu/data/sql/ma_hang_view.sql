-- Danh muc ma.hang Odoo: doc tu view QL v_mdm_hang_hoa_bcu + join line (id, DVT, DVCS).

CREATE OR REPLACE VIEW ma_hang AS
SELECT DISTINCT ON (l.id)
    l.id                                    AS id,
    l.id                                    AS mdm_line_id,
    l.tong_hop_id                           AS mdm_id,
    v.ma_mdm                                AS ma_mdm,
    TRIM(v.ma_dv)                           AS ma_sap,
    COALESCE(v.ten_dv, l.ten)               AS ten_hang,
    l.dvt                                   AS don_vi_tinh_id,
    bs.id                                   AS bom_sale_id,
    l.dvcs                                  AS company_id,
    v.ten_nganh_hang                        AS nganh_hang,
    nh.id                                   AS nganh_hang_id,
    TRUE                                    AS active,
    COALESCE(l.create_uid, 1)               AS create_uid,
    COALESCE(l.write_uid, 1)               AS write_uid,
    COALESCE(l.create_date, NOW() AT TIME ZONE 'UTC') AS create_date,
    COALESCE(l.write_date, NOW() AT TIME ZONE 'UTC')  AS write_date
FROM v_mdm_hang_hoa_bcu v
INNER JOIN mdm_tong_hop_line l
    ON TRIM(l.ma_dv) = TRIM(v.ma_dv)
LEFT JOIN bom_sale bs
    ON bs.ma = v.ma_bom_sale
LEFT JOIN mdm_tong_hop th
    ON th.id = l.tong_hop_id
LEFT JOIN mdm_nganh_hang nh
    ON nh.id = th.nganh_hang
ORDER BY l.id, v.ma_mdm;

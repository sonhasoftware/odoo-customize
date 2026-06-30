-- ============================================================
-- Sync ma_hang from MDM.
-- ============================================================

CREATE OR REPLACE FUNCTION public.fn_sync_ma_hang_from_mdm_line(p_line_id INTEGER)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
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
        l.ten,
        l.dvt,
        l.bom_sale,
        l.dvcs,
        nh.ten,
        TRUE,
        1, 1, NOW(), NOW()
    FROM mdm_tong_hop_line l
    LEFT JOIN mdm_tong_hop th ON th.id = l.tong_hop_id
    LEFT JOIN mdm_nganh_hang nh ON nh.id = th.nganh_hang
    WHERE l.id = p_line_id
      AND l.ma_dv IS NOT NULL
      AND TRIM(l.ma_dv) != ''
    ON CONFLICT (mdm_line_id) DO UPDATE SET
        mdm_id = EXCLUDED.mdm_id,
        ma_mdm = EXCLUDED.ma_mdm,
        ma_sap = EXCLUDED.ma_sap,
        ten_hang = EXCLUDED.ten_hang,
        don_vi_tinh_id = EXCLUDED.don_vi_tinh_id,
        bom_sale_id = EXCLUDED.bom_sale_id,
        company_id = EXCLUDED.company_id,
        nganh_hang = EXCLUDED.nganh_hang,
        active = TRUE,
        write_uid = 1,
        write_date = NOW();
END;
$$;

CREATE OR REPLACE FUNCTION public.trg_sync_ma_hang_from_mdm_line()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND OLD.ma_dv IS NOT NULL
       AND TRIM(OLD.ma_dv) != ''
       AND (NEW.ma_dv IS NULL OR TRIM(NEW.ma_dv) = '' OR TRIM(NEW.ma_dv) != TRIM(OLD.ma_dv)) THEN
        UPDATE ma_hang
           SET active = FALSE,
               write_uid = 1,
               write_date = NOW()
         WHERE mdm_line_id = OLD.id;
    END IF;

    IF NEW.ma_dv IS NOT NULL AND TRIM(NEW.ma_dv) != '' THEN
        PERFORM public.fn_sync_ma_hang_from_mdm_line(NEW.id);
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_mdm_line_sync_ma_hang_aiu ON mdm_tong_hop_line;
CREATE TRIGGER trg_mdm_line_sync_ma_hang_aiu
AFTER INSERT OR UPDATE OF ma_mdm, ma_dv, dvcs, tong_hop_id, ten, dvt, bom_sale
ON mdm_tong_hop_line
FOR EACH ROW
EXECUTE FUNCTION public.trg_sync_ma_hang_from_mdm_line();

CREATE OR REPLACE FUNCTION public.trg_sync_ma_hang_from_mdm_parent()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE ma_hang mh
       SET ten_hang = l.ten,
           don_vi_tinh_id = l.dvt,
           bom_sale_id = l.bom_sale,
           nganh_hang = nh.ten,
           write_uid = 1,
           write_date = NOW()
      FROM mdm_tong_hop_line l
      LEFT JOIN mdm_nganh_hang nh ON nh.id = NEW.nganh_hang
     WHERE l.tong_hop_id = NEW.id
       AND mh.mdm_line_id = l.id;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_mdm_parent_sync_ma_hang_au ON mdm_tong_hop;
CREATE TRIGGER trg_mdm_parent_sync_ma_hang_au
AFTER UPDATE OF ten, dvt, bom_sale, nganh_hang
ON mdm_tong_hop
FOR EACH ROW
EXECUTE FUNCTION public.trg_sync_ma_hang_from_mdm_parent();

-- Full sync existing MDM data when installing/upgrading the module.
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
    l.ten,
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
ON CONFLICT (mdm_line_id) DO UPDATE SET
    mdm_id = EXCLUDED.mdm_id,
    ma_mdm = EXCLUDED.ma_mdm,
    ma_sap = EXCLUDED.ma_sap,
    ten_hang = EXCLUDED.ten_hang,
    don_vi_tinh_id = EXCLUDED.don_vi_tinh_id,
    bom_sale_id = EXCLUDED.bom_sale_id,
    company_id = EXCLUDED.company_id,
    nganh_hang = EXCLUDED.nganh_hang,
    active = TRUE,
    write_uid = 1,
    write_date = NOW();

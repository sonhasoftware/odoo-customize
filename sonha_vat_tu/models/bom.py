# -*- coding: utf-8 -*-
import os as _os
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_SAP_BOM_TRIGGER_SQL = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    'data', 'bc_triggers.sql',
)


class Bom(models.Model):
    _name = 'bom'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'BOM'
    _rec_name = 'ma_tp'
    _order = 'company_id, ma_tp, ma_nvl'

    ma_tp = fields.Char(string='Mã thành phẩm', index=True)
    ten_tp = fields.Char(string='Tên thành phẩm')
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True,
        default=lambda self: self.env.company)
    sl_dinh_muc = fields.Float(
        string='Số lượng định mức / 1 sản phẩm', digits=(16, 3), default=0.0)
    do_day = fields.Float(string='Độ dày', digits=(16, 2))
    kho_1 = fields.Float(string='Khổ 1', digits=(16, 0))
    kho_2 = fields.Float(string='Khổ 2', digits=(16, 0))

    _sql_constraints = [
        ('uniq_company_tp_nvl', 'unique(company_id, ma_tp, ma_nvl)',
         'BOM đã tồn tại theo đơn vị, mã thành phẩm và mã NVL!'),
    ]

    def action_download_bom_template(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/sonha_vat_tu/static/xls/bom_templates.xlsx',
            'target': 'self',
        }

    def action_open_import_bom_wizard(self):
        return {
            'name': _('Import BOM'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.bom.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_company_id': self.env.company.id,
            },
        }

    def action_sync_sap_bom(self):
        """Đồng bộ BOM từ bảng md_sap_bom (SAP API) sang bảng bom.
        1. Đảm bảo trigger tồn tại trên bảng md_sap_bom
        2. Backfill toàn bộ dữ liệu hiện có
        """
        cr = self.env.cr

        # Kiểm tra bảng md_sap_bom tồn tại
        cr.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'md_sap_bom'
        """)
        if not cr.fetchone():
            raise UserError(_(
                'Bảng md_sap_bom chưa tồn tại.\n'
                'Vui lòng vào Cấu hình API SAP và nhấn "Tải dữ liệu" '
                'cho BOM trước.'))

        # Đảm bảo function + trigger tồn tại (re-run từ bc_triggers.sql)
        with open(_SAP_BOM_TRIGGER_SQL, 'r', encoding='utf-8') as f:
            cr.execute(f.read())
        _logger.info('SAP BOM trigger function ensured.')

        # Đảm bảo trigger gắn trên bảng
        cr.execute("""
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'trg_sync_sap_bom'
              AND tgrelid = 'md_sap_bom'::regclass
        """)
        if not cr.fetchone():
            cr.execute("""
                CREATE TRIGGER trg_sync_sap_bom
                AFTER INSERT ON md_sap_bom
                FOR EACH ROW EXECUTE PROCEDURE sync_md_sap_bom_to_bom()
            """)
            _logger.info('Trigger trg_sync_sap_bom created on md_sap_bom.')

        # Backfill: UPSERT dữ liệu hiện có từ md_sap_bom → bom
        v_company_id = self.env.company.id or 17
        # Tạo function helper parse số SAP (xử lý dấu trừ cuối: "0.727-" → -0.727)
        cr.execute("""
            CREATE OR REPLACE FUNCTION safe_sap_numeric(val TEXT)
            RETURNS NUMERIC AS $$
            DECLARE
                cleaned TEXT;
            BEGIN
                IF val IS NULL OR TRIM(val) = '' THEN RETURN 0; END IF;
                cleaned := TRIM(val);
                -- SAP format: dấu trừ ở cuối, vd "0.727-" → "-0.727"
                IF cleaned LIKE '%-' THEN
                    cleaned := '-' || LEFT(cleaned, LENGTH(cleaned) - 1);
                END IF;
                -- Loại bỏ ký tự không phải số/dấu chấm/dấu trừ
                cleaned := regexp_replace(cleaned, '[^0-9.\-]', '', 'g');
                IF cleaned = '' OR cleaned = '-' THEN RETURN 0; END IF;
                RETURN cleaned::NUMERIC;
            EXCEPTION WHEN OTHERS THEN
                RETURN 0;
            END;
            $$ LANGUAGE plpgsql IMMUTABLE;
        """)

        cr.execute("""
            INSERT INTO bom (company_id, ma_tp, ten_tp, ma_nvl, ten_nvl,
                             sl_dinh_muc, do_day, kho_1, kho_2,
                             create_uid, create_date, write_uid, write_date)
            SELECT
                %(company_id)s,
                d.ma_tp, d.ten_tp, d.ma_nvl, d.ten_nvl,
                d.sl_dm_num,
                0, 0, 0,
                1, NOW() AT TIME ZONE 'UTC',
                1, NOW() AT TIME ZONE 'UTC'
            FROM (
                SELECT DISTINCT ON (TRIM(s.ma_tp), TRIM(s.ma_nvl))
                    TRIM(s.ma_tp) AS ma_tp,
                    COALESCE(NULLIF(TRIM(s.ten_tp), ''), TRIM(s.ma_tp)) AS ten_tp,
                    TRIM(s.ma_nvl) AS ma_nvl,
                    COALESCE(NULLIF(TRIM(s.ten_nvl), ''), TRIM(s.ma_nvl)) AS ten_nvl,
                    safe_sap_numeric(s.sl_dm) AS sl_dm_num
                FROM md_sap_bom s
                WHERE s.ma_tp IS NOT NULL AND TRIM(s.ma_tp) != ''
                  AND s.ma_nvl IS NOT NULL AND TRIM(s.ma_nvl) != ''
                ORDER BY TRIM(s.ma_tp), TRIM(s.ma_nvl), s.id DESC
            ) d
            ON CONFLICT (company_id, ma_tp, ma_nvl) DO UPDATE SET
                ten_tp = COALESCE(NULLIF(EXCLUDED.ten_tp, ''), bom.ten_tp),
                ten_nvl = COALESCE(NULLIF(EXCLUDED.ten_nvl, ''), bom.ten_nvl),
                sl_dinh_muc = EXCLUDED.sl_dinh_muc,
                write_date = NOW() AT TIME ZONE 'UTC'
        """, {'company_id': v_company_id})

        synced = cr.rowcount
        _logger.info('SAP BOM sync: %d rows upserted into bom.', synced)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đồng bộ BOM từ SAP'),
                'message': _('Đã đồng bộ %d dòng BOM từ SAP.') % synced,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

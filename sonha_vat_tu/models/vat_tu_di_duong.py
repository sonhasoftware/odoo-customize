# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class VatTuDiDuong(models.Model):
    _name = 'vat.tu.di.duong'
    _description = 'Vật tư đi đường'
    _order = 'company_id, month_date, ma_nvl'

    company_id = fields.Many2one(
        'res.company',
        string='Đơn vị',
        default=lambda self: self.env.company,
        index=True,
        help='Đơn vị nhận vật tư đi đường.',
    )
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL', index=True)
    month_key = fields.Char(string='Tháng', index=True)
    month_date = fields.Date(string='Tháng tính toán', index=True)
    so_luong = fields.Float(string='Số lượng', digits=(16, 3))

    _sql_constraints = [
        (
            'uniq_vdd_company_nvl_month',
            'unique(company_id, ma_nvl, month_key)',
            'Đã có dòng vật tư đi đường cho cùng Đơn vị, Mã NVL và Tháng.',
        ),
    ]

    def _get_ten_nvl(self, ma_nvl):
        if not ma_nvl:
            return False
        master = self.env['ma.hang'].search([('ma_sap', '=', ma_nvl)], limit=1)
        return master.ten_hang or False

    @api.onchange('ma_nvl')
    def _onchange_ma_nvl(self):
        for rec in self:
            rec.ten_nvl = rec._get_ten_nvl(rec.ma_nvl) or rec.ten_nvl

    @api.constrains('month_key')
    def _check_month_key(self):
        pattern = re.compile(r'^(0[1-9]|1[0-2])/\d{4}$')
        for rec in self:
            if rec.month_key and not pattern.match(rec.month_key):
                raise ValidationError('Tháng phải đúng định dạng MM/YYYY, ví dụ 04/2026.')

    @api.model_create_multi
    def create(self, vals_list):
        Period = self.env['ke.hoach.vat.tu']
        for vals in vals_list:
            if vals.get('month_key') and not vals.get('month_date'):
                vals['month_date'] = Period._month_key_to_date(vals['month_key'])
            if vals.get('ma_nvl') and not vals.get('ten_nvl'):
                vals['ten_nvl'] = self._get_ten_nvl(vals['ma_nvl'])
        return super().create(vals_list)

    def write(self, vals):
        if 'month_key' in vals:
            vals = dict(vals)
            vals['month_date'] = self.env['ke.hoach.vat.tu']._month_key_to_date(vals.get('month_key'))
        if vals.get('ma_nvl') and not vals.get('ten_nvl'):
            vals = dict(vals)
            vals['ten_nvl'] = self._get_ten_nvl(vals['ma_nvl'])
        return super().write(vals)

    def action_open_import_wizard(self):
        return {
            'name': _('Import vật tư đi đường'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.vat.tu.di.duong.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def init(self):
        """Gỡ cột pr_number (legacy) và gom dòng trùng trước unique mới."""
        cr = self._cr
        cr.execute("""
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_name = 'vat_tu_di_duong'
              AND constraint_name = 'uniq_vdd_company_nvl_month_pr'
        """)
        if cr.fetchone():
            cr.execute(
                'ALTER TABLE vat_tu_di_duong DROP CONSTRAINT uniq_vdd_company_nvl_month_pr'
            )
        cr.execute("""
            WITH dups AS (
                SELECT company_id, ma_nvl, month_key,
                       MIN(id) AS keep_id, SUM(so_luong) AS total_qty
                FROM vat_tu_di_duong
                GROUP BY company_id, ma_nvl, month_key
                HAVING COUNT(*) > 1
            )
            UPDATE vat_tu_di_duong v SET so_luong = d.total_qty
            FROM dups d
            WHERE v.id = d.keep_id
        """)
        cr.execute("""
            DELETE FROM vat_tu_di_duong v
            USING vat_tu_di_duong v2
            WHERE v.company_id = v2.company_id
              AND v.ma_nvl = v2.ma_nvl
              AND v.month_key = v2.month_key
              AND v.id > v2.id
        """)
        cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'vat_tu_di_duong' AND column_name = 'pr_number'
        """)
        if cr.fetchone():
            cr.execute('ALTER TABLE vat_tu_di_duong DROP COLUMN pr_number')

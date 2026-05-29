# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KeHoachVatTuLine(models.Model):
    _name = 'ke.hoach.vat.tu.line'
    _description = 'Ke hoach vat tu chot'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id, company_id, month_date, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Ky', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Cong ty san xuat', index=True)
    nganh_hang_id = fields.Many2one(
        'nganh.hang', string='Nganh hang', index=True)
    dong_hang_id = fields.Many2one(
        'dong.hang', string='Dong hang', index=True)
    ma_hang_id = fields.Many2one(
        'ma.hang', string='Ma hang', index=True)
    ma_sap = fields.Char(string='Ma SAP', index=True)
    month_key = fields.Char(string='Thang', index=True)
    month_date = fields.Date(string='Thang tinh toan', index=True)
    qty_kinh_doanh = fields.Float(string='So luong kinh doanh', digits=(16, 2))
    qty_san_xuat = fields.Float(string='So luong san xuat', digits=(16, 2))
    qty_chenh_lech = fields.Float(
        string='Chenh lech',
        compute='_compute_qty_chenh_lech',
        store=True,
        digits=(16, 2),
    )
    qty = fields.Float(string='So luong tinh toan', digits=(16, 2))
    note = fields.Char(string='Ghi chu')

    _sql_constraints = [
        ('uniq_material_plan_row',
         'unique(period_id, company_id, ma_hang_id, ma_sap, month_key)',
         'Trung dong ke hoach vat tu chot!'),
    ]

    @api.depends('qty_kinh_doanh', 'qty_san_xuat')
    def _compute_qty_chenh_lech(self):
        for rec in self:
            rec.qty_chenh_lech = (rec.qty_san_xuat or 0.0) - (rec.qty_kinh_doanh or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        Period = self.env['ke.hoach.vat.tu']
        MaHang = self.env['ma.hang']
        for vals in vals_list:
            if vals.get('period_id'):
                period = Period.browse(vals['period_id'])
                if period.state != 'ke_hoach':
                    raise UserError(_('Ke hoach vat tu da khoa vi ky ke hoach da sang buoc sau.'))
            if vals.get('month_key') and not vals.get('month_date'):
                vals['month_date'] = Period._month_key_to_date(vals['month_key'])
            if vals.get('ma_hang_id'):
                master = MaHang.browse(vals['ma_hang_id'])
                vals.setdefault('ma_sap', master.ma_sap)
                vals.setdefault('nganh_hang_id', master.nganh_hang_id.id)
                vals.setdefault('dong_hang_id', master.dong_hang_id.id)
            if 'qty_san_xuat' in vals and 'qty' not in vals:
                vals['qty'] = vals.get('qty_san_xuat') or 0.0
        return super().create(vals_list)

    def write(self, vals):
        self._check_period_editable()
        if 'month_key' in vals:
            vals = dict(vals)
            vals['month_date'] = self.env['ke.hoach.vat.tu']._month_key_to_date(vals.get('month_key'))
        if 'qty_san_xuat' in vals and 'qty' not in vals:
            vals = dict(vals)
            vals['qty'] = vals.get('qty_san_xuat') or 0.0
        return super().write(vals)

    def unlink(self):
        self._check_period_editable()
        return super().unlink()

    def _check_period_editable(self):
        if self.env.context.get('skip_period_lock'):
            return
        locked = self.filtered(lambda rec: rec.period_id and rec.period_id.state != 'ke_hoach')
        if locked:
            raise UserError(_('Ke hoach vat tu da khoa vi ky ke hoach da sang buoc sau.'))

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KeHoachVatTuLine(models.Model):
    _name = 'ke.hoach.vat.tu.line'
    _description = 'Kế hoạch vật tư chốt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id, company_id, month_date, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty sản xuất', index=True)
    nganh_hang_id = fields.Many2one(
        'nganh.hang', string='Ngành hàng', index=True)
    dong_hang_id = fields.Many2one(
        'dong.hang', string='Dòng hàng', index=True)
    ma_hang_id = fields.Many2one(
        'ma.hang', string='Mã hàng', index=True)
    ma_sap = fields.Char(string='Mã SAP', index=True)
    month_key = fields.Char(string='Tháng', index=True)
    month_date = fields.Date(string='Tháng tính toán', index=True)
    qty = fields.Float(string='Số lượng', digits=(16, 2))
    source_type = fields.Selection([
        ('business_plan', 'Sản xuất theo kế hoạch kinh doanh'),
        ('forecast', 'Sản xuất theo dự trù'),
    ], string='Loại kế hoạch', default='business_plan', index=True)
    note = fields.Char(string='Ghi chú')

    _sql_constraints = [
        ('uniq_material_plan_row',
         'unique(period_id, company_id, ma_hang_id, ma_sap, month_key)',
         'Trùng dòng kế hoạch vật tư chốt!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        Period = self.env['ke.hoach.vat.tu']
        MaHang = self.env['ma.hang']
        for vals in vals_list:
            if vals.get('period_id'):
                period = Period.browse(vals['period_id'])
                if period.state != 'ke_hoach':
                    raise UserError(_('Kế hoạch vật tư đã khóa vì kỳ kế hoạch đã sang bước sau.'))
            if vals.get('month_key') and not vals.get('month_date'):
                vals['month_date'] = Period._month_key_to_date(vals['month_key'])
            if vals.get('ma_hang_id'):
                master = MaHang.browse(vals['ma_hang_id'])
                vals.setdefault('ma_sap', master.ma_sap)
                vals.setdefault('nganh_hang_id', master.nganh_hang_id.id)
                vals.setdefault('dong_hang_id', master.dong_hang_id.id)
        return super().create(vals_list)

    def write(self, vals):
        self._check_period_editable()
        if 'month_key' in vals:
            vals = dict(vals)
            vals['month_date'] = self.env['ke.hoach.vat.tu']._month_key_to_date(vals.get('month_key'))
        return super().write(vals)

    def unlink(self):
        self._check_period_editable()
        return super().unlink()

    def _check_period_editable(self):
        if self.env.context.get('skip_period_lock'):
            return
        locked = self.filtered(lambda rec: rec.period_id and rec.period_id.state != 'ke_hoach')
        if locked:
            raise UserError(_('Kế hoạch vật tư đã khóa vì kỳ kế hoạch đã sang bước sau.'))

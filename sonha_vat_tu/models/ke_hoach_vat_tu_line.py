# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class KeHoachVatTuLine(models.Model):
    _name = 'ke.hoach.vat.tu.line'
    _description = 'Kế hoạch vật tư chốt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id, company_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty sản xuất', index=True, required=True)
    nganh_hang = fields.Char(string='Ngành hàng', index=True)
    dong_hang = fields.Char(string='Dòng hàng', index=True)
    ma_hang = fields.Char(string='Mã hàng', index=True)
    ma_sap = fields.Char(string='Mã SAP', index=True)
    qty_kd_t0 = fields.Float(string='Kinh doanh T0', digits=(16, 2))
    qty_kd_t1 = fields.Float(string='Kinh doanh T+1', digits=(16, 2))
    qty_kd_t2 = fields.Float(string='Kinh doanh T+2', digits=(16, 2))
    qty_kd_t3 = fields.Float(string='Kinh doanh T+3', digits=(16, 2))

    qty_sx_t0 = fields.Float(string='Sản xuất T0', digits=(16, 2))
    qty_sx_t1 = fields.Float(string='Sản xuất T+1', digits=(16, 2))
    qty_sx_t2 = fields.Float(string='Sản xuất T+2', digits=(16, 2))
    qty_sx_t3 = fields.Float(string='Sản xuất T+3', digits=(16, 2))

    qty_cl_t0 = fields.Float(string='Chênh lệch T0', compute='_compute_qty_chenh_lech', store=True, digits=(16, 2))
    qty_cl_t1 = fields.Float(string='Chênh lệch T+1', compute='_compute_qty_chenh_lech', store=True, digits=(16, 2))
    qty_cl_t2 = fields.Float(string='Chênh lệch T+2', compute='_compute_qty_chenh_lech', store=True, digits=(16, 2))
    qty_cl_t3 = fields.Float(string='Chênh lệch T+3', compute='_compute_qty_chenh_lech', store=True, digits=(16, 2))

    qty_t0 = fields.Float(string='Tính toán T0', digits=(16, 2))
    qty_t1 = fields.Float(string='Tính toán T+1', digits=(16, 2))
    qty_t2 = fields.Float(string='Tính toán T+2', digits=(16, 2))
    qty_t3 = fields.Float(string='Tính toán T+3', digits=(16, 2))
    note = fields.Char(string='Ghi chú')

    _sql_constraints = [
        ('uniq_material_plan_row',
         'unique(period_id, company_id, ma_sap)',
         'Trùng dòng kế hoạch vật tư chốt!'),
    ]

    @api.depends(
        'qty_kd_t0', 'qty_kd_t1', 'qty_kd_t2', 'qty_kd_t3',
        'qty_sx_t0', 'qty_sx_t1', 'qty_sx_t2', 'qty_sx_t3',
    )
    def _compute_qty_chenh_lech(self):
        for rec in self:
            rec.qty_cl_t0 = (rec.qty_sx_t0 or 0.0) - (rec.qty_kd_t0 or 0.0)
            rec.qty_cl_t1 = (rec.qty_sx_t1 or 0.0) - (rec.qty_kd_t1 or 0.0)
            rec.qty_cl_t2 = (rec.qty_sx_t2 or 0.0) - (rec.qty_kd_t2 or 0.0)
            rec.qty_cl_t3 = (rec.qty_sx_t3 or 0.0) - (rec.qty_kd_t3 or 0.0)

    @api.constrains('company_id')
    def _check_production_company(self):
        invalid = self.filtered(
            lambda rec: rec.company_id.company_code not in ('BNH', 'SSP')
        )
        if invalid:
            raise ValidationError(_(
                'Công ty sản xuất của kế hoạch vật tư chỉ được là BNH hoặc SSP.'
            ))

    @api.model_create_multi
    def create(self, vals_list):
        Period = self.env['ke.hoach.vat.tu']
        MaHang = self.env['ma.hang'].sudo()
        for vals in vals_list:
            if vals.get('period_id'):
                period = Period.browse(vals['period_id'])
                if period.state != 'ke_hoach':
                    raise UserError(_('Kế hoạch vật tư đã khóa vì kỳ kế hoạch đã sang bước sau.'))
            if vals.get('ma_sap'):
                master = MaHang.search([('ma_sap', '=', vals['ma_sap'])], limit=1)
                if master:
                    vals.setdefault('nganh_hang', master.nganh_hang)
            for idx in (0, 1, 2, 3):
                sx_f = f'qty_sx_t{idx}'
                qty_f = f'qty_t{idx}'
                if sx_f in vals and qty_f not in vals:
                    vals[qty_f] = vals.get(sx_f) or 0.0
        return super().create(vals_list)

    def write(self, vals):
        self._check_period_editable()
        vals = dict(vals)
        for idx in (0, 1, 2, 3):
            sx_f = f'qty_sx_t{idx}'
            qty_f = f'qty_t{idx}'
            if sx_f in vals and qty_f not in vals:
                vals[qty_f] = vals.get(sx_f) or 0.0
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

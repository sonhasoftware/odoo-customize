# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KeHoachVatTuLine(models.Model):
    _name = 'ke.hoach.vat.tu.line'
    _description = 'Kế hoạch vật tư chốt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id, company_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị đặt hàng', index=True, required=True)
    company_sx_id = fields.Many2one(
        'res.company', string='Nhà máy SX', index=True, required=True,
        help='Đơn vị sản xuất (BNH/SSP).',
    )
    nganh_hang = fields.Char(string='Ngành hàng', index=True)
    ten_hang = fields.Char(
        string='Tên hàng',
        compute='_compute_ten_hang',
        store=True,
        readonly=True,
    )
    ma_hang = fields.Char(string='Mã hàng', index=True)
    ma_sap = fields.Char(string='Mã', index=True)

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
         'Trùng dòng kế hoạch vật tư (Kỳ, Đơn vị, Mã)!'),
    ]

    @api.depends('ma_sap')
    def _compute_ten_hang(self):
        codes = {(rec.ma_sap or '').strip() for rec in self if (rec.ma_sap or '').strip()}
        name_map = {}
        if codes:
            meta_map = self.env['ma.hang'].get_mdm_sap_meta_map(codes)
            name_map = {code: meta.get('ten_hang', '') for code, meta in meta_map.items()}
        for rec in self:
            code = (rec.ma_sap or '').strip()
            rec.ten_hang = name_map.get(code, '') if code else ''

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

    @api.model_create_multi
    def create(self, vals_list):
        Period = self.env['ke.hoach.vat.tu']
        period_ids = {v['period_id'] for v in vals_list if v.get('period_id')}
        if period_ids:
            locked = Period.browse(list(period_ids)).filtered(lambda p: p.state != 'ke_hoach')
            if locked:
                raise UserError(_('Kế hoạch vật tư đã khóa vì kỳ kế hoạch đã sang bước sau.'))

        sap_codes = sorted({
            (v.get('ma_sap') or '').strip()
            for v in vals_list if (v.get('ma_sap') or '').strip()
        })
        meta_map = self.env['ma.hang'].get_mdm_sap_meta_map(sap_codes) if sap_codes else {}
        NganhHang = self.env['mdm.nganh.hang'].sudo()

        for vals in vals_list:
            ma_sap = (vals.get('ma_sap') or '').strip()
            if ma_sap:
                meta = meta_map.get(ma_sap, {})
                if not vals.get('nganh_hang') and meta.get('nganh_hang_id'):
                    nh = NganhHang.browse(meta['nganh_hang_id'])
                    vals['nganh_hang'] = nh.ten or ''
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

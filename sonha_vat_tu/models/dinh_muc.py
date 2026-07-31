# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_SCOPE = 'dm'

_QTY_FIELDS = (
    'qty_kinh_doanh_t0', 'qty_kinh_doanh_t1', 'qty_kinh_doanh_t2', 'qty_kinh_doanh_t3',
    'qty_san_xuat_t0', 'qty_san_xuat_t1', 'qty_san_xuat_t2', 'qty_san_xuat_t3',
    'qty_chenh_lech_t0', 'qty_chenh_lech_t1', 'qty_chenh_lech_t2', 'qty_chenh_lech_t3',
    'qty_t0', 'qty_t1', 'qty_t2', 'qty_t3',
)


class DinhMuc(models.Model):
    _name = 'dinh.muc'
    _description = 'Định mức kỳ'
    _order = 'period_id, company_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True)
    ma_sap = fields.Char(string='Mã', index=True)
    ten_sap = fields.Char(string='Tên SAP')
    ma_tp = fields.Char(string='Mã TP', index=True)
    ten_tp = fields.Char(string='Tên TP')
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    sl_dinh_muc = fields.Float(
        string='Định mức', digits=(16, 3), readonly=True,
        help='Số lượng NVL / 1 SP theo nhánh BOM (sl_thuc_te từ bom_tinh_toan).',
    )
    sl_dinh_muc_thay_doi = fields.Float(
        string='Định mức thay đổi', digits=(16, 3), copy=False,
        help='Nhập khi định mức SAP/BOM chưa đúng. B3 sẽ dùng giá trị này thay cho định mức gốc.',
    )
    co_sl_dinh_muc_override = fields.Boolean(
        string='Có định mức thay đổi', default=False, copy=False,
    )
    sl_dinh_muc_ap_dung = fields.Float(
        string='Định mức áp dụng', digits=(16, 3),
        compute='_compute_sl_dinh_muc_ap_dung', store=True, readonly=True,
    )

    qty_kinh_doanh_t0 = fields.Float(string='KD T0', digits=(16, 2))
    qty_kinh_doanh_t1 = fields.Float(string='KD T1', digits=(16, 2))
    qty_kinh_doanh_t2 = fields.Float(string='KD T2', digits=(16, 2))
    qty_kinh_doanh_t3 = fields.Float(string='KD T3', digits=(16, 2))

    qty_san_xuat_t0 = fields.Float(string='SX T0', digits=(16, 2))
    qty_san_xuat_t1 = fields.Float(string='SX T1', digits=(16, 2))
    qty_san_xuat_t2 = fields.Float(string='SX T2', digits=(16, 2))
    qty_san_xuat_t3 = fields.Float(string='SX T3', digits=(16, 2))

    qty_chenh_lech_t0 = fields.Float(string='CL T0', digits=(16, 2))
    qty_chenh_lech_t1 = fields.Float(string='CL T1', digits=(16, 2))
    qty_chenh_lech_t2 = fields.Float(string='CL T2', digits=(16, 2))
    qty_chenh_lech_t3 = fields.Float(string='CL T3', digits=(16, 2))

    qty_t0 = fields.Float(string='Số lượng T0', digits=(16, 3))
    qty_t1 = fields.Float(string='Số lượng T1', digits=(16, 3))
    qty_t2 = fields.Float(string='Số lượng T2', digits=(16, 3))
    qty_t3 = fields.Float(string='Số lượng T3', digits=(16, 3))

    @api.depends('sl_dinh_muc', 'sl_dinh_muc_thay_doi', 'co_sl_dinh_muc_override')
    def _compute_sl_dinh_muc_ap_dung(self):
        for rec in self:
            if rec.co_sl_dinh_muc_override:
                rec.sl_dinh_muc_ap_dung = rec.sl_dinh_muc_thay_doi or 0.0
            else:
                rec.sl_dinh_muc_ap_dung = rec.sl_dinh_muc or 0.0

    def _effective_sl_dinh_muc(self):
        self.ensure_one()
        if self.co_sl_dinh_muc_override:
            return self.sl_dinh_muc_thay_doi or 0.0
        return self.sl_dinh_muc or 0.0

    def _check_period_editable(self):
        locked = self.filtered(
            lambda rec: not rec.period_id or rec.period_id.state != 'dinh_muc'
        )
        if locked:
            raise UserError(_('Chỉ được sửa định mức thay đổi ở bước Định mức kỳ.'))

    def _scale_qty_vals(self, old_eff, new_eff):
        self.ensure_one()
        if not old_eff:
            return {}
        ratio = new_eff / old_eff
        return {
            fname: (getattr(self, fname) or 0.0) * ratio
            for fname in _QTY_FIELDS
        }

    def _format_sl(self, qty):
        if qty is False:
            return _('Trống')
        return '{:,.3f}'.format(qty or 0.0).replace(',', 'X').replace('.', ',').replace('X', '.')

    def _override_tracking_row(self):
        self.ensure_one()
        new_override = self.sl_dinh_muc_thay_doi if self.co_sl_dinh_muc_override else False
        return {
            'don_vi': self.company_id.sudo().company_code or self.company_id.sudo().name or '',
            'ma_sap': self.ma_sap or '',
            'ten_sap': self.ten_sap or '',
            'ma_nvl': self.ma_nvl or '',
            'ten_nvl': self.ten_nvl or '',
            'sl_dinh_muc': self._format_sl(self.sl_dinh_muc),
            'sl_dinh_muc_thay_doi': self._format_sl(new_override),
        }

    @api.model
    def _build_override_table_html(self, lines):
        rows = Markup('').join(
            Markup(
                "<tr>"
                "<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                "<td class='text-end'>%s</td><td class='text-end'>%s</td>"
                "</tr>"
            ) % (
                escape(line['don_vi']),
                escape(line['ma_sap']),
                escape(line['ten_sap']),
                escape(line['ma_nvl']),
                escape(line['ten_nvl']),
                escape(line['sl_dinh_muc']),
                escape(line['sl_dinh_muc_thay_doi']),
            )
            for line in lines
        )
        return Markup("""
            <p class="mb-2"><b>%s</b></p>
            <div class="table-responsive">
                <table class="table table-sm table-bordered o_main_table mb-0" style="font-size: 13px;">
                    <thead class="bg-light">
                        <tr>
                            <th>Đơn vị</th>
                            <th>Mã</th>
                            <th>Tên SAP</th>
                            <th>Mã NVL</th>
                            <th>Tên NVL</th>
                            <th class="text-end">Định mức</th>
                            <th class="text-end">Định mức thay đổi</th>
                        </tr>
                    </thead>
                    <tbody>%s</tbody>
                </table>
            </div>
        """) % (_('Cập nhật định mức thay đổi'), rows)

    @api.model
    def _log_override_changes(self, changes_by_period):
        for period, lines in changes_by_period.items():
            if not lines:
                continue
            period.with_context(vat_tu_chatter_scope=_SCOPE).message_post(
                body=self._build_override_table_html(lines),
            )

    def write(self, vals):
        if 'sl_dinh_muc_thay_doi' not in vals:
            return super().write(vals)

        self._check_period_editable()
        vals = dict(vals)
        if vals['sl_dinh_muc_thay_doi'] in (False, None, ''):
            vals.update(sl_dinh_muc_thay_doi=0.0, co_sl_dinh_muc_override=False)
        elif not vals['sl_dinh_muc_thay_doi']:
            vals.update(sl_dinh_muc_thay_doi=0.0, co_sl_dinh_muc_override=False)
        else:
            vals['co_sl_dinh_muc_override'] = True

        old_map = {
            rec.id: rec.sl_dinh_muc_thay_doi if rec.co_sl_dinh_muc_override else False
            for rec in self
        }

        if len(self) == 1:
            rec = self
            old_eff = rec._effective_sl_dinh_muc()
            new_eff = (
                vals['sl_dinh_muc_thay_doi'] if vals['co_sl_dinh_muc_override']
                else rec.sl_dinh_muc or 0.0
            )
            if old_eff and abs(old_eff - new_eff) > 1e-12:
                vals.update(rec._scale_qty_vals(old_eff, new_eff))

        res = super().write(vals)

        changes_by_period = {}
        for rec in self:
            old_val = old_map[rec.id]
            new_val = rec.sl_dinh_muc_thay_doi if rec.co_sl_dinh_muc_override else False
            if old_val == new_val or not rec.period_id:
                continue
            changes_by_period.setdefault(rec.period_id, []).append(
                rec._override_tracking_row()
            )
        self._log_override_changes(changes_by_period)
        if not self.env.context.get('skip_bom_dinh_muc_sync'):
            self._sync_to_bom_dinh_muc()
        return res

    def _sync_to_bom_dinh_muc(self):
        BomDinhMuc = self.env['bom.dinh.muc']
        for rec in self:
            BomDinhMuc._upsert_from_dinh_muc(rec, update_override=True)

    def _apply_master_override(self, master):
        self.ensure_one()
        old_eff = self._effective_sl_dinh_muc()
        if master.sl_dinh_muc_thay_doi:
            vals = {
                'sl_dinh_muc_thay_doi': master.sl_dinh_muc_thay_doi,
                'co_sl_dinh_muc_override': True,
            }
            new_eff = master.sl_dinh_muc_thay_doi
        else:
            vals = {
                'sl_dinh_muc_thay_doi': 0.0,
                'co_sl_dinh_muc_override': False,
            }
            new_eff = self.sl_dinh_muc or 0.0
        if old_eff and abs(old_eff - new_eff) > 1e-12:
            vals.update(self._scale_qty_vals(old_eff, new_eff))
        return super(DinhMuc, self.with_context(skip_bom_dinh_muc_sync=True)).write(vals)

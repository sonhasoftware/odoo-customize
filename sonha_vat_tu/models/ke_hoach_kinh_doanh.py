# -*- coding: utf-8 -*-
from markupsafe import Markup, escape
from odoo import api, fields, models, _
from odoo.exceptions import UserError


_SCOPE = 'kd'


class KeHoachKinhDoanh(models.Model):
    _name = 'ke.hoach.kinh.doanh'
    _description = 'Ke hoach kinh doanh'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id, month_date, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    nganh_hang = fields.Char(string='Ngành hàng', index=True)
    dong_hang = fields.Char(string='Dòng hàng', index=True)
    ma_hang_id = fields.Many2one(
        'ma.hang', string='Mã hàng', index=True)
    ma_sap = fields.Char(string='Mã SAP', index=True)
    month_key = fields.Char(string='Tháng', index=True)
    month_date = fields.Date(string='Tháng tính toán', index=True)
    qty = fields.Float(string='Số lượng', digits=(16, 2))
    note = fields.Char(string='Ghi chú')

    _sql_constraints = [
        ('uniq_business_row',
         'unique(period_id, ma_sap, month_key)',
         'Trùng dòng: Kỳ, Mã SAP và Tháng phải duy nhất trên kế hoạch kinh doanh!'),
    ]

    @api.onchange('ma_hang_id')
    def _onchange_ma_hang(self):
        for rec in self:
            if rec.ma_hang_id:
                rec.ma_sap = rec.ma_hang_id.ma_sap or rec.ma_sap
                rec.nganh_hang = rec.ma_hang_id.nganh_hang or rec.nganh_hang

    @api.model_create_multi
    def create(self, vals_list):
        Period = self.env['ke.hoach.vat.tu']
        MaHang = self.env['ma.hang'].sudo()
        for vals in vals_list:
            if vals.get('period_id'):
                period = Period.browse(vals['period_id'])
                if period.state != 'ke_hoach':
                    raise UserError(_('Kế hoạch kinh doanh đã khóa vì kỳ kế hoạch đã sang bước sau.'))

            if vals.get('month_key') and not vals.get('month_date'):
                vals['month_date'] = Period._month_key_to_date(vals['month_key'])

            if vals.get('ma_hang_id'):
                master = MaHang.browse(vals['ma_hang_id'])
                vals.setdefault('ma_sap', master.ma_sap)
                vals.setdefault('nganh_hang', master.nganh_hang)
            elif vals.get('ma_sap'):
                master = MaHang.search([('ma_sap', '=', vals['ma_sap'])], limit=1)
                if master:
                    vals['ma_hang_id'] = master.id
                    vals.setdefault('nganh_hang', master.nganh_hang)
        records = super().create(vals_list)
        if not self.env.context.get('is_importing'):
            self._log_action_table(records, action='create')
        return records

    def unlink(self):
        self._check_period_editable()
        self._log_action_table(self, action='unlink')
        return super().unlink()

    def _check_period_editable(self):
        locked = self.filtered(lambda rec: rec.period_id and rec.period_id.state != 'ke_hoach')
        if locked:
            raise UserError(_('Kế hoạch kinh doanh đã khóa vì kỳ kế hoạch đã sang bước sau.'))

    @api.model
    def _format_qty(self, qty):
        return "{:,.2f}".format(qty or 0.0).replace(',', 'X').replace('.', ',').replace('X', '.')

    def _tracking_values(self):
        return {
            'nganh': self.nganh_hang or '',
            'dong': self.dong_hang or '',
            'ma_sap': self.ma_sap or '',
            'month_key': self.month_key or '',
            'qty': self._format_qty(self.qty),
        }

    @api.model
    def _log_action_table(self, records, action='create'):
        period_lines = {}
        for rec in records.filtered('period_id'):
            period_lines.setdefault(rec.period_id, []).append(rec._tracking_values())

        for period, lines in period_lines.items():
            title = (
                "<span class='text-success'><i class='fa fa-plus-circle'></i> "
                f"<b>Đã thêm {len(lines)} dòng kế hoạch kinh doanh mới:</b></span>"
            ) if action == 'create' else (
                "<span class='text-danger'><i class='fa fa-trash'></i> "
                f"<b>Đã xóa {len(lines)} dòng kế hoạch kinh doanh:</b></span>"
            )
            period.with_context(vat_tu_chatter_scope=_SCOPE).message_post(
                body=self._build_tracking_table_html(title, lines, action=action)
            )

    @api.model
    def _build_tracking_table_html(self, title, lines, action='create'):
        def cell(value):
            value = escape(value)
            return Markup("<del class='text-muted'>%s</del>") % value if action == 'unlink' else value

        rows = ''.join(
            "<tr>"
            f"<td>{cell(vals['nganh'])}</td>"
            f"<td>{cell(vals['dong'])}</td>"
            f"<td>{cell(vals['ma_sap'])}</td>"
            f"<td>{cell(vals['month_key'])}</td>"
            f"<td class='text-end'>{cell(vals['qty'])}</td>"
            "</tr>"
            for vals in lines
        )
        return Markup("""
            <p class="mb-2">%s</p>
            <div class="table-responsive">
                <table class="table table-sm table-bordered o_main_table mb-0" style="font-size: 13px;">
                    <thead class="bg-light">
                        <tr>
                            <th>Ngành hàng</th>
                            <th>Dòng hàng</th>
                            <th>Mã SAP</th>
                            <th>Tháng</th>
                            <th class="text-end">Số lượng</th>
                        </tr>
                    </thead>
                    <tbody>%s</tbody>
                </table>
            </div>
        """) % (Markup(title), Markup(rows))

    @api.model
    def _log_field_changes(self, changes_by_period):
        """Gom mọi thay đổi trong cùng một period vào 1 message bảng để tránh
        spam chatter khi user sửa nhiều dòng cùng lúc."""
        for period, changes in changes_by_period.items():
            if not changes:
                continue
            items = ''.join(
                "<li>"
                "<b class='o-mail-Message-trackingOld me-1 px-1 text-muted fw-bold'>%s</b>"
                "<i class='o_TrackingValue_separator fa fa-long-arrow-right mx-1 text-600' role='img'></i>"
                "<b class='o-mail-Message-trackingNew me-1 fw-bold text-info'>%s</b>"
                "<span class='o-mail-Message-trackingField ms-1 fst-italic text-muted'>(%s)</span>"
                "</li>" % (escape(old), escape(new), escape(label))
                for old, new, label in changes
            )
            period.with_context(vat_tu_chatter_scope=_SCOPE).message_post(
                body=Markup("<ul>%s</ul>") % Markup(items)
            )

    def write(self, vals):
        TRACKED = {'ma_sap': 'Mã SAP', 'month_key': 'Tháng', 'qty': 'Số lượng'}

        if not self.env.context.get('skip_period_lock'):
            self._check_period_editable()

        if 'month_key' in vals:
            vals = dict(vals)
            vals['month_date'] = self.env['ke.hoach.vat.tu']._month_key_to_date(vals.get('month_key'))

        old = {f: {r.id: r[f] for r in self} for f in TRACKED if f in vals}
        res = super().write(vals)
        if self.env.context.get('is_importing'):
            return res

        changes_by_period = {}
        for f, label in TRACKED.items():
            if f not in old:
                continue
            for rec in self:
                ov, nv = old[f][rec.id], rec[f]
                if ov == nv:
                    continue
                ov_disp = ov if ov not in (False, None, '') else 'Trống'
                nv_disp = nv if nv not in (False, None, '') else 'Trống'
                ma_hang_code = rec.ma_hang_id.ma_sap if rec.ma_hang_id else ''
                changes_by_period.setdefault(rec.period_id, []).append((
                    str(ov_disp),
                    str(nv_disp),
                    f'{label} - Mã hàng {ma_hang_code}',
                ))
        self._log_field_changes(changes_by_period)

        return res

# -*- coding: utf-8 -*-
import re
from markupsafe import Markup, escape
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_SCOPE = 'sx'


class KeHoachSanXuat(models.Model):
    _name = 'ke.hoach.san.xuat'
    _description = 'Kế hoạch sản xuất theo tháng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id, company_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ',
        ondelete='cascade', index=True)

    company_id = fields.Many2one(
        'res.company', string='Công ty',
        default=lambda self: self.env.company, index=True)

    nganh_hang = fields.Many2one(
        'mdm.nganh.hang', string='Ngành hàng',
        compute='_compute_ma_hang_meta',
        store=True,
        readonly=True,
        index=True,
        ondelete='restrict')
    ten_hang = fields.Char(
        string='Tên hàng',
        compute='_compute_ma_hang_meta',
        store=True,
        readonly=True,
    )
    ma_hang = fields.Char(string='Mã hàng', index=True)
    ma_sap = fields.Char(
        string='Mã SAP', index=True)


    qty_t0 = fields.Float(string='Tháng T0', digits=(16, 2))
    qty_t1 = fields.Float(string='Tháng T+1', digits=(16, 2))
    qty_t2 = fields.Float(string='Tháng T+2', digits=(16, 2))
    qty_t3 = fields.Float(string='Tháng T+3', digits=(16, 2))

    note = fields.Char(string='Ghi chú')

    _sql_constraints = [
        ('uniq_row',
         'unique(period_id, company_id, ma_sap)',
         'Trùng dòng: (Kỳ, Công ty, Mã SAP) phải duy nhất!'),
    ]

    @api.depends('ma_sap')
    def _compute_ma_hang_meta(self):
        codes = {(rec.ma_sap or '').strip() for rec in self if (rec.ma_sap or '').strip()}
        meta_map = self.env['ma.hang'].get_sap_meta_map(codes)
        for rec in self:
            code = (rec.ma_sap or '').strip()
            meta = meta_map.get(code, {}) if code else {}
            rec.ten_hang = meta.get('ten_hang', '')
            rec.nganh_hang = meta.get('nganh_hang_id') or False

    @api.constrains('company_id')
    def _check_production_company(self):
        invalid = self.filtered(
            lambda rec: rec.company_id
            and rec.company_id.company_code not in ('BNH', 'SSP')
        )
        if invalid:
            raise ValidationError(_(
                'Đơn vị sản xuất chỉ được phép là BNH hoặc SSP.'
            ))

    @api.model_create_multi
    def create(self, vals_list):
        period_ids = list(set(v['period_id'] for v in vals_list if v.get('period_id')))
        if period_ids:
            for period in self.env['ke.hoach.vat.tu'].browse(period_ids):
                if period.state != 'ke_hoach':
                    raise UserError(_('Kế hoạch sản xuất đã khóa vì kỳ kế hoạch đã sang bước sau.'))

        company = self.env.company
        allow_unassigned = self.env.context.get('allow_unassigned_production_company')

        for vals in vals_list:
            if not vals.get('company_id') and vals.get('period_id'):
                if allow_unassigned:
                    vals['company_id'] = False
                else:
                    if company.company_code not in ('BNH', 'SSP'):
                        raise UserError(_('Công ty hiện tại không phải công ty sản xuất BNH/SSP.'))
                    vals['company_id'] = company.id

        records = super().create(vals_list)
        
        # Log khi Thêm dòng trên UI (bỏ qua nếu đang chạy import wizard)
        if not self.env.context.get('is_importing'):
            self._log_action_table(records, action='create')
                
        return records

    def unlink(self):
        periods = self.mapped('period_id')
        self._check_period_editable()
        if not self.env.context.get('is_importing'):
            self._log_action_table(self, action='unlink')
        res = super().unlink()
        return res

    def _check_period_editable(self):
        locked = self.filtered(lambda rec: rec.period_id and rec.period_id.state != 'ke_hoach')
        if locked:
            raise UserError(_('Kế hoạch sản xuất đã khóa vì kỳ kế hoạch đã sang bước sau.'))

    @api.model
    def _format_qty(self, qty):
        return "{:,.2f}".format(qty or 0.0).replace(',', 'X').replace('.', ',').replace('X', '.')

    @api.model
    def _month_labels(self, period):
        labels = {
            'qty_t0': 'Tháng T0',
            'qty_t1': 'Tháng T+1',
            'qty_t2': 'Tháng T+2',
            'qty_t3': 'Tháng T+3',
        }
        period_month = period.period_month if period else False
        if not period_month:
            return labels
        try:
            month, year = [int(part) for part in period_month.split('/')]
        except (TypeError, ValueError):
            return labels
        for idx in range(4):
            cur_month = month + idx
            cur_year = year
            while cur_month > 12:
                cur_month -= 12
                cur_year += 1
            labels[f'qty_t{idx}'] = 'Tháng %02d/%s' % (cur_month, cur_year)
        return labels

    def _tracking_values(self):
        return {
            'nganh': self.nganh_hang.ten if self.nganh_hang else '',
            'ten_hang': self.ten_hang or '',
            'ma_hang': self.ma_hang or '',
            'ma_sap': self.ma_sap or '',
            'qty_t0': self._format_qty(self.qty_t0),
            'qty_t1': self._format_qty(self.qty_t1),
            'qty_t2': self._format_qty(self.qty_t2),
            'qty_t3': self._format_qty(self.qty_t3),
        }

    @api.model
    def _log_action_table(self, records, action='create'):
        period_lines = {}
        for rec in records.filtered('period_id'):
            period_lines.setdefault(rec.period_id, []).append(rec._tracking_values())

        for period, lines in period_lines.items():
            title = (
                "<span class='text-success'><i class='fa fa-plus-circle'></i> "
                f"<b>Đã thêm {len(lines)} dòng kế hoạch sản xuất mới:</b></span>"
            ) if action == 'create' else (
                "<span class='text-danger'><i class='fa fa-trash'></i> "
                f"<b>Đã xóa {len(lines)} dòng kế hoạch sản xuất:</b></span>"
            )
            period.with_context(vat_tu_chatter_scope=_SCOPE).message_post(
                body=self._build_tracking_table_html(title, lines, period, action=action)
            )

    @api.model
    def _build_tracking_table_html(self, title, lines, period, action='create'):
        month_labels = self._month_labels(period)

        def cell(value):
            value = escape(value)
            return Markup("<del class='text-muted'>%s</del>") % value if action == 'unlink' else value

        rows = ''.join(
            "<tr>"
            f"<td>{cell(vals['nganh'])}</td>"
            f"<td>{cell(vals['ten_hang'])}</td>"
            f"<td>{cell(vals['ma_hang'])}</td>"
            f"<td>{cell(vals['ma_sap'])}</td>"
            f"<td class='text-end'>{cell(vals['qty_t0'])}</td>"
            f"<td class='text-end'>{cell(vals['qty_t1'])}</td>"
            f"<td class='text-end'>{cell(vals['qty_t2'])}</td>"
            f"<td class='text-end'>{cell(vals['qty_t3'])}</td>"
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
                            <th>Tên hàng</th>
                            <th>Mã hàng</th>
                            <th>Mã SAP</th>
                            <th class="text-end">%s</th>
                            <th class="text-end">%s</th>
                            <th class="text-end">%s</th>
                            <th class="text-end">%s</th>
                        </tr>
                    </thead>
                    <tbody>%s</tbody>
                </table>
            </div>
        """) % (
            Markup(title),
            escape(month_labels['qty_t0']),
            escape(month_labels['qty_t1']),
            escape(month_labels['qty_t2']),
            escape(month_labels['qty_t3']),
            Markup(rows),
        )

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
        TRACKED = {
            'ma_hang': 'Mã hàng',
            'ma_sap': 'Mã SAP',
            'qty_t0': False,
            'qty_t1': False,
            'qty_t2': False,
            'qty_t3': False,
        }

        if not self.env.context.get('skip_period_lock'):
            self._check_period_editable()

        if 'company_id' in vals and not vals.get('company_id'):
            if not self.env.context.get('allow_unassigned_production_company'):
                raise UserError(_('Đơn vị sản xuất không được để trống.'))

        old = {f: {r.id: r[f] for r in self} for f in TRACKED if f in vals}
        res = super().write(vals)
        if self.env.context.get('is_importing'):
            return res

        changes_by_period = {}
        month_label_cache = {}
        for f, label in TRACKED.items():
            if f not in old:
                continue
            for rec in self:
                ov, nv = old[f][rec.id], rec[f]
                if ov == nv:
                    continue
                if f.startswith('qty_t'):
                    month_labels = month_label_cache.setdefault(
                        rec.period_id.id,
                        self._month_labels(rec.period_id),
                    )
                    label = month_labels[f]
                    ov_disp = self._format_qty(ov)
                    nv_disp = self._format_qty(nv)
                else:
                    ov_disp = ov if ov not in (False, None, '') else 'Trống'
                    nv_disp = nv if nv not in (False, None, '') else 'Trống'
                ma_hang_code = rec.ma_hang or ''
                changes_by_period.setdefault(rec.period_id, []).append((
                    str(ov_disp),
                    str(nv_disp),
                    f'{label} - Mã hàng {ma_hang_code}',
                ))
        self._log_field_changes(changes_by_period)

        return res

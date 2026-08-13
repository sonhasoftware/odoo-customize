# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .ke_hoach_line_mixin import QTY_FIELDS


class KeHoachKinhDoanhLine(models.Model):
    _name = 'ke.hoach.kinh.doanh.line'
    _description = 'Dòng kế hoạch kinh doanh'
    _inherit = ['ke.hoach.line.mixin']

    _CHATTER_SCOPE = 'kd'
    _LINE_LABEL = 'kế hoạch kinh doanh'

    kinh_doanh_id = fields.Many2one(
        'ke.hoach.kinh.doanh', string='KHKD',
        required=True, ondelete='cascade', index=True,
    )
    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ SX',
        related='kinh_doanh_id.period_sx_id', store=True, readonly=True,
    )

    _sql_constraints = [
        ('uniq_kd_line',
         'unique(kinh_doanh_id, company_id, ma_sap)',
         'Trùng dòng: KHKD, Đơn vị và Mã phải duy nhất!'),
    ]

    @api.model
    def _assign_create_sequences(self, vals_list):
        next_by_header = {}
        for vals in vals_list:
            if vals.get('sequence') or not vals.get('kinh_doanh_id'):
                continue
            hid = vals['kinh_doanh_id']
            if hid not in next_by_header:
                last = self.search(
                    [('kinh_doanh_id', '=', hid)], order='sequence desc', limit=1)
                next_by_header[hid] = last.sequence if last else 0
            next_by_header[hid] += 10
            vals['sequence'] = next_by_header[hid]

    def _chatter_header(self):
        self.ensure_one()
        return self.kinh_doanh_id

    def _check_period_editable(self):
        locked = self.filtered(lambda rec: rec.kinh_doanh_id.locked)
        if locked:
            raise UserError(
                _('%s đã khóa vì kế hoạch kinh doanh đã lấy vào sản xuất.')
                % self._LINE_LABEL.capitalize()
            )

    @api.model
    def _check_period_open(self, vals_list):
        kd_ids = {v['kinh_doanh_id'] for v in vals_list if v.get('kinh_doanh_id')}
        locked = self.env['ke.hoach.kinh.doanh'].browse(list(kd_ids)).filtered('locked')
        if locked:
            raise UserError(
                _('%s đã khóa vì kế hoạch kinh doanh đã lấy vào sản xuất.')
                % self._LINE_LABEL.capitalize()
            )

    @api.constrains('ma_sap', 'kinh_doanh_id')
    def _check_ma_sap_in_catalog(self):
        if self.env.context.get('is_importing'):
            return
        for rec in self.filtered(
            lambda r: not r.kinh_doanh_id.locked and (r.ma_sap or '').strip()
        ):
            if not self.env['ma.hang'].sap_exists_in_mdm(rec.ma_sap.strip()):
                raise ValidationError(
                    _('Mã "%s" không có trong MDM (mdm.tong.hop.line).') % rec.ma_sap
                )

    def _post_scoped_message(self, header, body):
        header.with_context(vat_tu_chatter_scope=self._CHATTER_SCOPE).message_post(body=body)

    @api.model
    def _log_action_table(self, records, action='create'):
        by_header = {}
        for rec in records:
            header = rec._chatter_header()
            if header:
                by_header.setdefault(header, []).append(rec._tracking_values())

        for header, lines in by_header.items():
            if action == 'create':
                title = (
                    "<span class='text-success'><i class='fa fa-plus-circle'></i> "
                    f"<b>Đã thêm {len(lines)} dòng {self._LINE_LABEL} mới:</b></span>"
                )
            else:
                title = (
                    "<span class='text-danger'><i class='fa fa-trash'></i> "
                    f"<b>Đã xóa {len(lines)} dòng {self._LINE_LABEL}:</b></span>"
                )
            self._post_scoped_message(
                header,
                self._build_tracking_table_html(title, lines, header, action=action),
            )

    def _log_tracked_changes(self, old):
        changes_by_header = {}
        month_label_cache = {}
        for fname, static_label in self._TRACKED_FIELDS.items():
            if fname not in old:
                continue
            for rec in self:
                ov, nv = old[fname][rec.id], rec[fname]
                if ov == nv:
                    continue
                header = rec._chatter_header()
                if not header:
                    continue
                cache_key = (header._name, header.id)
                if fname in QTY_FIELDS:
                    if cache_key not in month_label_cache:
                        month_label_cache[cache_key] = self._month_labels(header)
                    label = month_label_cache[cache_key][fname]
                    ov_disp, nv_disp = self._format_qty(ov), self._format_qty(nv)
                else:
                    label = static_label
                    ov_disp = ov if ov not in (False, None, '') else 'Trống'
                    nv_disp = nv if nv not in (False, None, '') else 'Trống'
                changes_by_header.setdefault(header, []).append((
                    str(ov_disp), str(nv_disp),
                    '%s - Mã hàng %s' % (label, rec.ma_hang or ''),
                ))

        for header, changes in changes_by_header.items():
            if not changes:
                continue
            items = ''.join(
                "<li>"
                "<b class='o-mail-Message-trackingOld me-1 px-1 text-muted fw-bold'>%s</b>"
                "<i class='o_TrackingValue_separator fa fa-long-arrow-right mx-1 text-600' role='img'></i>"
                "<b class='o-mail-Message-trackingNew me-1 fw-bold text-info'>%s</b>"
                "<span class='o-mail-Message-trackingField ms-1 fst-italic text-muted'>(%s)</span>"
                "</li>" % (escape(old_val), escape(new_val), escape(label))
                for old_val, new_val, label in changes
            )
            self._post_scoped_message(header, Markup("<ul>%s</ul>") % Markup(items))

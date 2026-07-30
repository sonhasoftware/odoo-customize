# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

MONTH_COUNT = 4
QTY_FIELDS = tuple('qty_t%d' % idx for idx in range(MONTH_COUNT))


class KeHoachLineMixin(models.AbstractModel):
    """Phần dùng chung của dòng kế hoạch kinh doanh (KD) và sản xuất (SX):
    danh mục mã hàng, đánh STT, ghi hàng loạt khi import, khóa theo trạng thái
    kỳ và ghi log chatter dạng bảng.
    """
    _name = 'ke.hoach.line.mixin'
    _description = 'Dòng kế hoạch theo tháng (dùng chung KD/SX)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id, sequence, id'

    _CHATTER_SCOPE = 'kd'
    _LINE_LABEL = 'kế hoạch'
    _TRACKED_FIELDS = {
        'ma_hang': 'Mã hàng',
        'ma_sap': 'Mã',
        **{fname: False for fname in QTY_FIELDS},
    }
    # Cột được phép ghi bằng SQL hàng loạt khi import, kèm kiểu Postgres.
    _BULK_IMPORT_COLUMNS = {
        'ma_hang': 'varchar',
        'note': 'varchar',
        'sequence': 'int',
        **{fname: 'numeric' for fname in QTY_FIELDS},
    }

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    sequence = fields.Integer(string='STT', default=10, index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True, required=True)
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
    ma_sap = fields.Char(string='Mã', index=True)
    qty_t0 = fields.Float(string='Tháng T0', digits=(16, 2))
    qty_t1 = fields.Float(string='Tháng T+1', digits=(16, 2))
    qty_t2 = fields.Float(string='Tháng T+2', digits=(16, 2))
    qty_t3 = fields.Float(string='Tháng T+3', digits=(16, 2))
    note = fields.Char(string='Ghi chú')

    @api.depends('ma_sap')
    def _compute_ma_hang_meta(self):
        codes = {(rec.ma_sap or '').strip() for rec in self if (rec.ma_sap or '').strip()}
        meta_map = self.env['ma.hang'].get_mdm_sap_meta_map(codes)
        for rec in self:
            code = (rec.ma_sap or '').strip()
            meta = meta_map.get(code, {}) if code else {}
            rec.ten_hang = meta.get('ten_hang', '')
            rec.nganh_hang = meta.get('nganh_hang_id') or False

    # ------------------------------------------------------------------
    # STT
    # ------------------------------------------------------------------
    @api.model
    def _assign_create_sequences(self, vals_list):
        next_by_period = {}
        for vals in vals_list:
            if vals.get('sequence') or not vals.get('period_id'):
                continue
            pid = vals['period_id']
            if pid not in next_by_period:
                last = self.search([('period_id', '=', pid)], order='sequence desc', limit=1)
                next_by_period[pid] = last.sequence if last else 0
            next_by_period[pid] += 10
            vals['sequence'] = next_by_period[pid]

    # ------------------------------------------------------------------
    # Ghi hàng loạt khi import
    # ------------------------------------------------------------------
    @api.model
    def _sql_bulk_import_update(self, updates):
        """Ghi hàng loạt khi import"""
        if not updates:
            return
        columns = [
            col for col in self._BULK_IMPORT_COLUMNS
            if col in updates[0][1]
        ]
        if not columns:
            return

        ids = [row_id for row_id, _vals in updates]
        params = [self.env.uid, ids]
        for col in columns:
            pg_type = self._BULK_IMPORT_COLUMNS[col]
            if pg_type == 'varchar':
                default = ''
            elif col == 'sequence':
                default = 10
            else:
                default = 0.0
            params.append([vals.get(col) or default for _row_id, vals in updates])

        assignments = ',\n                '.join(
            '%s = data.%s' % (col, col) for col in columns
        )
        unnest_cols = ',\n                       '.join(
            'unnest(%%s::%s[]) AS %s' % (self._BULK_IMPORT_COLUMNS[col], col)
            for col in columns
        )
        self.env.cr.execute("""
            UPDATE {table} AS k SET
                {assignments},
                write_uid = %s,
                write_date = NOW() AT TIME ZONE 'UTC'
            FROM (
                SELECT unnest(%s::int[]) AS id,
                       {unnest_cols}
            ) AS data
            WHERE k.id = data.id
        """.format(
            table=self._table,
            assignments=assignments,
            unnest_cols=unnest_cols,
        ), params)
        self.browse(ids).invalidate_recordset(columns + ['write_uid', 'write_date'])

    # ------------------------------------------------------------------
    # Ràng buộc
    # ------------------------------------------------------------------
    @api.constrains('ma_sap', 'period_id')
    def _check_ma_sap_in_catalog(self):
        if self.env.context.get('is_importing'):
            return
        for rec in self.filtered(
            lambda r: r.period_id.state == 'ke_hoach' and (r.ma_sap or '').strip()
        ):
            if not self.env['ma.hang'].sap_exists_in_mdm(rec.ma_sap.strip()):
                raise ValidationError(
                    _('Mã "%s" không có trong MDM (mdm.tong.hop.line).') % rec.ma_sap
                )

    def _check_period_editable(self):
        locked = self.filtered(lambda rec: rec.period_id and rec.period_id.state != 'ke_hoach')
        if locked:
            raise UserError(
                _('%s đã khóa vì kỳ kế hoạch đã sang bước sau.')
                % self._LINE_LABEL.capitalize()
            )

    @api.model
    def _check_period_open(self, vals_list):
        period_ids = {v['period_id'] for v in vals_list if v.get('period_id')}
        if not period_ids:
            return
        for period in self.env['ke.hoach.vat.tu'].browse(list(period_ids)):
            if period.state != 'ke_hoach':
                raise UserError(
                    _('%s đã khóa vì kỳ kế hoạch đã sang bước sau.')
                    % self._LINE_LABEL.capitalize()
                )

    # ------------------------------------------------------------------
    # Hook cho model con
    # ------------------------------------------------------------------
    @api.model
    def _prepare_create_vals(self, vals_list):
        return

    def _post_create_sync(self):
        return

    def _post_write_sync(self):
        return

    def _post_unlink_sync(self, periods):
        return

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        self._check_period_open(vals_list)
        self._prepare_create_vals(vals_list)
        self._assign_create_sequences(vals_list)
        records = super().create(vals_list)
        if not self.env.context.get('is_importing'):
            self._log_action_table(records, action='create')
        records._post_create_sync()
        return records

    def write(self, vals):
        if not self.env.context.get('skip_period_lock'):
            self._check_period_editable()
        old = {
            fname: {rec.id: rec[fname] for rec in self}
            for fname in self._TRACKED_FIELDS if fname in vals
        }
        res = super().write(vals)
        if self.env.context.get('is_importing'):
            return res
        self._log_tracked_changes(old)
        self._post_write_sync()
        return res

    def unlink(self):
        self._check_period_editable()
        if not self.env.context.get('is_importing'):
            self._log_action_table(self, action='unlink')
        periods = self.mapped('period_id')
        res = super().unlink()
        self._post_unlink_sync(periods)
        return res

    # ------------------------------------------------------------------
    # Chatter
    # ------------------------------------------------------------------
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
        for idx in range(MONTH_COUNT):
            cur_month, cur_year = month + idx, year
            while cur_month > 12:
                cur_month -= 12
                cur_year += 1
            labels['qty_t%d' % idx] = 'Tháng %02d/%s' % (cur_month, cur_year)
        return labels

    def _tracking_values(self):
        return {
            'don_vi': self.company_id.sudo().company_code or self.company_id.sudo().name or '',
            'nganh': self.nganh_hang.ten if self.nganh_hang else '',
            'ten_hang': self.ten_hang or '',
            'ma_hang': self.ma_hang or '',
            'ma_sap': self.ma_sap or '',
            **{fname: self._format_qty(self[fname]) for fname in QTY_FIELDS},
        }

    def _post_scoped_message(self, period, body):
        period.with_context(vat_tu_chatter_scope=self._CHATTER_SCOPE).message_post(body=body)

    @api.model
    def _log_action_table(self, records, action='create'):
        period_lines = {}
        for rec in records.filtered('period_id'):
            period_lines.setdefault(rec.period_id, []).append(rec._tracking_values())

        for period, lines in period_lines.items():
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
                period,
                self._build_tracking_table_html(title, lines, period, action=action),
            )

    @api.model
    def _build_tracking_table_html(self, title, lines, period, action='create'):
        month_labels = self._month_labels(period)

        def cell(value):
            value = escape(value)
            return Markup("<del class='text-muted'>%s</del>") % value if action == 'unlink' else value

        rows = ''.join(
            "<tr>"
            f"<td>{cell(vals['don_vi'])}</td>"
            f"<td>{cell(vals['nganh'])}</td>"
            f"<td>{cell(vals['ten_hang'])}</td>"
            f"<td>{cell(vals['ma_hang'])}</td>"
            f"<td>{cell(vals['ma_sap'])}</td>"
            + ''.join(
                f"<td class='text-end'>{cell(vals[fname])}</td>"
                for fname in QTY_FIELDS
            )
            + "</tr>"
            for vals in lines
        )
        month_headers = ''.join(
            Markup("<th class='text-end'>%s</th>") % escape(month_labels[fname])
            for fname in QTY_FIELDS
        )
        return Markup("""
            <p class="mb-2">%s</p>
            <div class="table-responsive">
                <table class="table table-sm table-bordered o_main_table mb-0" style="font-size: 13px;">
                    <thead class="bg-light">
                        <tr>
                            <th>Đơn vị</th>
                            <th>Ngành hàng</th>
                            <th>Tên hàng</th>
                            <th>Mã hàng</th>
                            <th>Mã</th>
                            %s
                        </tr>
                    </thead>
                    <tbody>%s</tbody>
                </table>
            </div>
        """) % (Markup(title), Markup(month_headers), Markup(rows))

    def _log_tracked_changes(self, old):
        """Gom mọi thay đổi trong cùng một kỳ vào 1 message để tránh spam
        chatter khi user sửa nhiều dòng cùng lúc."""
        changes_by_period = {}
        month_label_cache = {}
        for fname, static_label in self._TRACKED_FIELDS.items():
            if fname not in old:
                continue
            for rec in self:
                ov, nv = old[fname][rec.id], rec[fname]
                if ov == nv:
                    continue
                if fname in QTY_FIELDS:
                    month_labels = month_label_cache.setdefault(
                        rec.period_id.id, self._month_labels(rec.period_id),
                    )
                    label = month_labels[fname]
                    ov_disp, nv_disp = self._format_qty(ov), self._format_qty(nv)
                else:
                    label = static_label
                    ov_disp = ov if ov not in (False, None, '') else 'Trống'
                    nv_disp = nv if nv not in (False, None, '') else 'Trống'
                changes_by_period.setdefault(rec.period_id, []).append((
                    str(ov_disp), str(nv_disp),
                    '%s - Mã hàng %s' % (label, rec.ma_hang or ''),
                ))

        for period, changes in changes_by_period.items():
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
            self._post_scoped_message(period, Markup("<ul>%s</ul>") % Markup(items))

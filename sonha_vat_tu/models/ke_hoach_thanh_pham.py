# -*- coding: utf-8 -*-
import re
from markupsafe import Markup
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KeHoachThanhPham(models.Model):
    _name = 'ke.hoach.thanh.pham'
    _description = 'B1 - Kế hoạch thành phẩm theo tháng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id, company_id, month_key, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ',
        ondelete='cascade', index=True)

    company_id = fields.Many2one(
        'res.company', string='Công ty',
        default=lambda self: self.env.company, index=True)

    nganh_hang_id = fields.Many2one(
        'nganh.hang', string='Ngành hàng', index=True)
    dong_hang_id = fields.Many2one(
        'dong.hang', string='Dòng hàng', index=True)
    ma_hang_id = fields.Many2one(
        'ma.hang', string='Mã hàng', index=True)
    ma_hang = fields.Char(string='Mã hàng', index=True)
    ma_sap = fields.Char(
        string='Mã SAP', index=True)
    ma_bom = fields.Char(string='Mã BOM', index=True)

    month_key = fields.Char(
        string='Tháng', index=True)
    qty = fields.Float(
        string='Số lượng', digits=(16, 2))

    note = fields.Char(string='Ghi chú')

    _sql_constraints = [
        ('uniq_row',
         'unique(period_id, company_id, ma_sap, month_key)',
         'Trùng dòng: (Kỳ, Công ty, Mã SAP, Tháng) phải duy nhất!'),
    ]

    @api.constrains('month_key')
    def _check_month_key(self):
        pattern = re.compile(r'^(0[1-9]|1[0-2])/\d{4}$')
        for rec in self:
            if rec.month_key and not pattern.match(rec.month_key):
                raise ValidationError(
                    'Tháng phải đúng định dạng MM/YYYY, ví dụ 04/2026.'
                )

    @api.onchange('ma_hang_id')
    def _onchange_ma_hang(self):
        for rec in self:
            if rec.ma_hang_id:
                rec.ma_hang = rec.ma_hang_id.code
                rec.ma_sap = rec.ma_hang_id.ma_sap or rec.ma_sap
                rec.nganh_hang_id = rec.ma_hang_id.nganh_hang_id
                rec.dong_hang_id = rec.ma_hang_id.dong_hang_id

    @api.model_create_multi
    def create(self, vals_list):
        MaHang = self.env['ma.hang']
        for vals in vals_list:
            if vals.get('ma_hang_id'):
                master = MaHang.browse(vals['ma_hang_id'])
                vals.setdefault('ma_hang', master.code)
                vals.setdefault('ma_sap', master.ma_sap)
                vals.setdefault('nganh_hang_id', master.nganh_hang_id.id)
                vals.setdefault('dong_hang_id', master.dong_hang_id.id)

            if not vals.get('ma_hang_id') and vals.get('ma_sap'):
                master = MaHang.search([('ma_sap', '=', vals['ma_sap'])], limit=1)
                if master:
                    vals['ma_hang_id'] = master.id
                    vals.setdefault('ma_hang', master.code)
                    vals.setdefault('nganh_hang_id', master.nganh_hang_id.id)
                    vals.setdefault('dong_hang_id', master.dong_hang_id.id)

            if not vals.get('company_id') and vals.get('period_id'):
                period = self.env['ke.hoach.vat.tu'].browse(vals['period_id'])
                if period.company_id:
                    vals['company_id'] = period.company_id.id
                    
        records = super().create(vals_list)
        
        # Log khi Thêm dòng trên UI (bỏ qua nếu đang chạy import wizard)
        if not self.env.context.get('is_importing'):
            self._log_action_table(records, action='create')
                
        return records

    def unlink(self):
        self._log_action_table(self, action='unlink')
        return super().unlink()

    @api.model
    def _log_action_table(self, records, action='create'):
        if not records:
            return
        period_dict = {}
        for rec in records:
            if not rec.period_id:
                continue
            if rec.period_id not in period_dict:
                period_dict[rec.period_id] = []
            
            qty_str = "{:,.2f}".format(rec.qty or 0.0).replace(',', 'X').replace('.', ',').replace('X', '.')
            period_dict[rec.period_id].append({
                'nganh': rec.nganh_hang_id.name if rec.nganh_hang_id else '',
                'dong': rec.dong_hang_id.name if rec.dong_hang_id else '',
                'ma_hang': rec.ma_hang or '',
                'ma_sap': rec.ma_sap or '',
                'ma_bom': rec.ma_bom or '',
                'month_key': rec.month_key or '',
                'qty': qty_str
            })

        for period, lines in period_dict.items():
            if not lines:
                continue
            if action == 'create':
                title = f"<span class='text-success'><i class='fa fa-plus-circle'></i> <b>Đã thêm {len(lines)} dòng kế hoạch mới:</b></span>"
            else:
                title = f"<span class='text-danger'><i class='fa fa-trash'></i> <b>Đã xóa {len(lines)} dòng kế hoạch:</b></span>"
            msg = self.env['ke.hoach.thanh.pham']._build_tracking_table_html(title, lines, action=action)
            period.message_post(body=msg)

    @api.model
    def _build_tracking_table_html(self, title, lines, action='create'):
        table_html = """
        <div class="table-responsive">
        <table class="table table-sm table-bordered o_main_table mb-0" style="font-size: 13px;">
            <thead class="bg-light">
                <tr>
                    <th>Ngành hàng</th>
                    <th>Dòng hàng</th>
                    <th>Mã hàng</th>
                    <th>Mã SAP</th>
                    <th>Mã BOM</th>
                    <th>Tháng</th>
                    <th class="text-end">Số lượng</th>
                </tr>
            </thead>
            <tbody>
        """
        for vals in lines:
            if action == 'unlink':
                wrap_s = "<del class='text-muted'>"
                wrap_e = "</del>"
            else:
                wrap_s = ""
                wrap_e = ""
                
            table_html += f"""
                <tr>
                    <td>{wrap_s}{vals['nganh']}{wrap_e}</td>
                    <td>{wrap_s}{vals['dong']}{wrap_e}</td>
                    <td>{wrap_s}{vals['ma_hang']}{wrap_e}</td>
                    <td>{wrap_s}{vals['ma_sap']}{wrap_e}</td>
                    <td>{wrap_s}{vals['ma_bom']}{wrap_e}</td>
                    <td>{wrap_s}{vals['month_key']}{wrap_e}</td>
                    <td class="text-end">{wrap_s}{vals['qty']}{wrap_e}</td>
                </tr>
            """
        table_html += """
            </tbody>
        </table>
        </div>
        """
        return Markup(f"<p class='mb-2'>{title}</p>{table_html}")

    def create_tracking_message(self, old_value, new_value, field_label):
        self.ensure_one()
        message = Markup(
            "<li><b class='o-mail-Message-trackingOld me-1 px-1 text-muted fw-bold'>%s</b> "
            "<i class='o_TrackingValue_separator fa fa-long-arrow-right mx-1 text-600' role='img'></i>"
            "<b class='o-mail-Message-trackingNew me-1 fw-bold text-info'>%s</b> "
            "<span class='o-mail-Message-trackingField ms-1 fst-italic text-muted'>(%s)</span></li>"
        ) % (old_value, new_value, field_label)
        self.period_id.message_post(body=Markup("<ul>%s</ul>") % message)

    def write(self, vals):
        TRACKED = {'ma_sap': 'Mã SAP', 'ma_bom': 'Mã BOM', 'month_key': 'Tháng', 'qty': 'Số lượng'}

        old = {f: {r.id: r[f] for r in self} for f in TRACKED if f in vals}
        res = super().write(vals)

        for f in old:
            for rec in self:
                ov, nv = old[f][rec.id], rec[f]
                if ov != nv:
                    rec.create_tracking_message(
                        ov if ov not in (False, None, '') else 'Trống',
                        nv if nv not in (False, None, '') else 'Trống',
                        f'{TRACKED[f]} - Mã hàng {rec.ma_hang}',
                    )

        return res



from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class ExpShipment(models.Model):
    _name = 'exp.shipment'
    _order = 'date_shipment ASC, id ASC'

    contract_id = fields.Many2one('exp.contract', string="Hợp đồng", required=True, store=True)
    so_cont_number = fields.Char(string="Số cont, Số SO", store=True)
    quantity = fields.Float(string="Số lượng xuất", store=True)
    date_shipment = fields.Date(string="Ngày xuất hàng", required=True, store=True)
    status = fields.Selection([('draft', "Chưa tạo hóa đơn, Packing List"),
                               ('invoice', "Đã tạo hóa đơn, chưa tạo Packing List"),
                               ('pkl', "Chưa tạo hóa đơn, đã tạo Packing List"),
                               ('done', "Đã tạo hóa đơn, Packing List")],
                              compute="compute_status",
                              string="Trạng thái hóa đơn", default='draft', store=True)
    number_time = fields.Integer(string="Lần xuất hàng", compute="_compute_sequence", store=True)
    note = fields.Text(string="Ghi chú", store=True)

    contract_no = fields.Char(string="Số hợp đồng", store=True)
    customer_id = fields.Many2one('exp.customer', string="Khách hàng", store=True)
    state_id = fields.Many2one('exp.contract.state', string="Trạng thái", store=True)
    po_number = fields.Char(string="Số PO", store=True)
    total_amount = fields.Float(string="Tổng tiền", store=True)
    deposit_percent = fields.Float(string="% cọc", store=True)
    deposit_amount = fields.Float(string="Tiền cọc", store=True)
    currency = fields.Many2one('exp.config.currency', string="Tiền tệ", store=True)
    sign_date = fields.Date(string="Ngày ký hợp đồng", store=True)
    lc_required = fields.Boolean(string="Có yêu cầu LC không", store=True)
    lc_file = fields.Many2many('ir.attachment',
                               'exp_shipment_lc_attachment_rel',
                               'contract_id',
                               'attachment_id', string="File điều kiện LC", store=True)
    lc_file_name = fields.Char(string="Tên file điều kiện LC", store=True)
    created_by = fields.Many2one('res.users', string="Người tạo", store=True)
    created_date = fields.Date(string="Ngày tạo", store=True)
    shipping = fields.Text(string="Vận chuyển", store=True)
    payment = fields.Text(string="Thanh toán", store=True)
    note_contract = fields.Text(string="Ghi chú", store=True)
    cont_request = fields.Integer(string="Số lượng CONT yc", store=True)

    invoice = fields.Boolean(string="Tạo Invoice", compute="onchange_file_invoice", store=True)
    packing_list = fields.Boolean(string="Tạo PKL", compute="onchange_file_pkl", store=True)
    date_invoice = fields.Date(string="Ngày tạo hóa đơn", store=True)
    date_packing_list = fields.Date(string="Ngày tạo PKL", store=True)
    line_product = fields.One2many('exp.product', 'so_id', string="Sản phẩm", store=True)
    file_invoice = fields.Many2many('ir.attachment',
                                    'exp_shipment_invoice_attachment_rel',
                                    'contract_id',
                                    'attachment_id', string="File Invoice", store=True)
    file_invoice_name = fields.Char(string="Tên file Invoice", store=True)
    file_pkl = fields.Many2many('ir.attachment',
                                'exp_shipment_pkl_attachment_rel',
                                'contract_id',
                                'attachment_id', string="File Packing List", store=True)
    file_pkl_name = fields.Char(string="Tên file Packing List", store=True)

    shipping_port_from = fields.Many2one('exp.config.port', string="Cảng bốc hàng",
                                         domain="[('type', '=', 'port_form')]", store=True)
    shipping_port_to = fields.Many2one('exp.config.port', string="Cảng dỡ hàng",
                                       domain="[('type', '=', 'port_to')]", store=True)
    shipping_time = fields.Date(string="Thời gian", store=True)
    shipping_country = fields.Many2one('exp.config.country', string="Quốc gia", store=True)
    payment_term = fields.Many2one('exp.config.term', string="Điều khoản thanh toán", store=True)
    bank = fields.Many2one('exp.config.bank', string="Ngân hàng", store=True)
    payment_note = fields.Text(string="Ghi chú thêm khác", store=True)

    export_required_date = fields.Date(string="Ngày yêu cầu xuất hàng", store=True)

    readonly_file_char = fields.Char(default="Không có file.", store=True)
    contract_file = fields.Many2many('ir.attachment',
                                     'exp_shipment_contract_attachment_rel',
                                     'contract_id',
                                     'attachment_id', string="File hợp đồng cứng", store=True)
    contract_file_name = fields.Char(string="Tên file hợp đồng cứng", store=True)
    deposit_payment_file = fields.Many2many('ir.attachment',
                                            'exp_shipment_deposit_attachment_rel',
                                            'contract_id',
                                            'attachment_id', string="File điện chuyển tiền cọc", store=True)
    deposit_payment_file_name = fields.Char(string="Tên file chuyển tiền cọc", store=True)
    invoice_number = fields.Char(string="Số hóa đơn", store=True)

    def write(self, vals):
        res = super(ExpShipment, self).write(vals)
        for r in self:
            now = datetime.today().date()
            if 'file_invoice' in vals:
                r.date_invoice = str(now) if r.file_invoice else None
            if 'file_pkl' in vals:
                r.date_packing_list = str(now) if r.file_pkl else None
        return res

    @api.depends('file_invoice')
    def onchange_file_invoice(self):
        for r in self:
            if r.file_invoice:
                r.sudo().write({'invoice': True})
            else:
                r.sudo().write({'invoice': False})

    @api.depends('file_pkl')
    def onchange_file_pkl(self):
        for r in self:
            if r.file_pkl:
                r.packing_list = True
            else:
                r.packing_list = False

    @api.depends('date_shipment')
    def _compute_sequence(self):
        records = self.search([('contract_id', '=', self.contract_id.id)], order='date_shipment asc, id asc')
        seq = 1
        for rec in records:
            rec.number_time = seq
            seq += 1

    @api.depends('invoice', 'packing_list')
    def compute_status(self):
        for r in self:
            if r.invoice and r.packing_list:
                r.status = 'done'
            elif r.invoice and not r.packing_list:
                r.status = 'invoice'
            elif not r.invoice and r.packing_list:
                r.status = 'pkl'
            else:
                r.status = 'draft'

    def action_popup_invoice(self):
        for r in self:
            self.sudo().write({
                'contract_no': r.contract_id.contract_no,
                'customer_id': r.contract_id.customer_id.id,
                'state_id': r.contract_id.state_id.id,
                'po_number': r.contract_id.po_number,
                'total_amount': r.contract_id.total_amount,
                'deposit_percent': r.contract_id.deposit_percent,
                'deposit_amount': r.contract_id.deposit_amount,
                'currency': r.contract_id.currency,
                'sign_date': str(r.contract_id.sign_date),
                'lc_required': r.contract_id.lc_required,
                'lc_file': [(6, 0, r.contract_id.lc_file.ids)],
                'note_contract': r.contract_id.note,
                'cont_request': r.contract_id.cont_request,
                'shipping_time': str(r.contract_id.shipping_time),
                'shipping_port_from': r.contract_id.shipping_port_from.id,
                'shipping_port_to': r.contract_id.shipping_port_to.id,
                'shipping_country': r.contract_id.shipping_country.id,
                'payment_term': r.contract_id.payment_term.id,
                'bank': r.contract_id.bank.id,
                'payment_note': r.contract_id.payment_note,
                'created_by': r.contract_id.created_by,
                'created_date': r.contract_id.created_date,
                'export_required_date': str(r.contract_id.export_required_date),
                'contract_file': [(6, 0, r.contract_id.contract_file.ids)],
                'deposit_payment_file': [(6, 0, r.contract_id.deposit_payment_file.ids)],
                'readonly_file_char': "Không có file."
            })

            return {
                'name': 'Tạo Invoice, Packing list',
                'type': 'ir.actions.act_window',
                'res_model': 'exp.shipment',
                'view_mode': 'form',
                'res_id': self.id,
                'view_id': self.env.ref('sonha_ql_xuat_khau.view_create_invoice_form').id,
                'target': 'new',
                'context': {
                    'create': False,
                    'edit': True,
                }
            }

    def action_create_pkl(self):
        for r in self:
            now = datetime.today().date()
            r.date_packing_list = str(now)
            r.packing_list = True
            return {
                'name': 'Tạo Invoice, Packing list',
                'type': 'ir.actions.act_window',
                'res_model': 'exp.shipment',
                'view_mode': 'form',
                'res_id': self.id,
                'view_id': self.env.ref('sonha_ql_xuat_khau.view_create_invoice_form').id,
                'target': 'new',
                'context': {
                    'create': False,
                    'edit': False,
                }
            }

    def action_create_invoice(self):
        for r in self:
            documents = self.env['exp.export.document'].sudo().search([('type', '=', 'invoice')])
            vals = [(0, 0, {
                'document': doc.id,
                'file_name': doc.name,
                'radio_tick': False,
            }) for doc in documents]
            return {
                'name': 'Chọn mẫu tài liệu',
                'type': 'ir.actions.act_window',
                'res_model': 'popup.export.document',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_key': 'invoice',
                    'default_contract_id': r.contract_id.id,
                    'default_documents': vals,
                    'default_shipment_id': r.id,
                }
            }
            # now = datetime.today().date()
            # r.date_invoice = str(now)
            # r.invoice = True
            # return {
            #     'name': 'Tạo Invoice, Packing list',
            #     'type': 'ir.actions.act_window',
            #     'res_model': 'exp.shipment',
            #     'view_mode': 'form',
            #     'res_id': self.id,
            #     'view_id': self.env.ref('sonha_ql_xuat_khau.view_create_invoice_form').id,
            #     'target': 'new',
            #     'context': {
            #         'create': False,
            #         'edit': False,
            #     }
            # }

    def action_show_detail(self):
        return {
            'name': 'Chi tiết hàng hóa xuất',
            'type': 'ir.actions.act_window',
            'res_model': 'exp.shipment',
            'view_mode': 'form',
            'res_id': self.id,
            'view_id': self.env.ref('sonha_ql_xuat_khau.view_product_detail_form').id,
            'target': 'new',
            'context': {
                'create': False,
                'edit': False,
            }
        }


class ExpProduct(models.Model):
    _name = 'exp.product'

    contract_id = fields.Many2one('exp.contract', store=True)
    number_order = fields.Integer(string="STT", store=True)
    product_code = fields.Char(string="Mã hàng hóa", store=True)
    product_name = fields.Char(string="Tên hàng hóa", store=True)
    quantity = fields.Char(string="Số lượng", store=True)
    unit = fields.Char(string="Đơn vị tính", store=True)
    so_id = fields.Many2one('exp.shipment', store=True)
    so_number = fields.Char(string="Số SO", store=True)
    cay_uom = fields.Char(store=True)
    ton_uom = fields.Char(store=True)
    export_ton = fields.Float(string="Tổng khối lượng", compute="_compute_total_ton", store=True)

    @api.depends('ton_uom', 'cay_uom', 'quantity')
    def _compute_total_ton(self):
        for r in self:
            if r.ton_uom and r.cay_uom and r.quantity:
                quantity = float(r.quantity.split('.')[0])
                cay_uom = float(r.cay_uom or 0)
                ton_uom = float(r.ton_uom or 0)
                total_ton = round(((quantity * (cay_uom/ton_uom)) / 1000), 2)
                r.export_ton = total_ton
            else:
                r.export_ton = 0

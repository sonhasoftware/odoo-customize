from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class ReturnCustomer(models.Model):
    _name = 'return.customer'

    number_receipts = fields.Char(string="Số phiếu")
    sap_document = fields.Char(string="XNGH/CT SAP")
    customer_name = fields.Char(string="Họ và tên", compute="fillter_data_customer", store=True)
    phone_number = fields.Char(string="Điện thoại", compute="fillter_data_customer", store=True)
    address = fields.Text(string="Địa chỉ", compute="fillter_data_customer", store=True)
    product_code = fields.Char(string="Mã sản phẩm")
    product_name = fields.Char(string="Tên sản phẩm")
    unit = fields.Char(string="ĐVT")
    request_amount = fields.Integer(string="Số lượng yêu cầu")
    import_amount = fields.Integer(string="Số lượng thực nhập")
    export_warehouse = fields.Char(string="Kho xuất")
    import_warehouse = fields.Char(string="Kho nhập")
    plant = fields.Char(string="Plant")
    note = fields.Text(string="Ghi chú")
    warranty_code = fields.Many2one('warranty.information', string="ID")
    branch = fields.Many2one('bh.branch', string="Chi nhánh")
    type = fields.Selection([('tth', "Trước thu hồi"),
                             ('sth', "Sau thu hồi"),
                             ('return', "Trả khách")], string="Loại")
    transfer_warehouse_ids = fields.One2many('transfer.warehouse', 'return_customer', string="Chuyển kho")
    delivery_confirmation = fields.Char(string="Phiếu XNGH")


    @api.depends('warranty_code')
    def fillter_data_customer(self):
        for r in self:
            r.customer_name = r.warranty_code.customer_information if r.warranty_code.customer_information else ''
            r.phone_number = r.warranty_code.mobile_customer if r.warranty_code.mobile_customer else ''
            r.address = r.warranty_code.address if r.warranty_code.address else ''

    def check_transfer_warehouse(self, record):
        warranty_information = self.env['warranty.information'].sudo().search([('id', '=', record.warranty_code.id)])
        if record and record.type == 'tth':
            warranty_information.transfer_warehouse = True
        else:
            warranty_information.transfer_warehouse = False

    def create(self, vals):
        record = super(ReturnCustomer, self).create(vals)
        transfer_warehouse = self.env['transfer.warehouse'].sudo().search([('return_customer', '=', record.id)])
        vals = {
            'customer_information': record.customer_name,
            'mobile_customer': record.phone_number,
            'address': record.address,
            'warranty_code': record.warranty_code.id,
            'return_customer': record.id
        }
        if transfer_warehouse:
            transfer_warehouse.sudo().write(vals)
        else:
            raise ValidationError("Không có dữ liệu sản phẩm!")
        self.check_transfer_warehouse(record)
        return record

    def write(self, vals):
        res = super(ReturnCustomer, self).write(vals)
        if 'warranty_code' in vals:
            raise ValidationError("Không thể sửa mã bảo hành của phiếu!")
        return res

    def unlink(self):
        for r in self:
            self.env['transfer.warehouse'].sudo().search([('return_customer', '=', r.id)]).unlink()
            warranty_information = self.env['warranty.information'].sudo().search([('id', '=', r.warranty_code.id)])
            warranty_information.transfer_warehouse = False
        return super(ReturnCustomer, self).unlink()

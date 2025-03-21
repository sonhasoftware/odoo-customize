from odoo import api, fields, models

class ReturnCustomer(models.Model):
    _name = 'return.customer'

    number_receipts = fields.Char(string="Số phiếu nhập")
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
            if r.warranty_code:
                r.customer_name = r.warranty_code.customer_information if r.warranty_code.customer_information else ''
                r.phone_number = r.warranty_code.mobile_customer if r.warranty_code.mobile_customer else ''
                r.address = r.warranty_code.address if r.warranty_code.address else ''
            else:
                r.customer_name = ''
                r.phone_number = ''
                r.address = ''

    def check_transfer_warehouse(self):
        warranty_information = self.env['warranty.information'].sudo().search([])
        for r in warranty_information:
            transfer_warehouse = self.env['return.customer'].sudo().search([('warranty_code', '=', r.id)])
            if transfer_warehouse and transfer_warehouse.type == 'tth':
                r.transfer_warehouse = True
            else:
                r.transfer_warehouse = False

    def create(self, vals):
        list_records = super(ReturnCustomer, self).create(vals)
        for record in list_records:
            transfer_warehouse = self.env['transfer.warehouse'].sudo().search([('return_customer', '=', record.id)])
            vals = {
                'customer_information': record.customer_name,
                'mobile_customer': record.phone_number,
                'address': record.address,
                'warranty_code': record.warranty_code.id
            }
            if transfer_warehouse:
                transfer_warehouse.sudo().write(vals)
        self.check_transfer_warehouse()
        return list_records

    def write(self, vals):
        res = super(ReturnCustomer, self).write(vals)
        for record in self:
            transfer_warehouse = self.env['transfer.warehouse'].sudo().search([('return_customer', '=', record.id)])
            vals = {
                'customer_information': record.customer_name,
                'mobile_customer': record.phone_number,
                'address': record.address,
                'warranty_code': record.warranty_code.id
            }
            if transfer_warehouse:
                transfer_warehouse.sudo().write(vals)
        self.check_transfer_warehouse()
        return res

    def unlink(self):
        for r in self:
            self.env['transfer.warehouse'].search([('return_customer', '=', r.id)]).unlink()
        remove = super(ReturnCustomer, self).unlink()
        self.check_transfer_warehouse()
        return remove

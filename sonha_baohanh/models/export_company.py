from odoo import api, fields, models

class ExportCompany(models.Model):
    _name = 'export.company'

    export_date = fields.Date(string="Ngày xuất", default=fields.Datetime.now)
    delivery_note = fields.Char(string="Phếu xuất")
    customer_name = fields.Char(string="Họ và tên", compute="fillter_data_customer", store=True)
    customer_phone = fields.Char(string="Số điện thoại", compute="fillter_data_customer", store=True)
    address = fields.Text(string="Địa chỉ", compute="fillter_data_customer", store=True)
    warranty_code = fields.Many2one('warranty.information', string="ID")
    branch_id = fields.Many2one('bh.branch', string="Đơn vị")
    product_code = fields.Char(string="Mã sản phẩm")
    product_name = fields.Char(string="Tên sản phẩm")
    export_warehouse = fields.Char(string="Mã kho xuất")
    unit = fields.Char(string="ĐVT")
    request_amount = fields.Integer(string="Số lượng yêu cầu")
    export_amount = fields.Integer(string="Số lượng thực xuất")
    note = fields.Text(string="Ghi chú")
    form_export_company = fields.One2many('form.export.company.rel', 'warranty_code', string="Sản phẩm", compute="_onchange_warranty_code", inverse="_inverse_data")

    @api.depends('warranty_code')
    def fillter_data_customer(self):
        for r in self:
            if r.warranty_code:
                r.customer_name = r.warranty_code.customer_information if r.warranty_code.customer_information else ''
                r.customer_phone = r.warranty_code.mobile_customer if r.warranty_code.mobile_customer else ''
                r.address = r.warranty_code.address if r.warranty_code.address else ''
            else:
                r.customer_name = ''
                r.customer_phone = ''
                r.address = ''

    @api.depends('warranty_code')
    def _onchange_warranty_code(self):
        for record in self:
            if record.warranty_code:
                record.form_export_company = self.env['form.export.company.rel'].search([('warranty_code', '=', record.warranty_code.id)])
            else:
                record.form_export_company = False

    def _inverse_data(self):
        for r in self:
            if r.form_export_company:
                for record in r.form_export_company:
                    record.write({'product_code': record.product_code})

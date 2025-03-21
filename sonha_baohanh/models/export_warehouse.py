from odoo import api, fields, models

class ExportWarehouse(models.Model):
    _name = 'export.warehouse'

    delivery_note = fields.Char(string="Phếu xuất")
    number_receipts = fields.Many2one('return.customer', string="Số phiếu nhập chờ trả khách")
    customer_name = fields.Char(string="Tên khách hàng", compute="fillter_data_customer", store=True)
    phone_number = fields.Char(string="Điện thoại", compute="fillter_data_customer", store=True)
    address = fields.Text(string="Địa chỉ", compute="fillter_data_customer", store=True)
    delivery_confirmation = fields.Char(string="Phiếu XNGH")
    export_date = fields.Date(string="Ngày xuất kho", default=fields.Datetime.now)
    driver = fields.Char(string="Người lái xe")
    branch_id = fields.Many2one('bh.branch', string="Đơn vị")
    warranty_code = fields.Many2one('warranty.information', string="ID bảo hành")
    form_export_id = fields.One2many('form.export.company.rel', 'warranty_code', string="Sản phẩm", compute="_onchange_warranty_code", inverse="_inverse_data")

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

    @api.depends('warranty_code')
    def _onchange_warranty_code(self):
        for record in self:
            if record.warranty_code:
                record.form_export_id = self.env['form.export.company.rel'].search([('warranty_code', '=', record.warranty_code.id)])
            else:
                record.form_export_id = False

    def _inverse_data(self):
        for r in self:
            if r.form_export_id:
                for record in r.form_export_id:
                    record.write({'product_code': record.product_code})
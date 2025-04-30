from odoo import api, fields, models

class TransferWarehouse(models.Model):
    _name = 'transfer.warehouse'
    _rec_name = 'warranty_code'

    warranty_code = fields.Many2one('warranty.information', string="ID")
    customer_information = fields.Char(string="Tên khách hàng")
    mobile_customer = fields.Char(string="Số điện thoại")
    address = fields.Text(string="Địa chỉ")
    product_code = fields.Many2one('sonha.product', string="Mã sản phẩm")
    product_name = fields.Char(string="Tên sản phẩm", compute="filter_product", store=True)
    unit = fields.Char(string="ĐVT", compute="filter_product", store=True)
    request_amount = fields.Integer(string="SL yêu cầu")
    receive_amount = fields.Integer(string="SL thực nhập")
    export_warehouse = fields.Char(string="Kho xuất")
    import_warehouse = fields.Char(string="Kho nhập")
    note = fields.Text(string="Ghi chú")
    branch_id = fields.Many2one('bh.branch', string="Chi nhánh")
    return_customer = fields.Many2one('return.customer', string="Nhập kho trả khách")

    @api.depends('product_code')
    def filter_product(self):
        for r in self:
            r.product_name = r.product_code.product_name if r.product_code.product_name else ''
            r.unit = r.product_code.unit if r.product_code.unit else ''

    def create(self, vals):
        record = super(TransferWarehouse, self).create(vals)
        record.sudo().write({"warranty_code": record.return_customer.warranty_code.id})
        return record

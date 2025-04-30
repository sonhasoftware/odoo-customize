from odoo import api, fields, models

class FormExportCompanyRel(models.Model):
    _name = 'form.export.company.rel'

    customer_name = fields.Char(string="Họ và tên")
    phone_number = fields.Char(string="Số điện thoại")
    address = fields.Text(string="Địa chỉ")
    warranty_code = fields.Many2one('warranty.information', string="ID")
    product_code = fields.Many2one('sonha.product', string="Mã sản phẩm")
    product_name = fields.Char(string="Tên sản phẩm")
    export_warehouse = fields.Char(string="Mã kho xuất")
    unit = fields.Char(string="ĐVT")
    request_amount = fields.Integer(string="Yêu cầu")
    export_amount = fields.Integer(string="Thực xuất")
    note = fields.Text(string="Ghi chú")
    plant = fields.Char(string="Plant")
    branch_id = fields.Many2one('bh.branch', string="Đơn vị")
    import_before_repair = fields.Many2one('import.before.repair', string="Id trước sửa chữa")
    export_company_date = fields.Date(string="Ngày xuất kho về công ty")
    delivery_note_to_com = fields.Char(string="Phiếu xuất về công ty")



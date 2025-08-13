from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MDCustomer(models.Model):
    _name = 'md.customer'

    customer_code = fields.Char("Mã khách hàng")
    customer_name = fields.Char("Tên khách hàng")
    cust_phone = fields.Char("Số điện thoại")
    address = fields.Char("Địa chỉ khách")
    tax_code = fields.Char("Mã số thuế")
    company_id = fields.Many2one('res.company', string="Đơn vị")
    customer_type_id = fields.Many2one('bp.type', string="Phân loại khách")
    customer_group_id = fields.Many2one('bp.group.account', string="Nhóm khách hàng")
    country_id = fields.Many2one('res.country', string='Quốc gia')
    state_id = fields.Many2one('res.country.state', string='Tỉnh thành')
    customer_class = fields.Selection([('domestic', "Trong nước"), ('abroad', "Nước ngoài")], string="Kiểu khách hàng")
    district_id = fields.Many2one('config.district', string="Quận/Huyện")
    ward_id = fields.Many2one('config.ward', string="Phường/xã")
    declare_customer = fields.Many2one('declare.md.customer')
    cccd_number = fields.Char("Số cccd")
    legal_representative = fields.Char("Đại diện pháp lý")
    mail_address = fields.Char("Email")
    old_customer_code = fields.Char("Mã khách hàng cũ")

    postal_code = fields.Char("Mã bưu điện")
    language = fields.Char("Ngôn ngữ", default="EN")
    fax_number = fields.Char("Số Fax")
    bank_number = fields.Char("Số tài khoản ngân hàng")
    bank_owner = fields.Char("Chủ tài khoản")
    sale_man = fields.Many2one('declare.md.saleman', "Nhân viên kinh doanh")
    region_manager = fields.Char("Quản lý vùng")
    area_manager = fields.Char("Quản lý khu vực")
    bank_country_code = fields.Many2one('bank.country', string="Mã quốc gia")
    bank_key = fields.Many2one('bank.data', string="Ngân hàng")

    customer_sale = fields.One2many('customer.sale', 'md_customer')

    company_code = fields.Many2one('company.code', "Mã công ty")
    vendor_code = fields.Char("Mã NCC liên kết")
    trading_partner = fields.Many2one('trading.partner', string="Công ty nội bộ")
    reconciliation_account = fields.Many2one('reconciliation.account', string="Tài khoản kế toán")
    payment_term = fields.Many2one('payment.term', string="Điều khoản thanh toán")
    payment_method = fields.Many2many('cus.payment.method', string="Phương thức thanh toán")

    credit_limit = fields.One2many('credit.limit', 'md_customer')

    relationship = fields.One2many('emp.relationship', 'md_customer')

    customer_short_name = fields.Char("Tên ngắn gọn")
    search_term = fields.Char("Mã tìm kiếm nhanh")
    search_term_2 = fields.Char("Mã NCC trên Odoo")

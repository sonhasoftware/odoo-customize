from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MDSupplier(models.Model):
    _name = 'md.supplier'

    name = fields.Char("Tên nhà cung cấp")
    supp_code = fields.Char("Mã nhà cc")
    supp_phone = fields.Char("Điện thoại")
    tax_code = fields.Char("Mã số thuế")
    address = fields.Char("Địa chỉ")
    supp_type = fields.Many2one('bp.type', string="Loại nhân viên")
    bp_group_account = fields.Many2one('bp.group.account', string="Nhóm NCC")
    company_id = fields.Many2one('res.company', string="Đơn vị")
    country_id = fields.Many2one('res.country', string='Quốc gia')
    state_id = fields.Many2one('res.country.state', string='Tỉnh thành', domain="[('country_id', '=', country_id)]")
    supp_class = fields.Selection([('domestic', "Trong nước"), ('abroad', "Nước ngoài")], string="Kiểu nhà cung cấp")
    district_id = fields.Many2one('config.district', string="Quận/Huyện", domain="[('state_id', '=', state_id)]")
    ward_id = fields.Many2one('config.ward', string="Phường/xã", domain="[('district_id', '=', district_id)]")
    declare_supplier = fields.Many2one('declare.md.supplier')

    postal_code = fields.Char("Mã bưu điện")
    mail_address = fields.Char("Email")
    old_vendor_code = fields.Char("Mã NCC trên hệ thống khác")
    language = fields.Char("Ngôn ngữ", default="EN", required=True)
    fax_number = fields.Char("Số Fax")
    bank_number = fields.Char("Số tài khoản ngân hàng")
    bank_owner = fields.Char("Chủ tài khoản")
    bank_country_code = fields.Many2one('bank.country', string="Mã quốc gia")
    bank_key = fields.Many2one('bank.data', string="Ngân hàng", domain="[('bank_country', '=', bank_country_code)]")
    industry = fields.Many2one('vendor.industry', string="Loại NCC(SX/TM)")
    form_of_org = fields.Many2one('form.organization', string="Hình thức sở hữu doanh nghiệp")
    deposit_proportion = fields.Char("Tỷ lệ đặt cọc")
    company_code = fields.Many2one('company.code', string="Mã công ty")

    trading_partner = fields.Many2one('trading.partner', string="Công ty nội bộ")
    customer_code = fields.Char("Mã nhân viên")
    reconciliation_account = fields.Many2one('reconciliation.account', string="Tài khoản kế toán")
    planning_group = fields.Many2one('planning.group', string="Nhóm quy hoạch")
    payment_term = fields.Many2one('payment.term', string="Điều khoản thanh toán")
    double_invoice = fields.Boolean("Kiểm tra hóa đơn trùng", default=True)
    payment_method = fields.Many2many('cus.payment.method', string="Phương thức thanh toán")
    clear_debt = fields.Boolean("Khấu trừ công nợ")

    vendor_purchase = fields.One2many('vendor.purchase', 'md_vendor')

    vendor_block = fields.Boolean("Khóa nhà cung cấp")



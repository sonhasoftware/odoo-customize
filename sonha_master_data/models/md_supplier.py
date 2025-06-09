from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MDSupplier(models.Model):
    _name = 'md.supplier'

    name = fields.Char("Tên nhà cc")
    supp_full_name = fields.Char("Tên đầy đủ")
    supp_code = fields.Char("Mã nhà cc")
    supp_registration = fields.Binary("Đăng ký kinh doanh")
    supp_job = fields.Char("Chức vụ")
    supp_phone = fields.Char("Điện thoại")
    sap_transfer = fields.Boolean("SAP transfer")
    tax_code = fields.Char("Mã số thuế")
    represent = fields.Char("Người đại diện")
    supp_type = fields.Many2one('supplier.type', string="Loại NCC")
    supp_group = fields.Many2one('supplier.group', string="Nhóm NCC")


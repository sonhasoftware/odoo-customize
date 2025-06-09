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
    customer_type_id = fields.Many2one('customer.type', string="Phân loại khách")
    customer_group_id = fields.Many2one('customer.group', string="Nhóm khách hàng")
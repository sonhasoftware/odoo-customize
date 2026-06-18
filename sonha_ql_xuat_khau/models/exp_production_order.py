from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpProductionOrder(models.Model):
    _name = 'exp.production.order'

    contract_id = fields.Many2one('exp.contract', string="Hợp đồng", store=True)
    order_no = fields.Char(string="Mã đơn xuất", store=True)
    product_code = fields.Char(string="Mã sản phẩm", store=True)
    product_name = fields.Char(string="Tên sản phẩm", store=True)
    quantity = fields.Float(string="Số lượng", store=True)
    status = fields.Char(string="Trạng thái đơn", store=True)
    excel_file = fields.Binary(string="File excel đính kèm", store=True)
    unit = fields.Char(string="Đơn vị tính", store=True)

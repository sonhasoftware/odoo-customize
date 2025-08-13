from odoo import models, fields, api


class TradingPartner(models.Model):
    _name = 'trading.partner'

    name = fields.Char("Công ty nội bộ")
    trading_partner_name = fields.Char("Tên")
    tax_code = fields.Char("Mã số thuế")
    address = fields.Char("Địa chỉ")

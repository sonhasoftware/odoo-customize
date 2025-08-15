from odoo import models, fields, api


class SonHaUom(models.Model):
    _name = 'sonha.uom'

    name = fields.Char("Đơn vị tính")
    category = fields.Selection([('unit', "Đơn vị"),
                                 ('length', "Độ dài/khoảng cách"),
                                 ('mass', "Khối lượng"),
                                 ('volume', "Thể tích"),
                                 ('time', "Thời gian")], string="Loại")
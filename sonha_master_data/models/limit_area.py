from odoo import models, fields, api


class LimitArea(models.Model):
    _name = 'limit.area'
    _rec_name = 'area'

    area = fields.Char("Vùng hạn mức")
    description = fields.Char("Diễn giải")
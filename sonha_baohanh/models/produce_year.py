from odoo import api, fields, models

class ProduceYear(models.Model):
    _name = 'produce.year'

    name = fields.Char(string="Năm")
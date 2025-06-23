from odoo import models, fields, api


class ConfigCar(models.Model):
    _name = 'config.car'

    company_id = fields.Many2one('res.company', string="Công ty")
    number_of_car = fields.Integer("Số lượng xe")

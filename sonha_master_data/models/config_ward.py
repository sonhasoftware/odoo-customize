from odoo import models, fields, api


class ConfigWard(models.Model):
    _name = 'config.ward'

    district_id = fields.Many2one('config.district', string="Quận/Huyện")
    name = fields.Char("Phường/Xã")

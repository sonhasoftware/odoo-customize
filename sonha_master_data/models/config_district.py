from odoo import models, fields, api


class ConfigDistrict(models.Model):
    _name = 'config.district'

    state_id = fields.Many2one('res.country.state', string="Tỉnh/Thành")
    name = fields.Char("Quận/Huyện")

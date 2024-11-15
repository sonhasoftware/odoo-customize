from odoo import api, fields, models


class ConfigStatus(models.Model):
    _name = 'config.status'
    _rec_name = 'it_status_name'

    user_status_name = fields.Char(string="Tên trạng thái")
    it_status_name = fields.Char(string="Tên trạng thái (IT)")
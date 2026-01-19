from odoo import api, fields, models


class ConfigOvertime(models.Model):
    _name = 'config.overtime'

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True)
    percent = fields.Selection([('100', "100%"),
                                ('150', "150%"),
                                ('200', "200%"),
                                ('250', "250%"),
                                ('300', "300%")],
                               string="Phần trăm", required=True)

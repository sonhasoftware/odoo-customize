from odoo import api, fields, models


class ConfigOvertime(models.Model):
    _name = 'config.overtime'

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True)
    percent = fields.Selection([('100', "100%"),
                                ('150', "150%"),
                                ('200', "200%"),
                                ('270', "270%"),
                                ('300', "300%"),
                                ('390', "390%")],
                               string="Phần trăm", required=True)

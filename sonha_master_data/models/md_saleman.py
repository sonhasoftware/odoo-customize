from odoo import models, fields, api


class MDSaleman(models.Model):
    _name = 'md.saleman'

    code = fields.Char("Mã NVKD")
    name = fields.Char("Tên NVKD")
    company_id = fields.Many2one('res.company', string="Đơn vị")

    declare_saleman = fields.Many2one('declare.md.saleman')
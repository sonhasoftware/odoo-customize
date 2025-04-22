from odoo import api, fields, models


class ConfigTemplateReport(models.Model):
    _name = 'config.template.report'

    name = fields.Char("Tên báo cáo")
    file = fields.Binary(string="Mẫu báo cáo", attachment=True)
    apply = fields.Many2one('ir.model')


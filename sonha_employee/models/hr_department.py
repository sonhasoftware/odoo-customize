from odoo import fields, models, _

class HrDepartment(models.Model):
    _inherit = 'hr.department'

    send_mail = fields.Boolean(string='Gửi mail', default=False)
    shift = fields.Many2one('config.shift', string="Ca làm việc")

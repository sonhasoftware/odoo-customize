from odoo import models, fields, api


class AssignStaff(models.TransientModel):
    _name = 'assign.staff'

    staff = fields.Many2one('declare.md.saleman', string="Nhân viên kinh doanh")
    customer = fields.Many2many('declare.md.customer', string="Khách hàng", domain="[('status', '=', 'draft')]")

    wizard_assign = fields.Many2one('wizard.assign.staff')
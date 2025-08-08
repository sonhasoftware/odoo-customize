from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class WizardAssignStaff(models.TransientModel):
    _name = 'wizard.assign.staff'

    assign_staff = fields.One2many('assign.staff', 'wizard_assign')

    def action_confirm(self):
        for r in self.assign_staff:
            r.customer.sudo().write({'sale_man': r.staff})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

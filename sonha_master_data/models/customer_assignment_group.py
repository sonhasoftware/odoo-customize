from odoo import models, fields, api


class CustomerAssignmentGroup(models.Model):
    _name = 'customer.assignment.group'
    _rec_name = 'description'

    code = fields.Char("Mã")
    description = fields.Char("Diễn giải")
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    ipr_request_ids = fields.One2many(
        "ipr.request",
        "employee_id",
        string="Purchase Request History",
    )


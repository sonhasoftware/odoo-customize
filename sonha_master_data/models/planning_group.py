from odoo import models, fields, api


class PlanningGroup(models.Model):
    _name = 'planning.group'
    _rec_name = 'display_name'

    name = fields.Char("Mã dự báo dòng tiền")
    description = fields.Char("Diễn giải")

    display_name = fields.Char(compute="compute_display_name", store=True)

    @api.depends('name', 'description')
    def compute_display_name(self):
        for r in self:
            if r.name and r.description:
                r.display_name = f"{r.name} - {r.description}"
            else:
                r.display_name = ""

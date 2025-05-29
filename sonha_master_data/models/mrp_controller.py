from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MRPController(models.Model):
    _name = 'mrp.controller'
    _rec_name = 'x_full_name'

    plant = fields.Many2many('stock.warehouse', string="Kho")
    mrp_controller = fields.Char("MRP Controller", required=True)
    mrp_controller_name = fields.Char("Tên MRP Controller", required=True)
    x_full_name = fields.Char("Tên đầy đủ", compute="get_full_name", store=True)

    @api.depends('mrp_controller', 'mrp_controller_name')
    def get_full_name(self):
        for r in self:
            if r.mrp_controller and r.mrp_controller_name:
                r.x_full_name = f"{r.mrp_controller} - {r.mrp_controller_name}"
            else:
                r.x_full_name = ""


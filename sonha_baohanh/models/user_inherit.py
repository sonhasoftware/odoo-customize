from odoo import api, fields, models


class User_Inherit(models.Model):
    _inherit = 'res.users'
    # _rec_name = 'combination'

    branch_ids = fields.Many2many(
         'bh.branch',
         string="Chi nhánh"
    )
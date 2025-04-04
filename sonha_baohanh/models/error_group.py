from odoo import api, fields, models


class ErrorGroup(models.Model):
    _name = 'error.group'
    _rec_name = 'error_group_name'

    error_group_code = fields.Char(string="Mã nhóm lỗi")
    error_group_name = fields.Char(string="Tên nhóm lỗi")
    # company_id = fields.Many2one("res.company", string="Công ty")

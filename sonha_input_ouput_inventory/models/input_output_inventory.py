from odoo import api, fields, models

class InputOutputInventory(models.Model):
    _name = 'input.output.inventory'

    id_record = fields.Char(string="ID")
    date = fields.Date(string="Ngày")
    content = fields.Char(string="Nội dung")
    status = fields.Many2one('config.status', string="Trạng thái")
    enter_emp = fields.Many2one('hr.employee', string="Người nhập")
    two_hundred_one = fields.Integer(string="201")
    three_hundred_four = fields.Integer(string="304")
    three_hundred_sixteen = fields.Integer(string="316")
    total = fields.Integer(string="Total", compute="count_total")

    @api.depends('two_hundred_one', 'three_hundred_four','three_hundred_sixteen')
    def count_total(self):
        for r in self:
            r.total = r.two_hundred_one + r.three_hundred_four + r.three_hundred_sixteen

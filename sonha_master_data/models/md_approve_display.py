from odoo import models, fields, api


class MDApproveDisplay(models.Model):
    _name = 'md.approve.display'
    _order = 'sequence_step,id'

    sequence_step = fields.Integer("Trình tự")
    level = fields.Selection([('suggest', "Đề xuất"),
                              ('examine', "Thẩm tra"),
                              ('review', "Soát xét"),
                              ('approve', "Phê duyệt"),
                              ('notice', "Nhận thông báo")],
                             string="Cấp duyệt")
    employee_id = fields.Many2one('hr.employee', string="Người duyệt")
    status = fields.Selection([('waiting', "Chờ duyệt"),
                              ('done', "Đã duyệt")], default='waiting', string="Trạng thái")
    md_customer = fields.Many2one('declare.md.customer')
    md_supplier = fields.Many2one('declare.md.supplier')
    md_product = fields.Many2one('declare.md.product')
    md_saleman = fields.Many2one('declare.md.saleman')

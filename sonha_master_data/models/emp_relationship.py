from odoo import models, fields, api


class EmpRelationship(models.Model):
    _name = 'emp.relationship'

    rel_category = fields.Selection([('zasm', "ZASM"), ('zrsm', "ZRSM")], string="Mối quan hệ")
    emp_relationship_1 = fields.Many2one('declare.md.saleman', string="Nhân viên")
    emp_relationship_2 = fields.Many2one('declare.md.saleman', string="Nhân viên")

    declare_customer = fields.Many2one('declare.md.customer')
    md_customer = fields.Many2one('md.customer')

from odoo import api, Command, fields, models, tools, SUPERUSER_ID, _, _lt


class Task(models.Model):
    _inherit = 'project.task'

    cap = fields.Many2one('project.project', string="Cấp")
    noi_dung_cv = fields.Text("Nội dung công việc")
    so_ngay_ht = fields.Float("Số ngày hoàn thành")
    ngay_bat_dau = fields.Date("Ngày bắt đầu")
    ngay_ket_thuc = fields.Date("Ngày kết thúc")
    ngay_hoan_thanh = fields.Date("Ngày hoàn thành")
    ns_lam = fields.Many2one('res.users', string="NS làm")
    chu_so_huu = fields.Many2one('res.users', string="Chủ sở hữu")


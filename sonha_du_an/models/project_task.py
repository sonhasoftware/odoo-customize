from datetime import timedelta

from odoo import api, fields, models


class Task(models.Model):
    _inherit = 'project.task'

    cap = fields.Many2one(
        'project.project',
        string="Dự án con",
        domain="[('du_an_cha_id', '!=', False)]",
    )
    noi_dung_cv = fields.Text("Nội dung công việc", required=True)
    so_ngay_ht = fields.Float("Số ngày hoàn thành", required=True)
    ngay_bat_dau = fields.Date("Ngày bắt đầu", required=True)
    ngay_ket_thuc = fields.Date("Ngày kết thúc", compute="get_ngay_ket_thuc")
    ngay_hoan_thanh = fields.Date("Ngày hoàn thành")
    ns_lam = fields.Many2one('res.users', string="NS làm", required=True)
    chu_so_huu = fields.Many2one('res.users', string="Chủ sở hữu", required=True)
    so_ngay_pending = fields.Float("Số ngày Pending")

    @api.onchange('cap')
    def _onchange_cap(self):
        if self.cap:
            self.project_id = self.cap

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('cap'):
                vals['project_id'] = vals['cap']
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('cap'):
            vals = dict(vals, project_id=vals['cap'])
        return super().write(vals)

    @api.depends('so_ngay_ht', 'ngay_bat_dau', 'so_ngay_pending')
    def get_ngay_ket_thuc(self):
        for r in self:
            if r.so_ngay_pending > 0 and r.so_ngay_ht and r.ngay_bat_dau:
                r.ngay_ket_thuc = r.ngay_bat_dau + timedelta(days=(r.so_ngay_ht + r.so_ngay_pending))
            elif r.so_ngay_pending <= 0 and r.so_ngay_ht and r.ngay_bat_dau:
                r.ngay_ket_thuc = r.ngay_bat_dau + timedelta(days=r.so_ngay_ht)
            else:
                r.ngay_ket_thuc = False

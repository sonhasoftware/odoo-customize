from odoo import api, Command, fields, models, _, _lt


class Project(models.Model):
    _inherit = 'project.project'

    so_du_an = fields.Char("Số dự án")
    group_du_an = fields.Char("Group dự án")
    noi_dung = fields.Text("Nội dung")
    nguoi_qlda = fields.Many2one('res.users', string="Người QLDA")
    ngay_kt_da = fields.Date("Ngày kết thúc DA")
    ngay_kt_chinh_sua = fields.Date("Ngày kết thúc chỉnh sửa")


    def action_luu_tam(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã lưu tạm'),
                'message': _('Dữ liệu dự án đã được lưu tạm, bạn có thể chọn ở trường Cấp.'),
                'type': 'success',
                'sticky': False,
            }
        }

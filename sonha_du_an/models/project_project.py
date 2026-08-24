from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Project(models.Model):
    _inherit = 'project.project'

    so_du_an = fields.Char("Số dự án")
    group_du_an = fields.Char("Group dự án")
    noi_dung = fields.Text("Nội dung")
    nguoi_qlda = fields.Many2one('res.users', string="Người QLDA")
    ngay_kt_da = fields.Date("Ngày kết thúc DA")
    ngay_kt_chinh_sua = fields.Date("Ngày kết thúc chỉnh sửa")
    du_an_cha_id = fields.Many2one(
        'project.project',
        string="Dự án cha",
        index=True,
        ondelete='restrict',
    )
    du_an_con_ids = fields.One2many(
        'project.project',
        'du_an_cha_id',
        string="Dự án con",
    )

    @api.onchange('du_an_cha_id')
    def _onchange_du_an_cha_id(self):
        if self.du_an_cha_id and self.du_an_cha_id == self:
            self.du_an_cha_id = False
            return {
                'warning': {
                    'title': _("Dữ liệu không hợp lệ"),
                    'message': _("Dự án cha không được trùng với chính dự án hiện tại."),
                }
            }
        return {}

    @api.constrains('du_an_cha_id')
    def _check_du_an_cha_id(self):
        for project in self:
            parent = project.du_an_cha_id
            while parent:
                if parent == project:
                    raise ValidationError(
                        _("Dự án cha không được tạo thành vòng lặp với dự án con.")
                    )
                parent = parent.du_an_cha_id

    def action_luu_tam(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã lưu tạm'),
                'message': _('Dữ liệu dự án đã được lưu tạm, bạn có thể chọn ở trường Dự án con.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_tasks(self):
        action = super().action_view_tasks()
        if len(self) == 1:
            action['domain'] = [('project_id', '=', self.id)]
            context = dict(action.get('context') or {})
            context.update({
                'default_project_id': self.id,
                'default_cap': self.id,
            })
            action['context'] = context
        return action

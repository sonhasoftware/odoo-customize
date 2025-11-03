from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class YardBall(models.Model):
    _name = 'yard.ball'

    area = fields.Many2one('sonha.area', string="Khu vực")
    yard = fields.Many2one('sonha.yard', string="Sân")
    date_active = fields.Date("Ngày hoạt động")
    start_active = fields.Float("Thời gian hoạt động từ")
    end_active = fields.Float("Thời gian hoạt động đến")
    pick_up = fields.Boolean("Nhặt bóng")
    start_ball = fields.Float("Từ")
    end_ball = fields.Float("Đến")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    status = fields.Selection([
        ('active', 'Hoạt động'),
        ('end', 'Kết thúc'),
        ('done', 'Đã duyệt'),
    ], string='Trạng thái', default='active')

    status_order = fields.Integer(compute="_compute_status_order")

    @api.depends('status')
    def _compute_status_order(self):
        for rec in self:
            if rec.status == "active":
                rec.status_order = 1
            elif rec.status == "end":
                rec.status_order = 2
            elif rec.status == "done":
                rec.status_order = 3

    def action_end(self):
        for r in self:
            if r.employee_id.user_id.id == self.env.user.id or r.employee_id.parent_id.user_id.id == self.env.user.id:
                r.status = 'end'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_done(self):
        for r in self:
            if r.employee_id.parent_id.user_id.id == self.env.user.id:
                r.status = 'done'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    @api.constrains('start_ball', 'end_ball', 'start_active', 'end_active')
    def check_validate_leave(self):
        for r in self:
            if r.end_ball and r.start_ball and r.end_ball <= r.start_ball:
                raise ValidationError("Thời gian kết thúc nhặt bóng không được bé hơn thời gian bắt đầu!")
            if r.end_active <= r.start_active:
                raise ValidationError("Thời gian kết thúc hoạt động không được bé hơn thời gian bắt đầu!")

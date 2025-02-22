from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class WordSlip(models.Model):
    _name = 'word.slip'

    from_date = fields.Date("Từ ngày")
    to_date = fields.Date("Đến ngày")

    start_time = fields.Selection([
        ('first_half', 'Nửa ca đầu'),
        ('second_half', 'Nửa ca sau'),
    ], string='Ca bắt đầu')

    end_time = fields.Selection([
        ('first_half', 'Nửa ca đầu'),
        ('second_half', 'Nửa ca sau'),
    ], string='Ca kết thúc')

    time_to = fields.Float("Thời gian bắt đầu")
    time_from = fields.Float("Thời gian kết thúc")

    word_slip = fields.Many2one('form.word.slip')
    employee_id = fields.Many2one('hr.employee', compute="get_employee_slip")
    type = fields.Many2one('config.word.slip', related='word_slip.type')
    duration = fields.Float("Ngày", compute="get_duration")
    reason = fields.Text(string="Lý do")

    @api.constrains("from_date", "to_date", 'word_slip')
    def check_employee_days_limit(self):
        for r in self:
            if r.from_date and r.to_date and r.from_date.month != r.to_date.month:
                raise ValidationError("Dữ liệu từ ngày đến ngày phải trong cùng 1 tháng")
            start_date = r.from_date.replace(day=1)
            end_date = start_date + relativedelta(days=-1, months=1)
            if r.word_slip.regis_type == 'one':
                limit_day = self.env['config.leave'].sudo().search([('employee_ids', 'in', r.word_slip.employee_id.id)])
                if limit_day:
                    requests = self.env["word.slip"].search([
                        ("word_slip.employee_id", "=", r.word_slip.employee_id.id),
                        ("from_date", ">=", start_date),
                        ("to_date", "<=", end_date),
                        ("word_slip.type", "=", limit_day.word_slip.id),
                        ("id", "!=", r.id)
                    ])
                    total_days = sum((r.to_date - r.from_date).days + 1 for r in requests)
                    current_days = (r.to_date - r.from_date).days + 1
                    if total_days + current_days > limit_day.date:
                        raise ValidationError(f"Bạn đã đăng ký quá số lượng loại đơn này trong 1 tháng!")
            elif r.word_slip.regis_type == 'many':
                for emp in r.word_slip.employee_ids:
                    limit_day = self.env["config.leave"].sudo().search([
                        ("employee_ids", "in", emp.id)
                    ], limit=1)

                    if limit_day:

                        # Lọc tất cả đơn của nhân viên này trong tháng
                        requests = self.env["word.slip"].search([
                            ("word_slip.employee_ids", "in", emp.id),  # Nhân viên trong đơn
                            ("from_date", ">=", start_date),
                            ("to_date", "<=", end_date),
                            ("word_slip.type", "=", limit_day.word_slip.id),
                            ("id", "!=", r.id)  # Loại trừ đơn hiện tại nếu đang sửa
                        ])

                        # Tính tổng số ngày đã đăng ký
                        total_days = sum((req.to_date - req.from_date).days + 1 for req in requests)
                        current_days = (r.to_date - r.from_date).days + 1

                        if total_days + current_days > limit_day.date:
                            raise ValidationError(f"Nhân viên {emp.name} đã đăng ký quá số ngày cho phép trong tháng!")

    @api.depends('word_slip')
    def get_employee_slip(self):
        for r in self:
            if r.word_slip:
                if r.word_slip.employee_id:
                    r.employee_id = r.word_slip.employee_id.id
                elif r.word_slip.employee_ids:
                    r.employee_id = r.word_slip.employee_ids[:1].id
                else:
                    r.employee_id = None


    #Lấy thông tin số ngày công mà nhân viên nghỉ
    @api.depends('start_time', 'end_time', 'from_date', 'to_date')
    def get_duration(self):
        for r in self:
            r.duration = 0
            if r.from_date == r.to_date:
                if r.type.date_and_time == 'date':
                    if r.start_time and r.end_time:
                        if r.start_time == r.end_time:
                            r.duration = 0.5
                        elif r.start_time == 'first_half' and r.end_time == 'second_half':
                            r.duration = 1
            else:
                start_date = fields.Date.from_string(r.from_date)
                end_date = fields.Date.from_string(r.to_date)
                day_duration = (end_date - start_date).days + 1 if start_date and end_date else 0
                if r.type.date_and_time == 'date':
                    if r.start_time and r.end_time:
                        if r.start_time == r.end_time:
                            r.duration = 0.5 * day_duration
                        elif r.start_time == 'first_half' and r.end_time == 'second_half':
                            r.duration = 1 * day_duration
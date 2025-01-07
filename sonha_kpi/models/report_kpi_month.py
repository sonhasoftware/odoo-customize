from odoo import api, fields, models, _
from datetime import datetime, timedelta


class ReportKpiMonth(models.Model):
    _name = 'report.kpi.month'

    department_id = fields.Many2one('hr.department', string="Phòng ban")
    year = fields.Integer('Năm')
    small_items_each_month = fields.Many2one('sonha.kpi.month', string="Nội dung CV KPI của tháng")
    kpi_year_id = fields.Many2one('sonha.kpi.year', string="Hạng mục lớn",
                                  domain="[('sonha_kpi', '=', sonha_kpi)]")
    start_date = fields.Date('Ngày bắt đầu')
    end_date = fields.Date("Ngày hoàn thành")

    dv_amount_work = fields.Float("khối lượng CVTH", default=0)
    dv_matter_work = fields.Float("Chất lượng CVTH", default=0)
    dv_comply_regulations = fields.Float("Chấp hành nội quy, quy chế", default=0)
    dv_initiative = fields.Float("Cải tiến, đề xuất, sáng kiến", default=0)
    dv_description = fields.Text("Mô tả chi tiết công việc")

    tq_amount_work = fields.Float("khối lượng CVTH", default=0)
    tq_matter_work = fields.Float("Chất lượng CVTH", default=0)
    tq_comply_regulations = fields.Float("Chấp hành nội quy, quy chế", default=0)
    tq_initiative = fields.Float("Cải tiến, đề xuất, sáng kiến", default=0)
    tq_description = fields.Text("Nhận xét chung của cấp có thẩm quyền")
    sonha_kpi = fields.Many2one('company.sonha.kpi')
    status = fields.Selection([('draft', 'Nháp'),
                               ('waiting', 'Chờ duyệt'),
                               ('approved', 'Đã duyệt')], string="Trạng thái", default='draft')

    mail_turn = fields.Integer(string="số lần gửi mail", default="0")
    url_data_mail = fields.Char(string="url kpi form")
    first_mail_date = fields.Date(string="Ngày gửi mail lần 1")

    def resend_kpi_report_mail(self):
        now = datetime.now().date()
        list_resend_mail = self.env['report.kpi.month'].sudo().search([('status', '=', 'waiting')])
        duplicate_department = set()
        for rc in list_resend_mail:
            if (rc.mail_turn == 1 and now == (rc.first_mail_date + timedelta(days=2))) or (rc.mail_turn == 2 and now == (rc.first_mail_date + timedelta(days=4))):
                if rc.department_id.id not in duplicate_department:
                    mail_to = self.env['report.mail.to'].sudo().search([('department_id.id', '=', rc.department_id.id)]).receive_emp.work_email
                    if mail_to:
                        template = self.env.ref('sonha_kpi.report_kpi_mail_template').sudo()
                        template.email_to = mail_to
                        template.sudo().send_mail(rc.id, force_send=True)
                        rc.mail_turn = rc.mail_turn + 1
                        duplicate_department.add(rc.department_id.id)

    def get_status_label(self):
        return dict(self._fields['status'].selection).get(self.status)

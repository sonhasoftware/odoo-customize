from odoo import api, fields, models, _
import pandas as pd
from odoo.exceptions import UserError, ValidationError


class SonHaKPIMonth(models.Model):
    _name = 'sonha.kpi.month'
    _rec_name = 'small_items_each_month'

    department_id = fields.Many2one('hr.department')
    year = fields.Integer('Năm')
    small_items_each_month = fields.Text("Nội dung CV KPI của tháng")
    kpi_year_id = fields.Many2one('sonha.kpi.year', string="Hạng mục lớn",
                                  domain="[('sonha_kpi', '=', sonha_kpi)]")
    employee_id = fields.Many2many('hr.employee', string="NS thực hiện", readonly=False)
    start_date = fields.Date('Ngày bắt đầu', required=True)
    end_date = fields.Date("Ngày hoàn thành", required=True)

    dv_amount_work = fields.Float("khối lượng CVTH", default=0)
    dv_matter_work = fields.Float("Chất lượng CVTH", default=0)
    dv_comply_regulations = fields.Float("Chấp hành nội quy, quy chế", default=0)
    dv_initiative = fields.Float("Cải tiến, đề xuất, sáng kiến", default=0)
    dv_description = fields.Text("Mô tả chi tiết công việc")

    tq_amount_work = fields.Float("khối lượng CVTH", default=0)
    tq_matter_work = fields.Float("Chất lượng CVTH", default=0)
    tq_comply_regulations = fields.Float("Chấp hành nội quy, quy chế", default=0)
    tq_initiative = fields.Float("Cải tiến, đề xuất, sáng kiến", default=0)
    status_tq = fields.Selection([('draft', 'Chưa đánh giá'),
                                  ('done', 'Đã đánh giá')], default='draft', compute="get_status_appraisal")
    tq_description = fields.Text("Nhận xét chung của cấp có thẩm quyền")
    sonha_kpi = fields.Many2one('company.sonha.kpi')

    @api.constrains('start_date', 'end_date')
    def validate_start_end_date(self):
        for r in self:
            if r.kpi_year_id.start_date <= r.start_date <= r.kpi_year_id.end_date and r.kpi_year_id.start_date <= r.end_date <= r.kpi_year_id.end_date:
                pass
            else:
                raise ValidationError("Dữ liệu tháng phải thuộc trong khoảng dữ liệu của năm")

    @api.depends('tq_amount_work', 'tq_matter_work', 'tq_comply_regulations', 'status_tq')
    def get_status_appraisal(self):
        for r in self:
            if r.tq_amount_work or r.tq_matter_work or r.tq_comply_regulations or r.status_tq:
                r.status_tq = 'done'
            else:
                r.status_tq = 'draft'

    @api.model
    def default_get(self, fields_list):
        res = super(SonHaKPIMonth, self).default_get(fields_list)
        sonha_kpi_id = self._context.get('default_sonha_kpi')
        if sonha_kpi_id:
            res['sonha_kpi'] = sonha_kpi_id
        return res

    def write(self, vals):
        res = super(SonHaKPIMonth, self).write(vals)
        for r in self:
            self.write_result_month(r)
        return res

    def create(self, vals):
        list_record = super(SonHaKPIMonth, self).create(vals)
        for record in list_record:
            record.department_id = record.kpi_year_id.department_id.id
            record.year = record.kpi_year_id.year
            record.kpi_year_id.dvdg_kpi = round(record.kpi_year_id.kpi_year * (
                        record.dv_amount_work * 50 + record.dv_matter_work * 30 + record.dv_comply_regulations * 10 + record.dv_initiative * 10) / 100, 3)
            record.kpi_year_id.total_percentage_month = record.kpi_year_id.dvdg_kpi / record.kpi_year_id.kpi_year if record.kpi_year_id.kpi_year else 0
            record.kpi_year_id.ctqdg_kpi = round(record.kpi_year_id.kpi_year * (
                        record.tq_amount_work * 50 + record.tq_matter_work * 30 + record.tq_comply_regulations * 10 + record.tq_initiative * 10) / 100, 3)
            self.create_result_month(record)
            self.create_report_month(record)
        return list_record

    def write_result_month(self, record):
        kpi_month_result = self.env['sonha.kpi.result.month'].sudo().search([('kpi_month', '=', record.id)])
        number_density = self.calculating_density(record)
        vals = {
            'department_id': record.department_id.id or '',
            'year': record.year or '',
            'name': record.kpi_year_id.id or '',
            'content_detail': record.small_items_each_month or '',
            'start_date': str(record.start_date) or '',
            'end_date': str(record.end_date) or '',
            'ti_trong': number_density / 100 or '',
            'sonha_kpi': record.sonha_kpi.id or '',
            'kq_hoan_thanh_amount_work': record.dv_amount_work or '',
            'kq_hoan_thanh_matter_work': record.dv_matter_work or '',
            'kq_hoan_thanh_comply_regulations': record.dv_comply_regulations or '',
            'kq_hoan_thanh_initiative': record.dv_initiative or '',
            'kq_hoan_thanh_tq_amount_work': record.tq_amount_work or '',
            'kq_hoan_thanh_tq_matter_work': record.tq_matter_work or '',
            'kq_hoan_thanh_tq_comply_regulations': record.tq_comply_regulations or '',
            'kq_hoan_thanh_tq_initiative': record.tq_initiative or '',
        }
        kpi_month_result.write(vals)
        kpi_month_result.filter_data_dvdg(kpi_month_result)
        kpi_month_result.filter_data_dvtq(kpi_month_result)
        kpi_month_result.kpi_month.kpi_year_id.dvdg_kpi = round(kpi_month_result.kpi_month.kpi_year_id.kpi_year * (
                    kpi_month_result.kpi_month.dv_amount_work * 50 + kpi_month_result.kpi_month.dv_matter_work * 30 + kpi_month_result.kpi_month.dv_comply_regulations * 10 + kpi_month_result.kpi_month.dv_initiative * 10) / 100, 3)
        kpi_month_result.kpi_month.kpi_year_id.total_percentage_month = kpi_month_result.kpi_month.kpi_year_id.dvdg_kpi / kpi_month_result.kpi_month.kpi_year_id.kpi_year if kpi_month_result.kpi_month.kpi_year_id.kpi_year else 0
        kpi_month_result.kpi_month.kpi_year_id.ctqdg_kpi = round(kpi_month_result.kpi_month.kpi_year_id.kpi_year * (
                    kpi_month_result.kpi_month.tq_amount_work * 50 + kpi_month_result.kpi_month.tq_matter_work * 30 + kpi_month_result.kpi_month.tq_comply_regulations * 10 + kpi_month_result.kpi_month.tq_initiative * 10) / 100, 3)


    def create_result_month(self, record):
        number_density = self.calculating_density(record)
        vals = {
            'department_id': record.department_id.id or '',
            'year': record.year or '',
            'name': record.kpi_year_id.id or '',
            'content_detail': record.small_items_each_month or '',
            'start_date': str(record.start_date) or '',
            'end_date': str(record.end_date) or '',
            'ti_trong': number_density / 100 or '',
            'sonha_kpi': record.sonha_kpi.id or '',
            'kq_hoan_thanh_amount_work': record.dv_amount_work or '',
            'kq_hoan_thanh_matter_work': record.dv_matter_work or '',
            'kq_hoan_thanh_comply_regulations': record.dv_comply_regulations or '',
            'kq_hoan_thanh_initiative': record.dv_initiative or '',
            'kq_hoan_thanh_tq_amount_work': record.tq_amount_work or '',
            'kq_hoan_thanh_tq_matter_work': record.tq_matter_work or '',
            'kq_hoan_thanh_tq_comply_regulations': record.tq_comply_regulations or '',
            'kq_hoan_thanh_tq_initiative': record.tq_initiative or '',
            'kpi_month': record.id
        }
        record = self.env['sonha.kpi.result.month'].create(vals)
        record.filter_data_dvdg(record)
        record.filter_data_dvtq(record)

    def calculating_density(self, r):
        number = 0
        key = self.env['sonha.kpi.year'].search([('year', '=', r.year), ('sonha_kpi', '=', r.sonha_kpi.id)])
        if r.start_date.month == 1:
            total = sum(key.mapped('ti_le_monh_one'))
            number = (r.kpi_year_id.ti_le_monh_one * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 2:
            total = sum(key.mapped('ti_le_monh_two'))
            number = (r.kpi_year_id.ti_le_monh_two * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 3:
            total = sum(key.mapped('ti_le_monh_three'))
            number = (r.kpi_year_id.ti_le_monh_three * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 4:
            total = sum(key.mapped('ti_le_monh_four'))
            number = (r.kpi_year_id.ti_le_monh_four * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 5:
            total = sum(key.mapped('ti_le_monh_five'))
            number = (r.kpi_year_id.ti_le_monh_five * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 6:
            total = sum(key.mapped('ti_le_monh_six'))
            number = (r.kpi_year_id.ti_le_monh_six * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 7:
            total = sum(key.mapped('ti_le_monh_seven'))
            number = (r.kpi_year_id.ti_le_monh_seven * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 8:
            total = sum(key.mapped('ti_le_monh_eight'))
            number = (r.kpi_year_id.ti_le_monh_eight * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 9:
            total = sum(key.mapped('ti_le_monh_nigh'))
            number = (r.kpi_year_id.ti_le_monh_nigh * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 10:
            total = sum(key.mapped('ti_le_monh_ten'))
            number = (r.kpi_year_id.ti_le_monh_ten * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 11:
            total = sum(key.mapped('ti_le_monh_eleven'))
            number = (r.kpi_year_id.ti_le_monh_eleven * 100) * 100 / (total * 100) if total != 0 else 0
        elif r.start_date.month == 12:
            total = sum(key.mapped('ti_le_monh_twenty'))
            number = (r.kpi_year_id.ti_le_monh_twenty * 100) * 100 / (total * 100) if total != 0 else 0
        return number

    def unlink(self):
        for r in self:
            self.env['sonha.kpi.result.month'].search([('kpi_month', '=', r.id)]).unlink()
        return super(SonHaKPIMonth, self).unlink()

    def create_report_month(self, record):
        vals = {
            'department_id': record.department_id.id or '',
            'year': record.year or '',
            'small_items_each_month': record.id or '',
            'kpi_year_id': record.kpi_year_id.id or '',
            'start_date': str(record.start_date) or '',
            'end_date': str(record.end_date) or '',
            'sonha_kpi': record.sonha_kpi.id or '',
            'dv_amount_work': record.dv_amount_work or '',
            'dv_matter_work': record.dv_matter_work or '',
            'dv_comply_regulations': record.dv_comply_regulations or '',
            'dv_initiative': record.dv_initiative or '',
            'dv_description': record.dv_description or ''
        }
        self.env['report.kpi.month'].sudo().create(vals)

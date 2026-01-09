from odoo import api, fields, models, _
import pandas as pd
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class SonHaKPIMonth(models.Model):
    _name = 'sonha.kpi.month'
    _rec_name = 'small_items_each_month'

    state = fields.Selection([('cancel', "Hủy"),
                              ('waiting', "Chưa hoàn thành"),
                              ('done', "Hoàn thành")
                              ], string="Trạng thái")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    year = fields.Integer('Năm')
    small_items_each_month = fields.Text("Nội dung CV KPI của tháng")
    kpi_year_id = fields.Many2one('sonha.kpi.year', string="Hạng mục lớn",
                                  domain="[('sonha_kpi', '=', sonha_kpi)]")
    employee_id = fields.Many2many('hr.employee', string="NS thực hiện", readonly=False,
                                   default=lambda self: self._get_current_user())
    month = fields.Selection([('one', 1),
                              ('two', 2),
                              ('three', 3),
                              ('four', 4),
                              ('five', 5),
                              ('six', 6),
                              ('seven', 7),
                              ('eight', 8),
                              ('nine', 9),
                              ('ten', 10),
                              ('eleven', 11),
                              ('twelve', 12), ], string="Tháng")
    start_date = fields.Date('Ngày bắt đầu', require=True)
    end_date = fields.Date("Ngày hoàn thành", require=True)

    dv_amount_work = fields.Float("khối lượng CVTH", default=0)
    dv_matter_work = fields.Float("Chất lượng CVTH", default=0)
    dv_comply_regulations = fields.Float("Chấp hành nội quy, quy chế", default=0)
    dv_initiative = fields.Float("Cải tiến, đề xuất, sáng kiến", default=0)
    dv_description = fields.Text("Mô tả chi tiết công việc")

    tq_amount_work = fields.Float("Khối lượng CVTH", default=0)
    tq_matter_work = fields.Float("Chất lượng CVTH", default=0)
    tq_comply_regulations = fields.Float("Chấp hành nội quy, quy chế", default=0)
    tq_initiative = fields.Float("Cải tiến, đề xuất, sáng kiến", default=0)
    status_tq = fields.Selection([('draft', 'Chưa đánh giá'),
                                  ('done', 'Đã đánh giá')], default='draft', compute="get_status_appraisal")
    tq_description = fields.Text("Nhận xét chung của cấp có thẩm quyền")
    sonha_kpi = fields.Many2one('company.sonha.kpi')
    parent_kpi_month = fields.Many2one('parent.kpi.month')
    upload_file = fields.Binary(string="File")
    upload_file_name = fields.Char(string="Tên File")
    upload_files = fields.Many2many('ir.attachment', string="Files")
    month_filter = fields.Integer("Tháng", compute="_get_month_filter")
    is_sent = fields.Boolean('is_sent')

    @api.onchange('sonha_kpi')
    def _onchange_kpi_id(self):
        # Lấy giá trị 'month_from_parent' từ context
        month = self.env.context.get('month_from_parent', 0)
        if month and month > 0:
            # Lọc những bản ghi có month_filter == month
            domain = [('month_filter', '=', month)]
        else:
            # Nếu không truyền month (hoặc month = 0), không lọc gì cả
            domain = []
        return {'domain': {'month_filter': domain}}

    @api.depends('start_date')
    def _get_month_filter(self):
        for r in self:
            if r.start_date:
                r.month_filter = r.start_date.month
            else:
                r.month_filter = 0

    @api.onchange('state')
    def get_value_data(self):
        for r in self:
            if r.state == 'done':
                r.dv_amount_work = 1
                r.dv_matter_work = 1
                r.dv_comply_regulations = 1
            else:
                r.dv_amount_work = r.dv_amount_work
                r.dv_matter_work = r.dv_matter_work
                r.dv_comply_regulations = r.dv_comply_regulations

    @api.constrains('start_date', 'end_date')
    def validate_start_end_date(self):
        for r in self:
            if r.start_date and r.end_date and r.kpi_year_id.start_date <= r.start_date <= r.kpi_year_id.end_date and r.kpi_year_id.start_date <= r.end_date <= r.kpi_year_id.end_date:
                pass
            else:
                self.env['bus.bus']._sendone(
                    (self._cr.dbname, 'res.partner', self.env.user.partner_id.id),
                    'simple_notification',
                    {
                        'title': "Cảnh báo!",
                        'message': f"Dữ liệu tháng của hạng mục nhỏ {r.small_items_each_month} nằm ngoài khoảng dữ liệu của năm!",
                        'sticky': False,
                    }
                )

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
            if r.state == 'cancel':
                self.delete_record_result(r)
            else:
                self.write_result_month(r)
                self.write_report_month(r)
        self.re_calculating_density_all(self[0])
        self.calculating_dvdgkpi_tqdgkpi(self[0])
        return res

    def create(self, vals):
        list_record = super(SonHaKPIMonth, self).create(vals)
        for record in list_record:
            record.department_id = record.kpi_year_id.department_id.id
            record.year = record.kpi_year_id.year
            self.create_result_month(record)
            self.create_report_month(record)
            self.re_calculating_density(record)
        self.calculating_dvdgkpi_tqdgkpi(list_record[0])
        return list_record

    def delete_record_result(self, record):
        kpi_month_result = self.env['sonha.kpi.result.month'].sudo().search([('kpi_month', '=', record.id)])
        kpi_month_result.sudo().unlink()

    def write_result_month(self, record):
        kpi_month_result = self.env['sonha.kpi.result.month'].sudo().search([('kpi_month', '=', record.id)])
        number_density = round(self.calculating_density(record), 2)
        vals = {
            'department_id': record.sonha_kpi.department_id.id or '',
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
        kpi_month_result.sudo().write(vals)
        kpi_month_result.filter_data_dvdg(kpi_month_result)
        kpi_month_result.filter_data_dvtq(kpi_month_result)

    def create_result_month(self, record):
        number_density = round(self.calculating_density(record), 2)
        vals = {
            'department_id': record.sonha_kpi.department_id.id or '',
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
        record = self.env['sonha.kpi.result.month'].sudo().create(vals)
        record.filter_data_dvdg(record)
        record.filter_data_dvtq(record)

    # Sửa để chỉ những kpi năm nào đã có bản ghi công việc nhỏ mới ảnh hưởng đến tỉ trọng
    def calculating_density(self, r):
        number = 0
        month_record = self.env['sonha.kpi.month'].sudo().search([('sonha_kpi', '=', r.sonha_kpi.id),
                                                                  ('state', '!=', 'cancel')])
        if month_record:
            exist_month = month_record.filtered(lambda x: x.start_date.month == r.start_date.month)
            if exist_month:
                exist_year = exist_month.mapped('kpi_year_id.id')
                key = self.env['sonha.kpi.year'].search([('year', '=', r.year),
                                                         ('sonha_kpi', '=', r.sonha_kpi.id),
                                                         ('id', 'in', exist_year)])
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
            self.env['report.kpi.month'].search([('small_items_each_month', '=', r.id)]).sudo().unlink()
        return super(SonHaKPIMonth, self).unlink()

    def create_report_month(self, record):
        vals = {
            'department_id': record.sonha_kpi.department_id.id or '',
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
            'dv_description': record.dv_description or '',
            'status': 'draft'
        }
        self.env['report.kpi.month'].sudo().create(vals)

    def write_report_month(self, record):
        kpi_month_report = self.env['report.kpi.month'].sudo().search([('small_items_each_month', '=', record.id)])
        vals = {
            'department_id': record.sonha_kpi.department_id.id or '',
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
        kpi_month_report.sudo().write(vals)

    def _get_current_user(self):
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        if employee:
            return [employee.id]
        return []

    # Tính lại tỉ trọng khi thêm
    def re_calculating_density(self, record):
        exist_month = self.env['sonha.kpi.month'].sudo().search([('sonha_kpi', '=', record.sonha_kpi.id),
                                                                 ('state', '!=', 'cancel')])
        if exist_month:
            records = exist_month.filtered(lambda x: x.start_date.month == record.start_date.month)
            if records:
                for r in records:
                    desnsity = round(r.calculating_density(r), 2) / 100
                    kpi_year_records = records.filtered(lambda x: x.kpi_year_id.id == r.kpi_year_id.id)
                    if kpi_year_records:
                        kpi_year_count = len(kpi_year_records)
                        month_record = self.env['sonha.kpi.result.month'].sudo().search([('kpi_month', '=', r.id)])
                        desnsity = desnsity / kpi_year_count
                        month_record.sudo().write({'ti_trong': desnsity})
                        # month_record.filter_data_dvdg(month_record)
                        # month_record.filter_data_dvtq(month_record)

    # Tính lại tỉ trọng khi sửa, vì sửa thời gian kpi tháng sang tháng khác cần tính lại tỉ trọng tháng cũ nên em cho tính lại tất cả
    def re_calculating_density_all(self, record):
        exist_month = self.env['sonha.kpi.month'].sudo().search([('sonha_kpi', '=', record.sonha_kpi.id)])
        for month in exist_month:
            self.re_calculating_density(month)

    # Tính đơn vị, thẩm quyền đánh giá kpi đến hiện tại
    def calculating_dvdgkpi_tqdgkpi(self, record):
        kpi_years = self.env['sonha.kpi.year'].sudo().search([('sonha_kpi', '=', record.sonha_kpi.id)])
        for kpi_year in kpi_years:
            dvdg_kpi = 0
            ctqdg_kpi = 0
            duplicate_month = set()
            kpi_months = self.env['sonha.kpi.month'].sudo().search([('kpi_year_id', '=', kpi_year.id)])
            if kpi_months:
                for kpi_month in kpi_months:
                    if kpi_month.start_date.month not in duplicate_month:
                        work_month = kpi_months.filtered(lambda x: x.start_date.month == kpi_month.start_date.month)
                        if work_month:
                            dv_amount_work = sum(work_month.mapped('dv_amount_work')) / len(work_month.mapped('dv_amount_work'))
                            tq_amount_work = sum(work_month.mapped('tq_amount_work')) / len(work_month.mapped('dv_amount_work'))
                            if kpi_month.start_date.month == 1:
                                total_work_month = kpi_year.ti_le_monh_one * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_one * tq_amount_work
                            elif kpi_month.start_date.month == 2:
                                total_work_month = kpi_year.ti_le_monh_two * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_two * tq_amount_work
                            elif kpi_month.start_date.month == 3:
                                total_work_month = kpi_year.ti_le_monh_three * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_three * tq_amount_work
                            elif kpi_month.start_date.month == 4:
                                total_work_month = kpi_year.ti_le_monh_four * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_four * tq_amount_work
                            elif kpi_month.start_date.month == 5:
                                total_work_month = kpi_year.ti_le_monh_five * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_five * tq_amount_work
                            elif kpi_month.start_date.month == 6:
                                total_work_month = kpi_year.ti_le_monh_six * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_six * tq_amount_work
                            elif kpi_month.start_date.month == 7:
                                total_work_month = kpi_year.ti_le_monh_seven * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_seven * tq_amount_work
                            elif kpi_month.start_date.month == 8:
                                total_work_month = kpi_year.ti_le_monh_eight * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_eight * tq_amount_work
                            elif kpi_month.start_date.month == 9:
                                total_work_month = kpi_year.ti_le_monh_nigh * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_nigh * tq_amount_work
                            elif kpi_month.start_date.month == 10:
                                total_work_month = kpi_year.ti_le_monh_ten * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_ten * tq_amount_work
                            elif kpi_month.start_date.month == 11:
                                total_work_month = kpi_year.ti_le_monh_eleven * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_eleven * tq_amount_work
                            elif kpi_month.start_date.month == 12:
                                total_work_month = kpi_year.ti_le_monh_twenty * dv_amount_work
                                total_tq_work_month = kpi_year.ti_le_monh_twenty * tq_amount_work
                            total_work_month = round(total_work_month * 100, 1) / 100
                            total_tq_work_month = round(total_tq_work_month * 100, 1) / 100
                            dvdg_kpi = dvdg_kpi + total_work_month
                            ctqdg_kpi = ctqdg_kpi + total_tq_work_month
                            duplicate_month.add(kpi_month.start_date.month)
            kpi_year.sudo().write({'dvdg_kpi': dvdg_kpi,
                                   'ctqdg_kpi': ctqdg_kpi})

    # @api.depends('month')
    # def get_month(self):
    #     for r in self:
    #         if r.month == 'one':
    #             r.start_date = f'{r.sonha_kpi.year}-1-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'two':
    #             r.start_date = f'{r.sonha_kpi.year}-2-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'three':
    #             r.start_date = f'{r.sonha_kpi.year}-3-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'four':
    #             r.start_date = f'{r.sonha_kpi.year}-4-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'five':
    #             r.start_date = f'{r.sonha_kpi.year}-5-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'six':
    #             r.start_date = f'{r.sonha_kpi.year}-6-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'seven':
    #             r.start_date = f'{r.sonha_kpi.year}-7-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'eight':
    #             r.start_date = f'{r.sonha_kpi.year}-8-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'nine':
    #             r.start_date = f'{r.sonha_kpi.year}-9-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'ten':
    #             r.start_date = f'{r.sonha_kpi.year}-10-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'eleven':
    #             r.start_date = f'{r.sonha_kpi.year}-11-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         elif r.month == 'twelve':
    #             r.start_date = f'{r.sonha_kpi.year}-12-1'
    #             r.end_date = r.start_date + relativedelta(months=1, days=-1)
    #         else:
    #             r.start_date = ''
    #             r.end_date = ''





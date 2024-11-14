from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SonHaKPIYear(models.Model):
    _name = 'sonha.kpi.year'

    department_id = fields.Many2one('hr.department')
    year = fields.Integer('Năm')
    name = fields.Char("Hạng mục lớn")
    start_date = fields.Date('Bắt đầu')
    end_date = fields.Date("Hoàn thành")
    kpi_year = fields.Float("KPI KH cả năm")
    dvdg_kpi = fields.Float("Đơn vị ĐG kpi đến hiện tại", readonly=True)
    dvdg_status = fields.Selection([('draft', "Chưa thực hiện"),
                                    ('in_progres', "Đang thực hiện"),
                                    ('done', "Hoàn thành")],
                                   string="Trạng thái ĐV đánh giá",
                                   compute="compute_filter_status", store=True, readonly=True)
    ctqdg_kpi = fields.Float("Cấp thẩm quyền ĐG KPI đến hiện tại", readonly=True)
    ctqdg_status = fields.Selection([('draft', "Chưa thực hiện"),
                                    ('in_progres', "Đang thực hiện"),
                                    ('done', "Hoàn thành")],
                                    string="Trạng thái cấp thẩm quyền ĐG",
                                    compute="compute_filter_status_authorization", store=True, readonly=True)

    ti_le_monh_one = fields.Float("Tháng 1")
    ti_le_monh_two = fields.Float("Tháng 2")
    ti_le_monh_three = fields.Float("Tháng 3")
    ti_le_monh_four = fields.Float("Tháng 4")
    ti_le_monh_five = fields.Float("Tháng 5")
    ti_le_monh_six = fields.Float("Tháng 6")
    ti_le_monh_seven = fields.Float("Tháng 7")
    ti_le_monh_eight = fields.Float("Tháng 8")
    ti_le_monh_nigh = fields.Float("Tháng 9")
    ti_le_monh_ten = fields.Float("Tháng 10")
    ti_le_monh_eleven = fields.Float("Tháng 11")
    ti_le_monh_twenty = fields.Float("Tháng 12")

    quy_doi_monh_one = fields.Float("Tháng 1")
    quy_doi_monh_two = fields.Float("Tháng 2")
    quy_doi_monh_three = fields.Float("Tháng 3")
    quy_doi_monh_four = fields.Float("Tháng 4")
    quy_doi_monh_five = fields.Float("Tháng 5")
    quy_doi_monh_six = fields.Float("Tháng 6")
    quy_doi_monh_seven = fields.Float("Tháng 7")
    quy_doi_monh_eight = fields.Float("Tháng 8")
    quy_doi_monh_nigh = fields.Float("Tháng 9")
    quy_doi_monh_ten = fields.Float("Tháng 10")
    quy_doi_monh_eleven = fields.Float("Tháng 11")
    quy_doi_monh_twenty = fields.Float("Tháng 12")

    kl_cv_monh_one = fields.Float("Tháng 1")
    kl_cv_monh_two = fields.Float("Tháng 2")
    kl_cv_monh_three = fields.Float("Tháng 3")
    kl_cv_monh_four = fields.Float("Tháng 4")
    kl_cv_monh_five = fields.Float("Tháng 5")
    kl_cv_monh_six = fields.Float("Tháng 6")
    kl_cv_monh_seven = fields.Float("Tháng 7")
    kl_cv_monh_eight = fields.Float("Tháng 8")
    kl_cv_monh_nigh = fields.Float("Tháng 9")
    kl_cv_monh_ten = fields.Float("Tháng 10")
    kl_cv_monh_eleven = fields.Float("Tháng 11")
    kl_cv_monh_twenty = fields.Float("Tháng 12")

    th_kl_cv_monh_one = fields.Float("Tháng 1")
    th_kl_cv_monh_two = fields.Float("Tháng 2")
    th_kl_cv_monh_three = fields.Float("Tháng 3")
    th_kl_cv_monh_four = fields.Float("Tháng 4")
    th_kl_cv_monh_five = fields.Float("Tháng 5")
    th_kl_cv_monh_six = fields.Float("Tháng 6")
    th_kl_cv_monh_seven = fields.Float("Tháng 7")
    th_kl_cv_monh_eight = fields.Float("Tháng 8")
    th_kl_cv_monh_nigh = fields.Float("Tháng 9")
    th_kl_cv_monh_ten = fields.Float("Tháng 10")
    th_kl_cv_monh_eleven = fields.Float("Tháng 11")
    th_kl_cv_monh_twenty = fields.Float("Tháng 12")

    sonha_kpi = fields.Many2one('company.sonha.kpi')

    @api.constrains('ti_le_monh_one', 'ti_le_monh_two', 'ti_le_monh_three', 'ti_le_monh_four',
                    'ti_le_monh_five', 'ti_le_monh_six', 'ti_le_monh_seven', 'ti_le_monh_eight',
                    'ti_le_monh_nigh', 'ti_le_monh_ten', 'ti_le_monh_eleven', 'ti_le_monh_twenty')
    def _check_month_values(self):
        for r in self:
            sum_month = r.ti_le_monh_one + r.ti_le_monh_two + r.ti_le_monh_three + r.ti_le_monh_four + r.ti_le_monh_five + r.ti_le_monh_six + r.ti_le_monh_seven + r.ti_le_monh_eight + r.ti_le_monh_nigh + r.ti_le_monh_ten + r.ti_le_monh_eleven + r.ti_le_monh_twenty
            if sum_month > r.kpi_year or not r.kpi_year:
                raise ValidationError("Tổng % các tháng lớn hơn KPI dự kiến cả năm")
            else:
                pass
            if r.start_date and r.end_date:
                months_to_check = [r.ti_le_monh_one, r.ti_le_monh_two,
                                   r.ti_le_monh_three, r.ti_le_monh_four,
                                   r.ti_le_monh_five, r.ti_le_monh_six,
                                   r.ti_le_monh_seven, r.ti_le_monh_eight,
                                   r.ti_le_monh_nigh, r.ti_le_monh_ten,
                                   r.ti_le_monh_eleven, r.ti_le_monh_twenty]

                start_month = r.start_date.month
                end_month = r.end_date.month
                for month in range(1, 13):
                    if month < start_month or month > end_month:
                        if months_to_check[month - 1] != 0.0:
                            raise ValidationError(f"Tháng {month} nằm ngoài phạm vi ngày bắt đầu và ngày kết thúc.")
            else:
                raise ValidationError("Phải điền dữ liệu ngày bắt đầu và ngày kết thúc trước")

    @api.constrains('kpi_year')
    def validate_kpi_kh_year(self):
        for r in self:
            kh_kpi = self.env['sonha.kpi.year'].search([('year', '=', r.year),
                                                        ('sonha_kpi', '=', r.sonha_kpi.id)])
            if sum(kh_kpi.mapped('kpi_year')) > 1:
                raise ValidationError("KPI kế hoạch cả năm không được vượt quá 100%")

    @api.depends('dvdg_kpi', 'kpi_year')
    def compute_filter_status(self):
        for r in self:
            if not r.dvdg_kpi:
                r.dvdg_status = 'draft'
            elif r.dvdg_kpi < r.kpi_year:
                r.dvdg_status = 'in_progres'
            else:
                r.dvdg_status = 'done'

    @api.depends('ctqdg_kpi', 'kpi_year')
    def compute_filter_status_authorization(self):
        for r in self:
            if not r.ctqdg_kpi:
                r.ctqdg_status = 'draft'
            elif r.ctqdg_kpi < r.kpi_year:
                r.ctqdg_status = 'in_progres'
            else:
                r.ctqdg_status = 'done'

    def create(self, vals):
        record = super(SonHaKPIYear, self).create(vals)
        for r in record:
            self.filter_date_year(r)
            self.filter_conversion_data(r)
            self.validate_kpi_year(r)
        return record

    def validate_kpi_year(self, record):
        total_kpi = self.env['sonha.kpi.year'].sudo().search([('year', '=', record.year),
                                                              ('sonha_kpi', '=', record.sonha_kpi.id)])
        validate_total = sum(total_kpi.mapped('kpi_year'))
        if validate_total > 1:
            raise ValidationError("KPI KH cả năm không được lớn hơn 100%")

    def filter_date_year(self, record):
        if record.sonha_kpi:
            record.year = record.sonha_kpi.year if record.sonha_kpi.year else ''
            record.department_id = record.sonha_kpi.department_id.id if record.sonha_kpi.department_id else ''

    def filter_conversion_data(self, r):
        key = self.env['sonha.kpi.year'].search([('year', '=', r.year),
                                                 ('sonha_kpi', '=', r.sonha_kpi.id)])
        if r.ti_le_monh_one:
            total = sum(key.mapped('ti_le_monh_one'))
            r.quy_doi_monh_one = (r.ti_le_monh_one * 100) * 100 / (total * 100)
        if r.ti_le_monh_two:
            total = sum(key.mapped('ti_le_monh_two'))
            r.quy_doi_monh_one = (r.ti_le_monh_two * 100) * 100 / (total * 100)
        if r.ti_le_monh_three:
            total = sum(key.mapped('ti_le_monh_three'))
            r.quy_doi_monh_one = (r.ti_le_monh_three * 100) * 100 / (total * 100)
        if r.ti_le_monh_four:
            total = sum(key.mapped('ti_le_monh_four'))
            r.quy_doi_monh_one = (r.ti_le_monh_four * 100) * 100 / (total * 100)
        if r.ti_le_monh_five:
            total = sum(key.mapped('ti_le_monh_five'))
            r.quy_doi_monh_one = (r.ti_le_monh_five * 100) * 100 / (total * 100)
        if r.ti_le_monh_six:
            total = sum(key.mapped('ti_le_monh_six'))
            r.quy_doi_monh_one = (r.ti_le_monh_six * 100) * 100 / (total * 100)
        if r.ti_le_monh_seven:
            total = sum(key.mapped('ti_le_monh_seven'))
            r.quy_doi_monh_one = (r.ti_le_monh_seven * 100) * 100 / (total * 100)
        if r.ti_le_monh_eight:
            total = sum(key.mapped('ti_le_monh_eight'))
            r.quy_doi_monh_one = (r.ti_le_monh_eight * 100) * 100 / (total * 100)
        if r.ti_le_monh_nigh:
            total = sum(key.mapped('ti_le_monh_nigh'))
            r.quy_doi_monh_one = (r.ti_le_monh_nigh * 100) * 100 / (total * 100)
        if r.ti_le_monh_ten:
            total = sum(key.mapped('ti_le_monh_ten'))
            r.quy_doi_monh_one = (r.ti_le_monh_ten * 100) * 100 / (total * 100)
        if r.ti_le_monh_eleven:
            total = sum(key.mapped('ti_le_monh_eleven'))
            r.quy_doi_monh_one = (r.ti_le_monh_eleven * 100) * 100 / (total * 100)
        if r.ti_le_monh_twenty:
            total = sum(key.mapped('ti_le_monh_twenty'))
            r.quy_doi_monh_one = (r.ti_le_monh_twenty * 100) * 100 / (total * 100)

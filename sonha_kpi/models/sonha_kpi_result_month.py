from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SonHaKPIResultMonth(models.Model):
    _name = 'sonha.kpi.result.month'

    department_id = fields.Many2one('hr.department')
    year = fields.Integer('Năm')
    name = fields.Many2one('sonha.kpi.year', string="Nội dung CV KPI cả năm")
    content_detail = fields.Text("Nội dung CV cụ thể")
    start_date = fields.Date('Bắt đầu')
    end_date = fields.Date("Hoàn thành")
    content = fields.Text("Nội dung")
    ti_trong = fields.Float("Tỉ trọng")
    description = fields.Text("Mô tả chi tiêt công việc")
    kpi_month = fields.Many2one('sonha.kpi.month')

    diem_chuan_amount_work = fields.Float("Điểm chuẩn (khối lượng CVTH)", default=50)
    diem_chuan_matter_work = fields.Float("Điểm chuẩn (Chất lượng CVTH)", default=30)
    diem_chuan_comply_regulations = fields.Float("Điểm chuẩn (Chấp hành nội quy, quy chế)", default=10)
    diem_chuan_initiative = fields.Float("Điểm chuẩn (Cải tiến, đề xuất, sáng kiến)", default=10)

    kq_hoan_thanh_amount_work = fields.Float("Kết quả hoàn thành ĐVĐG (khối lượng CVTH)")
    kq_hoan_thanh_matter_work = fields.Float("Kết quả hoàn thành ĐVĐG (Chất lượng CVTH)")
    kq_hoan_thanh_comply_regulations = fields.Float("Kết quả hoàn thành ĐVĐG (Chấp hành nội quy, quy chế)")
    kq_hoan_thanh_initiative = fields.Float("Kết quả hoàn thành ĐVĐG (Cải tiến, đề xuất, sáng kiến)")

    diem_dat_dv_amount_work = fields.Float("Điểm đạt ĐVĐG (khối lượng CVTH)", compute="filter_data_dvdg", store=True)
    diem_dat_dv_matter_work = fields.Float("Điểm đạt ĐVĐG (Chất lượng CVTH)", compute="filter_data_dvdg", store=True)
    diem_dat_dv_comply_regulations = fields.Float("Điểm đạt ĐVĐG (Chấp hành nội quy, quy chế)", compute="filter_data_dvdg", store=True)
    diem_dat_dv_initiative = fields.Float("Điểm đạt ĐVĐG (Cải tiến, đề xuất, sáng kiến)", compute="filter_data_dvdg", store=True)

    quy_doi_dv_amount_work = fields.Float("Điểm quy đổi theo tỉ trọng ĐVĐG (khối lượng CVTH)", compute="filter_data_dvdg", store=True)
    quy_doi_dv_matter_work = fields.Float("Điểm quy đổi theo tỉ trọng ĐVĐG (Chất lượng CVTH)", compute="filter_data_dvdg", store=True)
    quy_doi_dv_comply_regulations = fields.Float("Điểm quy đổi theo tỉ trọng ĐVĐG (Chấp hành nội quy, quy chế)", compute="filter_data_dvdg", store=True)
    quy_doi_dv_initiative = fields.Float("Điểm quy đổi theo tỉ trọng ĐVĐG (Cải tiến, đề xuất, sáng kiến)", compute="filter_data_dvdg", store=True)

    kq_hoan_thanh_tq_amount_work = fields.Float("Kết quả hoàn thành ĐVTQ (khối lượng CVTH)")
    kq_hoan_thanh_tq_matter_work = fields.Float("Kết quả hoàn thành ĐVTQ (Chất lượng CVTH)")
    kq_hoan_thanh_tq_comply_regulations = fields.Float("Kết quả hoàn thành ĐVTQ (Chấp hành nội quy, quy chế)")
    kq_hoan_thanh_tq_initiative = fields.Float("Kết quả hoàn thành ĐVTQ (Cải tiến, đề xuất, sáng kiến)")

    diem_dat_tq_amount_work = fields.Float("Điểm đạt ĐVTQ (khối lượng CVTH)", compute="filter_data_dvtq", store=True)
    diem_dat_tq_matter_work = fields.Float("Điểm đạt ĐVTQ (Chất lượng CVTH)", compute="filter_data_dvtq", store=True)
    diem_dat_tq_comply_regulations = fields.Float("Điểm đạt ĐVTQ (Chấp hành nội quy, quy chế)", compute="filter_data_dvtq", store=True)
    diem_dat_tq_initiative = fields.Float("Điểm đạt ĐVTQ (Cải tiến, đề xuất, sáng kiến)", compute="filter_data_dvtq", store=True)

    quy_doi_tq_amount_work = fields.Float("Điểm quy đổi theo tỉ trọng ĐVTQ (khối lượng CVTH)", compute="filter_data_dvtq", store=True)
    quy_doi_tq_matter_work = fields.Float("Điểm quy đổi theo tỉ trọng ĐVTQ (Chất lượng CVTH)", compute="filter_data_dvtq", store=True)
    quy_doi_tq_comply_regulations = fields.Float("Điểm quy đổi theo tỉ trọng ĐVTQ (Chấp hành nội quy, quy chế)", compute="filter_data_dvtq", store=True)
    quy_doi_tq_initiative = fields.Float("Điểm quy đổi theo tỉ trọng ĐVTQ (Cải tiến, đề xuất, sáng kiến)", compute="filter_data_dvtq", store=True)

    note = fields.Text("Nhận xét cấp thẩm quyền")
    sonha_kpi = fields.Many2one('company.sonha.kpi')

    def filter_data_dvtq(self, r):
        if r.diem_chuan_amount_work and r.kq_hoan_thanh_tq_amount_work:
            diem_dat_tq_amount_work = r.diem_chuan_amount_work * r.kq_hoan_thanh_tq_amount_work
            r.diem_dat_tq_amount_work = diem_dat_tq_amount_work
            r.quy_doi_tq_amount_work = diem_dat_tq_amount_work * r.ti_trong
        if r.diem_chuan_matter_work and r.kq_hoan_thanh_tq_matter_work:
            diem_dat_tq_matter_work = r.diem_chuan_matter_work * r.kq_hoan_thanh_tq_matter_work
            r.diem_dat_tq_matter_work = diem_dat_tq_matter_work
            r.quy_doi_tq_matter_work = diem_dat_tq_matter_work * r.ti_trong
        if r.diem_chuan_comply_regulations and r.kq_hoan_thanh_tq_comply_regulations:
            diem_dat_tq_comply_regulations = r.diem_chuan_comply_regulations * r.kq_hoan_thanh_tq_comply_regulations
            r.diem_dat_tq_comply_regulations = diem_dat_tq_comply_regulations
            r.quy_doi_tq_comply_regulations = diem_dat_tq_comply_regulations * r.ti_trong
        if r.diem_chuan_initiative and r.kq_hoan_thanh_tq_initiative:
            diem_dat_tq_initiative = r.diem_chuan_initiative * r.kq_hoan_thanh_tq_initiative
            r.diem_dat_tq_initiative = diem_dat_tq_initiative
            r.quy_doi_tq_initiative = diem_dat_tq_initiative * r.ti_trong

    def filter_data_dvdg(self, r):
        if r.diem_chuan_amount_work and r.kq_hoan_thanh_amount_work:
            diem_dat_dv_amount_work = r.diem_chuan_amount_work * r.kq_hoan_thanh_amount_work
            r.diem_dat_dv_amount_work = diem_dat_dv_amount_work
            r.quy_doi_dv_amount_work = diem_dat_dv_amount_work * r.ti_trong
        if r.diem_chuan_matter_work and r.kq_hoan_thanh_matter_work:
            diem_dat_dv_matter_work = r.diem_chuan_matter_work * r.kq_hoan_thanh_matter_work
            r.diem_dat_dv_matter_work = diem_dat_dv_matter_work
            r.quy_doi_dv_matter_work = diem_dat_dv_matter_work * r.ti_trong
        if r.diem_chuan_comply_regulations and r.kq_hoan_thanh_comply_regulations:
            diem_dat_dv_comply_regulations = r.diem_chuan_comply_regulations * r.kq_hoan_thanh_comply_regulations
            r.diem_dat_dv_comply_regulations = diem_dat_dv_comply_regulations
            r.quy_doi_dv_comply_regulations = diem_dat_dv_comply_regulations * r.ti_trong
        if r.diem_chuan_initiative and r.kq_hoan_thanh_initiative:
            diem_dat_dv_initiative = r.diem_chuan_initiative * r.kq_hoan_thanh_initiative
            r.diem_dat_dv_initiative = diem_dat_dv_initiative
            r.quy_doi_dv_initiative = diem_dat_dv_initiative * r.ti_trong

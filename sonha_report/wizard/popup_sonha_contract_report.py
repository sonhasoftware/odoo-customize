from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import date

class PopupSonhaContractReport(models.TransientModel):
    _name = 'popup.sonha.contract.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    department_domain = fields.Binary(compute="_compute_department_domain")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    employee_domain = fields.Binary(compute="_compute_employee_domain")
    contract_type_id = fields.Many2one('hr.contract.type', string="Kiểu hợp đồng")
    status = fields.Selection([('draft', "Mới"),
                               ('open', "Đang chạy"),
                               ('close', "Đã hết hạn"),
                               ('cancel', "Đã hủy")], string="Trạng thái")
    working_status = fields.Selection([('working', "Đang làm việc"),
                                       ('quit_job', "Nghỉ việc")], string="Trạng thái làm việc")

    @api.onchange("company_id")
    def _compute_department_domain(self):
        for rec in self:
            domain = []
            if rec.company_id:
                domain = [("company_id", "=", rec.company_id.id)]
            rec.department_domain = domain

    @api.onchange("company_id", "department_id")
    def _compute_employee_domain(self):
        for rec in self:
            domain = []
            if rec.department_id:
                domain = [("department_id", "=", rec.department_id.id)]
            elif rec.company_id:
                domain = [("company_id", "=", rec.company_id.id)]
            rec.employee_domain = domain

    def action_confirm(self):
        self.env['employee.report'].search([]).sudo().unlink()
        company_id = self.company_id.id if self.company_id else 0
        department_id = self.department_id.id if self.department_id else 0
        employee_id = self.employee_id.id if self.employee_id else 0
        start_date = self.from_date if self.from_date else date.today()
        end_date = self.to_date if self.to_date else date.today()
        contract_type_id = self.contract_type_id.id if self.contract_type_id else 0
        status = self.status if self.status else ''
        working_status = ''
        if self.working_status:
            working_status = 'lv' if self.working_status == 'working' else 'nv'

        query = "SELECT * FROM public.fn_bao_cao_hop_dong(%s, %s, %s, %s, %s, %s, %s, %s)"
        self.env.cr.execute(query, (company_id, start_date, end_date, department_id, employee_id, contract_type_id, status, working_status))
        rows = self.env.cr.dictfetchall()
        if rows:
            for row in rows:
                self.env['employee.report'].sudo().create({
                    'id_ns': row["id_ns"],
                    'ma_cham_cong': row["ma_cham_cong"],
                    'ma_nhan_vien': row["ma_nhan_vien"],
                    'ten_nhan_vien': row["ten_nhan_vien"],
                    'ngay_vao_cong_ty': row["ngay_vao_cong_ty"],
                    'ngay_vao': row["ngay_vao"],
                    'thang_vao': row["thang_vao"],
                    'nam_vao': row["nam_vao"],
                    'ngay_tiep_nhan': row["ngay_tiep_nhan"],
                    'phong_ban_id': row["phong_ban_id"],
                    'phong_ban': row["phong_ban"],
                    'chuc_vu': row["chuc_vu"],
                    'don_vi': row["don_vi"],
                    'gioi_tinh': row["gioi_tinh"],
                    'ngay_sinh': row["ngay_sinh"],
                    'tinh_trang_hon_nhan': row["tinh_trang_hon_nhan"],
                    'do_tuoi': row["do_tuoi"],
                    'dan_toc': row["dan_toc"],
                    'ton_giao': row["ton_giao"],
                    'nguyen_quan': row["nguyen_quan"],
                    'dia_chi_thuong_tru': row["dia_chi_thuong_tru"],
                    'noi_o_hien_tai': row["noi_o_hien_tai"],
                    'sdt': row["sdt"],
                    'so_cccd': row["so_cccd"],
                    'ngay_cap': row["ngay_cap"],
                    'noi_cap': row["noi_cap"],
                    'ma_so_thue': row["ma_so_thue"],
                    'bac_nhan_su': row["bac_nhan_su"],
                    'so_nam_tham_nien': row["so_nam_tham_nien"],
                    'so_thang_tham_nien': row["so_thang_tham_nien"],
                    'tham_nien': row["tham_nien"],
                    'trinh_do_vi_tinh': row["trinh_do_vi_tinh"],
                    'trinh_do_van_hoa': row["trinh_do_van_hoa"],
                    'ngoai_ngu': row["ngoai_ngu"],
                    'trinh_do_ngoai_ngu': row["trinh_do_ngoai_ngu"],
                    'ten_hd': row["ten_hd"],
                    'hop_dong_id': row["hop_dong_id"],
                    'tt_hd': row["tt_hd"],
                    'nhom_luong': row["nhom_luong"],
                    'khoi_me': row["khoi_me"],
                    'khoi_con': row["khoi_con"],
                    'trang_thai_lam_viec': row["trang_thai_lam_viec"],
                    'ngay_nghi_viec': row["ngay_nghi_viec"],
                    'ngay_nghi': row["ngay_nghi"],
                    'thang_nghi': row["thang_nghi"],
                    'nam_nghi': row["nam_nghi"],
                    'email': row["email"],
                    'nghi_lam': row["nghi_lam"],
                })
            return {
                    'type': 'ir.actions.act_window',
                    'name': 'Báo cáo hợp đồng',
                    'res_model': 'employee.report',
                    'view_mode': 'tree',
                    'views': [(self.env.ref('sonha_report.sonha_contract_employee_report_tree_view').id, 'tree')],
                    'target': 'current',
                }
        else:
            raise ValidationError("Không có dữ liệu!")



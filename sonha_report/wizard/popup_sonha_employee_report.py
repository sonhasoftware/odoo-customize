from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta


class PopupSonhaEmployeeReport(models.TransientModel):
    _name = 'popup.sonha.employee.report'

    from_date = fields.Date(string="Từ ngày", default=lambda self: self.default_from_date(), required=True)
    to_date = fields.Date(string="Đến ngày", default=lambda self: self.default_to_date(), required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị",
                                 domain="[('id', 'in', allowed_company_ids)]",
                                 default=lambda self: self.env.user.company_id, required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban",
                                    default=lambda self: self.default_department())
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  default=lambda self: self.default_employee_id())
    department_domain = fields.Binary(compute="_compute_department_domain")
    employee_domain = fields.Binary(compute="_compute_employee_domain")
    status_employee = fields.Selection([('working', "Đang làm việc"),
                                        ('quit_job', "Nghỉ việc")], string="Trạng thái làm việc")

    def default_from_date(self):
        now = datetime.today().date()
        from_date = now.replace(day=1)
        return from_date

    def default_to_date(self):
        now = datetime.today().date()
        to_date = (now.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
        return to_date

    def default_employee_id(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        if emp and not (self.env.user.has_group('sonha_employee.group_hr_employee') or self.env.user.has_group('sonha_employee.group_back_up_employee')):
            return emp
        else:
            return None

    def default_department(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        department_id = emp.department_id
        if department_id:
            return department_id
        else:
            return None

    @api.onchange("company_id")
    def _compute_department_domain(self):
        for rec in self:
            domain = [
                ('company_id', 'in', self.env.user.company_ids.ids),
                '|',
                ('manager_id.user_id', '=', self.env.user.id),
                ('id', '=', self.env.user.employee_id.department_id.id)
            ]
            if self.env.user.has_group('sonha_employee.group_hr_employee') or self.env.user.has_group(
                    'sonha_employee.group_back_up_employee'):
                domain = [('company_id', 'in', self.env.user.company_ids.ids)]
            if rec.company_id:
                domain.append(("company_id", "=", rec.company_id.id))
            rec.department_domain = domain

    @api.onchange("company_id", "department_id")
    def _compute_employee_domain(self):
        for rec in self:
            domain = [('company_id', 'in', self.env.user.company_ids.ids),
                      ('id', 'child_of', self.env.user.employee_id.id)]
            if self.env.user.has_group('sonha_employee.group_hr_employee') or self.env.user.has_group(
                    'sonha_employee.group_back_up_employee'):
                domain = [('company_id', 'in', self.env.user.company_ids.ids)]
            if rec.department_id:
                domain.append(("department_id", "=", rec.department_id.id))
            if rec.company_id:
                domain.append(("company_id", "=", rec.company_id.id))
            rec.employee_domain = domain

    def action_confirm(self):
        self.env['employee.report'].sudo().search([]).unlink()
        company_id = self.company_id.id if self.company_id else 0
        department_id = self.department_id.id if self.department_id else 0
        employee_id = self.employee_id.id if self.employee_id else 0
        start_date = self.from_date if self.from_date else date.today()
        end_date = self.to_date if self.to_date else date.today()
        status_employee = ''
        if self.status_employee:
            status_employee = 'lv' if self.status_employee == 'working' else 'nv'
        query = "SELECT * FROM public.fn_ho_so_nhan_su(%s, %s, %s, %s, %s, %s)"
        self.env.cr.execute(query, (company_id, start_date, end_date, department_id, employee_id, status_employee))
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
                    'nhom_luong': row["nhom_luong"],
                    'khoi_me': row["khoi_me"],
                    'khoi_con': row["khoi_con"],
                    'khong_xd_thoi_han': row["khong_xd_thoi_han"],
                    'co_xd_thoi_han': row["co_xd_thoi_han"],
                    'hd_thu_viec': row["hd_thu_viec"],
                    'hd_thoi_vu': row["hd_thoi_vu"],
                    'cong_tac_vien': row["cong_tac_vien"],
                    'khac': row["khac"],
                    'trang_thai_lam_viec': row["trang_thai_lam_viec"],
                    'ngay_nghi_viec': row["ngay_nghi_viec"],
                    'ngay_nghi': row["ngay_nghi"],
                    'thang_nghi': row["thang_nghi"],
                    'nam_nghi': row["nam_nghi"],
                    'email': row["email"],
                    'nghi_lam': row["nghi_lam"],
                    'state': 'employee',
                })
            return {
                    'type': 'ir.actions.act_window',
                    'name': 'Báo cáo hồ sơ nhân sự',
                    'res_model': 'employee.report',
                    'view_mode': 'tree',
                    'views': [(self.env.ref('sonha_report.emp_employee_report_tree_view').id, 'tree')],
                    'target': 'current',
                }
        else:
            raise ValidationError("Không có dữ liệu!")



from odoo import models, fields, api


class EmployeeReport(models.Model):
    _name = 'employee.report'

    id_ns = fields.Many2one('hr.employee', string="Nhân sự")
    ma_cham_cong = fields.Char(string="Mã chấm công")
    ma_nhan_vien = fields.Char(string="Mã nhân viên")
    ten_nhan_vien = fields.Char(string="Tên nhân viên")
    ngay_vao_cong_ty = fields.Date(string="Ngày vào công ty")
    ngay_vao = fields.Char(string="Ngày vào")
    thang_vao = fields.Char(string="Tháng vào")
    nam_vao = fields.Char(string="Năm vào")
    ngay_tiep_nhan = fields.Date(string="Ngày tiếp nhận")
    phong_ban_id = fields.Many2one('hr.department', string="Phòng ban")
    phong_ban = fields.Char(string="Tên phòng ban")
    chuc_vu = fields.Many2one('hr.job', string="Chức vụ")
    don_vi = fields.Many2one('res.company', string="Đơn vị")
    gioi_tinh = fields.Selection([('male', "Nam"),
                                  ('female', "Nữ"),
                                  ('other', "Khác")], string="Giới tính")
    ngay_sinh = fields.Date(string="Ngày sinh")
    tinh_trang_hon_nhan = fields.Selection([('single', "Độc thân"),
                                            ('married', "Đã kết hôn")], string="Tình trạng hôn nhân")
    do_tuoi = fields.Float(string="Độ tuổi")
    dan_toc = fields.Char(string="Dân tộc")
    ton_giao = fields.Selection([('yes', "Có"),
                                 ('no', "Không")], string="Tôn giáo")
    nguyen_quan = fields.Char(string="Nguyên quán")
    dia_chi_thuong_tru = fields.Char(string="Địa chỉ thường trú")
    noi_o_hien_tai = fields.Char(string="Nơi ở hiện tại")
    sdt = fields.Char(string="Số điện thoại")
    so_cccd = fields.Char(string="Số căng cước công dân")
    ngay_cap = fields.Date(string="Ngày cấp")
    noi_cap = fields.Char(string="Nơi cấp")
    ma_so_thue = fields.Char(string="Mã số thuế")
    bac_nhan_su = fields.Char(string="Bậc nhân sự")
    so_nam_tham_nien = fields.Float(string="Số năm thâm niên")
    so_thang_tham_nien = fields.Float(string="Số tháng thâm niên")
    tham_nien = fields.Char(string="Thâm niên")
    trinh_do_vi_tinh = fields.Char(string="Trình độ vi tính")
    trinh_do_van_hoa = fields.Char(string="Trình độ văn hóa")
    ngoai_ngu = fields.Char(string="Ngoại ngữ")
    trinh_do_ngoai_ngu = fields.Char(string="Trình độ ngoại ngữ")
    ten_hd = fields.Char(string="Tên hợp đồng")
    hop_dong_id = fields.Many2one('hr.contract.type', string="Hợp đồng")
    tt_hd = fields.Selection([('draft', "Mới"),
                               ('open', "Đang chạy"),
                               ('close', "Đã hết hạn"),
                               ('cancel', "Đã hủy")], string="Trạng thái hợp đồng")
    nhom_luong = fields.Char(string="Nhóm lương")
    khoi_me = fields.Char(string="Khối mẹ")
    khoi_con = fields.Char(string="Khối con")
    khong_xd_thoi_han = fields.Char(string="Không xác định thời hạn")
    co_xd_thoi_han = fields.Char(string="Có xác định thời hạn")
    hd_thu_viec = fields.Char(string="Hợp đồng thử việc")
    hd_thoi_vu = fields.Char(string="Hợp đồng thời vụ")
    cong_tac_vien = fields.Char(string="Cộng tác viên")
    khac = fields.Char(string="Khác")
    trang_thai_lam_viec = fields.Char(string="Trạng thái làm việc")
    ngay_nghi_viec = fields.Date(string="Ngày nghỉ việc")
    ngay_nghi = fields.Char(string="Ngày nghỉ")
    thang_nghi = fields.Char(string="Tháng nghỉ")
    nam_nghi = fields.Char(string="Năm nghỉ")
    email = fields.Char(string="Email")
    nghi_lam = fields.Char(string="Nghỉ làm")

    state = fields.Selection([('employee', "Nhân sự"),
                              ('contract', "Hợp đồng")], string="trạng thái")
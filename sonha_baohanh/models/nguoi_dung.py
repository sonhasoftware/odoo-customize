from odoo import api, fields, models


class NguoiDung(models.Model):
    _name = 'nguoi.dung'

    code = fields.Char(string="Mã người dùng")
    description = fields.Text(string="Tên người dùng")
    password = fields.Char(string="Mật khẩu")
    password_hint = fields.Text(string="PasswordHint")
    di_dong = fields.Char(string="Di động")
    email = fields.Char(string="Email")
    # chi_nhanh_ids = fields.One2many('bh.branch', 'nguoi_dung_ids', string="Chi nhánh")
    # chi_nhanh_ids = fields.Many2many(
    #     'bh.branch',
    #     #     #'nguoidung_chinhanh',  # Tên bảng trung gian
    #     #     #'id',  # Cột trỏ đến mô hình hiện tại
    #     #     #'id',  # Cột trỏ đến mô hình đích
    #     string="Chi nhánh"
    # )

    user_id = fields.Many2one('res.users', string="Tài khoản liên kết")


    def create_user(self):
        for r in self:
            user_vals = {
                'name': r.description,
                'login': r.email if r.email else r.code,
                'password': "1",
                'email': r.email or '',
                # 'employee_ids': [(4, r.id)],
                # 'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
            }
            self.env['res.users'].sudo().create(user_vals)
            r.user_id = self.env['res.users'].sudo().search(['|', ('login', '=', r.code),
                                                             ('login', '=', r.email)], limit=1)

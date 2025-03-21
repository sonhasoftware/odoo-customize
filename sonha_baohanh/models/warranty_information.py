from odoo import api, fields, models


class WarrantyInformation(models.Model):
    _name = 'warranty.information'
    _rec_name = 'display_warranty_code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    id = fields.Char(string="ID")
    reporter = fields.Char(string="Người báo")
    customer_information = fields.Text(string="Tên khách hàng", required=True)
    mobile_customer = fields.Char(string="Số điện thoại")

    province_id = fields.Many2one('province', string="Tỉnh thành")
    district_id = fields.Many2one('district', string="Quận/huyện", domain="[('province_id', '=', province_id)]")
    ward_commune_id = fields.Many2one('ward.commune', string="Phường/xã", domain="[('district_id', '=', district_id)]")
    address = fields.Text(string="Địa chỉ")
    product_type_id = fields.Many2one('product.type', string="Loại sản phẩm")
    error_information = fields.Text(string="Thông tin lỗi")
    branch_id = fields.Many2one('bh.branch', string="Chi nhánh")
    # staff_id = fields.Many2one('nhan.vien', string="Nhân viên")
    # bh_user_id = fields.Many2one('nguoi.dung', string="Quản lý")
    number_warranty_times = fields.Integer(string="Số lần bảo hành")
    warranty_status = fields.Selection([('open', "Mở"),
                                        ('close', "Đóng")], string="Trạng thái",
                                       default='open', compute="change_status", store=True, tracking=True)
    error_code = fields.Many2one('error.code', string="Mã lỗi", tracking=True)

    staff_number = fields.Char(string="Điện thoại nhân viên")
    call_date = fields.Datetime(string="Ngày gọi", default=fields.Datetime.now)
    appointment_date = fields.Datetime(string="Ngày hẹn", default=fields.Datetime.now)
    note = fields.Text(string="Ghi chú")
    amount = fields.Float(string="Số lượng")
    error_cause = fields.Text(string="Nguyên nhân lỗi", tracking=True)
    product_code = fields.Char(string="Mã sản phẩm", tracking=True)
    processing_content = fields.Text(string="Nội dung xử lý", tracking=True)
    produce_month = fields.Selection([('one', 1),
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
                                      ('twelve', 12)], string="Tháng sản xuất", tracking=True)
    distance = fields.Char(string="Cự li di chuyển(km)", tracking=True)
    service_fee = fields.Float(string="Phí dịch vụ", tracking=True)
    sent_date = fields.Datetime(string="Ngày gửi báo cáo", tracking=True)
    return_date = fields.Datetime(string="Ngày trả hàng", tracking=True)
    picture = fields.Many2many('ir.attachment', string="Ảnh hiện trường", tracking=True)
    exchange_form = fields.Many2one('form.exchange', string="Hình thức trao đổi", tracking=True)
    produce_year = fields.Many2one('produce.year', string="Năm sản xuất", tracking=True)
    warranty_date_completed = fields.Datetime(string="Ngày bảo hành xong", compute="fill_warranty_date_completed", store=True, tracking=True)
    import_company = fields.Boolean(string="Nhập kho", compute="is_import", store=True)
    transfer_warehouse = fields.Boolean(string="Chuyển kho")
    display_warranty_code = fields.Char(string="ID bảo hành", compute="filter_display_code", store=True)
    work = fields.Selection([('assign', 'Giao lịch'),
                             ('non_assign', 'Không giao lịch')], string="Giao lịch", required=True, default='assign')
    appointment = fields.Text(string="Hẹn khách")
    sap_document = fields.Char(string="Chứng từ")
    employee = fields.Many2one('bh.users', string="Nhân viên", domain="[('position', '=', 'employee')]")

    @api.depends('customer_information')
    def filter_display_code(self):
        for r in self:
            if r.id:
                if r.work == 'assign':
                    r.display_warranty_code = f"{r.id:06d}"
                else:
                    r.display_warranty_code = f"{r.id:06d}" + "N"
            else:
                r.display_warranty_code = ''


    @api.depends('exchange_form')
    def change_status(self):
        for r in self:
            if r.exchange_form.change_status:
                r.warranty_status = 'close'
            else:
                r.warranty_status = 'open'

    @api.depends('exchange_form', 'return_date')
    def fill_warranty_date_completed(self):
        for r in self:
            if r.exchange_form.change_done_date and r.return_date:
                r.warranty_date_completed = r.return_date
            else:
                r.warranty_date_completed = ''

    @api.depends('exchange_form')
    def is_import(self):
        for r in self:
            if r.exchange_form:
                r.import_company = True if r.exchange_form.import_company else False
            else:
                r.import_company = False




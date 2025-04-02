from odoo import api, fields, models
from datetime import datetime, time, timedelta
from odoo.exceptions import UserError, ValidationError

class WarrantyInformation(models.Model):
    _name = 'warranty.information'
    _rec_name = 'display_warranty_code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    id = fields.Char(string="ID")
    reporter = fields.Char(string="Người báo")
    customer_information = fields.Char(string="Tên khách hàng", required=True)
    mobile_customer = fields.Char(string="Số điện thoại")

    province_id = fields.Many2one('province', string="Tỉnh thành")
    district_id = fields.Many2one('district', string="Quận/huyện", domain="[('province_id', '=', province_id)]")
    ward_commune_id = fields.Many2one('ward.commune', string="Phường/xã", domain="[('district_id', '=', district_id)]")
    address = fields.Text(string="Địa chỉ")
    product_type_id = fields.Many2one('product.type', string="Loại sản phẩm")
    error_information = fields.Text(string="Thông tin lỗi")
    branch_id = fields.Many2one('bh.branch', string="Chi nhánh")
    number_warranty_times = fields.Integer(string="Số lần bảo hành")
    warranty_status = fields.Selection([('open', "Mở"),
                                        ('waiting', "Chờ"),
                                        ('branch_warehouse', "Về kho chi nhánh"),
                                        ('company_warehouse', "Về kho công ty"),
                                        ('fixing', "Đang sửa chữa"),
                                        ('fix_done', "Đã sửa chữa xong"),
                                        ('place_order', "Đã lập đơn hàng"),
                                        ('exported', "Đã xuất kho"),
                                        ('return_customer', "Sửa xong, nhập kho chi nhánh, kho VT"),
                                        ('close', "Đóng")], string="Trạng thái",
                                       default='open', tracking=True, compute="change_status", store=True)
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
                             ('wait_assign', 'Chờ giao lịch'),
                             ('non_assign', 'Không giao lịch')], string="Giao lịch", required=True, default='assign')
    appointment = fields.Text(string="Hẹn khách")
    sap_document = fields.Char(string="Chứng từ")
    non_fix = fields.Boolean(string="Không sửa", compute="is_non_fix", store=True)
    employee_id = fields.Many2one('hr.employee', string="Nhân viên")

    @api.constrains('work', 'appointment_date')
    def validate_appointment_date(self):
        now = datetime.now()
        for r in self:
            if r.work == 'wait_assign' and r.appointment_date <= now:
                raise ValidationError("Ngày hẹn phải lớn hơn ngày hiện tại!")

    @api.depends('work')
    def filter_display_code(self):
        for r in self:
            if r.work != 'assign':
                r.display_warranty_code = r.display_warranty_code + "N" if r.display_warranty_code else ''
            else:
                r.display_warranty_code = r.display_warranty_code.replace("N","") if r.display_warranty_code else ''

    def create(self, vals):
        record = super(WarrantyInformation, self).create(vals)
        vals = {
            'display_warranty_code': f"{record.id:06d}" if record.work != 'non_assign' else f"{record.id:06d}" + "N"
        }
        record.sudo().write(vals)
        return record

    @api.depends('exchange_form.change_done_date', 'return_date')
    def fill_warranty_date_completed(self):
        for r in self:
            if r.exchange_form.change_done_date and r.return_date:
                r.warranty_date_completed = r.return_date
            else:
                r.warranty_date_completed = ''

    @api.depends('exchange_form.non_fix')
    def is_non_fix(self):
        for r in self:
            if r.exchange_form.non_fix:
                r.non_fix = True
            else:
                r.non_fix = False

    def open_record(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'warranty.information',
            'res_id': self.id,
            'views': [(self.env.ref('sonha_baohanh.warranty_information_form_view').id, 'form')],
            'target': 'current',
        }

    def change_assign_status(self):
        now = datetime.now().date()
        list_record = self.env['warranty.information'].sudo().search([('work', '=', 'wait_assign')])
        list_record = list_record.filtered(lambda x: x.appointment_date.date() == now)
        for r in list_record:
            r.work = 'assign'

    @api.depends('exchange_form.import_company', 'exchange_form.change_status')
    def change_status(self):
        for r in self:
            if r.exchange_form.import_company:
                r.warranty_status = 'waiting'
            elif r.exchange_form.change_status:
                r.warranty_status = 'close'
            else:
                r.warranty_status = 'open'



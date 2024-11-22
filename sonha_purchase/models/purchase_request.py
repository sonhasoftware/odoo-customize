from odoo import models, fields, _
from odoo.exceptions import UserError
import psycopg2

class PurchaseRequest(models.Model):
    _name = 'purchase.request'

    message_main_attachment_id = fields.Integer(string="Main attachment", readonly=True)
    name = fields.Char(string="Mã Phiếu")
    x_user_id = fields.Many2one('res.users',string="Người đề nghị")
    x_company_id = fields.Many2one('res.company',string="Công ty", readonly=True)
    x_pr_date = fields.Datetime(string="Ngày đề nghị")
    state = fields.Selection(
        selection=[
            ('draft', 'Nháp'),
            ('approve','Đang phê duyệt')
        ],
        string="Trạng thái", default='draft', readonly=True
    )
    x_expected_cost = fields.Monetary(string="Tổng chi phí dự kiến", readonly=True)
    x_user_edit = fields.Many2one('res.users',string="Người bổ sung thông tin phiếu", readonly=True)
    x_note = fields.Text(string="Ghi chú bổ sung")
    # x_next_approver = fields.Many2many('res.users','user_rel','id','uid',string="Người duyệt tiếp theo", readonly=True)
    x_lock_edit = fields.Boolean(string="Khóa sửa")
    x_pr_type = fields.Selection(
        selection = [
            ('group_by','Mua tập trung'),
            ('individual','Mua độc lập')
        ],
        string="Loại yêu cầu"
    )
    currency_id = fields.Many2one('res.currency',string="Đơn vị tiề tệ")
    # x_type_budget_id = fields.Many2one('x.type.budget',string="Loại ngân sách",required=True)
    filename_authentication = fields.Char(string="Tên file")
    x_budget_plan = fields.Selection(
        selection = [
            ('in_plan','Trong kế hoạch'),
            ('out_plan','Ngoài kế hoạch')
        ],
        string="Ngân sách theo", required=True
    )
    x_date_pr_receive = fields.Date(string="Ngày muốn nhận hàng")
    x_approve_date = fields.Datetime(string="Ngày thông qua")
    x_product_frequent = fields.Selection(
        selection = [
            ('frequent','Hàng thường xuyên'),
            ('no_frequent','Hàng không thường xuyên')
        ],
        string="Hàng trong PR"
    )
    # x_pp_id = fields.Many2one('x.price.approval',string="Duyệt giá")
    x_remain_amount = fields.Monetary(string="Còn lại")
    x_budget_count = fields.Selection(
        selection=[
            ('in_budget','Trong ngân sách'),
            ('out_budget','Ngoài ngân sách')
        ],
        string="Đánh giá ngân sách"
    )
    x_date_request = fields.Datetime(string="Ngày gửi duyệt")
    x_date_approve = fields.Datetime(string="Ngày phê duyệt")
    x_time_approve = fields.Float(string="Thời gian hoàn thành")
    x_leadtime_pr = fields.Selection(
        selection=[
            ('none','Chưa xác định'),
            ('on_time','Trong thời gian quy định'),
            ('late','Trễ')
        ],
        string="Leadtime PR"
    )
    x_hr_department = fields.Many2one('hr.department',string="Phòng/Ban")
    x_begin = fields.Boolean(string="Sử dụng đầu kỳ")
    # x_hr_validate_procedure = fields.Many2one('x.hr.validate.procedure',string="Quy trình phê duyệt")
    last_approve_uid = fields.Many2one('res.users',string="Người phê duyệt cuối", readonly=True)
    x_descript = fields.Char(string="Diễn giải",required=True)
    # x_branch_id = fields.Many2one('x.branch',string="Chi nhánh")
    action_approve_uid = fields.Many2one('res.users',string="Người gửi duyệt")
    action_approve_date = fields.Datetime(string="Ngày gửi duyệt")
    x_type_pr = fields.Selection(
        selection=[
            ('ZNB','YCMH Lưu kho'),
            ('ZEX','YCMH dịch vụ, tiêu dùng phòng ban'),
            ('ZIO','YCMH Internal Order'),
            ('ZAS','YCMH Tài sản/Máy móc thiết bị')
        ],
        string="Loại yêu cầu mua hàng", required=True
    )
    sap_pr_name = fields.Char(string="Mã PR SAP", readonly=True)
    synch_sap = fields.Boolean(string="Đã đồng bộ SAP", readonly=True)
    using_sap_company = fields.Boolean(string="Triển khai SAP", readonly=True)


    def sync_purchase_request_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT name,x_descript FROM purchase_request"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            for r in data:
                records_to_create.append({
                    'name': r.get('name'),
                    'x_descript': r.get('x_descript'),
                })

        if records_to_create:
            self.sudo().create(records_to_create)
from odoo import models, fields, _
from odoo.exceptions import UserError
import psycopg2

class PurchaseRequest(models.Model):
    _name = 'purchase.request'

    name = fields.Char(string="Mã Phiếu")
    x_user_id = fields.Many2one('res.users',string="Người đề nghị")
    x_company_id = fields.Many2one('res.company',string="Công ty")
    x_pr_date = fields.Datetime(string="Ngày đề nghị")
    state = fields.Selection(
        selection=[
            ('draft', 'Nháp'),
            ('pending','Đang phê duyệt'),
            ('approve','Đã duyệt'),
            ('create_pp','Đã tạo phiếu tổng hợp'),
            ('deny','Không được duyệt'),
            ('cancel','Hủy'),
        ],
        string="Trạng thái", default='draft'
    )
    x_expected_cost = fields.Monetary(string="Tổng chi phí dự kiến")
    x_user_edit = fields.Many2one('res.users',string="Người bổ sung thông tin phiếu")
    x_note = fields.Text(string="Ghi chú bổ sung")
    # x_next_approver = fields.Many2many('res.users','user_rel','id','uid',string="Người duyệt tiếp theo")
    x_lock_edit = fields.Boolean(string="Khóa sửa")
    x_pr_type = fields.Selection(
        selection = [
            ('group_by','Mua tập trung'),
            ('individual','Mua độc lập')
        ],
        string="Loại yêu cầu"
    )
    currency_id = fields.Many2one('res.currency',string="Đơn vị tiề tệ")
    x_type_budget_id = fields.Many2one('x.type.budget',string="Loại ngân sách",)
    filename_authentication = fields.Char(string="Tên file")
    x_budget_plan = fields.Selection(
        selection = [
            ('in_plan','Trong kế hoạch'),
            ('out_plan','Ngoài kế hoạch')
        ],
        string="Ngân sách theo", 
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
    x_pp_id = fields.Many2one('x.price.approval',string="Duyệt giá")
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
    x_hr_validate_procedure = fields.Many2one('x.hr.validate.procedure',string="Quy trình phê duyệt")
    last_approve_uid = fields.Many2one('res.users',string="Người phê duyệt cuối")
    x_descript = fields.Char(string="Diễn giải",)
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
        string="Loại yêu cầu mua hàng", 
    )
    sap_pr_name = fields.Char(string="Mã PR SAP")
    synch_sap = fields.Boolean(string="Đã đồng bộ SAP")
    using_sap_company = fields.Boolean(string="Triển khai SAP")


    def sync_purchase_request_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                name,
                x_user_id,
                x_company_id,
                x_pr_date,
                state,
                x_expected_cost,
                x_user_edit,
                x_note,
                x_next_approver,
                x_lock_edit,
                x_pr_type,
                currency_id,
                x_type_budget_id,
                filename_authentication,
                x_budget_plan,
                x_date_pr_receive,
                x_approve_date,
                x_product_frequent,
                x_pp_id,
                x_remain_amount,
                x_budget_count,
                x_date_request,
                x_date_approve,
                x_time_approve,
                x_leadtime_pr,
                x_hr_department,
                x_begin,
                x_hr_validate_procedure,
                last_approve_uid,
                x_descript,
                x_branch_id,
                action_approve_uid,
                action_approve_date,
                x_type_pr,
                sap_pr_name,
                synch_sap,
                using_sap_company
            FROM 
                purchase_request
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'name': r.get('name'),
                    # 'x_user_id': r.get('x_user_id'),
                    # 'x_company_id': r.get('x_company_id'),
                    'x_pr_date': r.get('x_pr_date'),
                    'state': r.get('state'),
                    'x_expected_cost': r.get('x_expected_cost'),
                    # 'x_user_edit': r.get('x_user_edit'),
                    'x_note': r.get('x_note'),
                    # 'x_next_approver': r.get('x_next_approver'),
                    'x_lock_edit': r.get('x_lock_edit'),
                    'x_pr_type': r.get('x_pr_type'),
                    'currency_id': r.get('currency_id'),
                    'x_type_budget_id': r.get('x_type_budget_id'),
                    'filename_authentication': r.get('filename_authentication'),
                    'x_budget_plan': r.get('x_budget_plan'),
                    'x_date_pr_receive': r.get('x_date_pr_receive'),
                    'x_approve_date': r.get('x_approve_date'),
                    'x_product_frequent': r.get('x_product_frequent'),
                    'x_pp_id': r.get('x_pp_id'),
                    'x_remain_amount': r.get('x_remain_amount'),
                    'x_budget_count': r.get('x_budget_count'),
                    'x_date_request': r.get('x_date_request'),
                    'x_date_approve': r.get('x_date_approve'),
                    'x_time_approve': r.get('x_time_approve'),
                    'x_leadtime_pr': r.get('x_leadtime_pr'),
                    # 'x_hr_department': r.get('x_hr_department'),
                    'x_begin': r.get('x_begin'),
                    'x_hr_validate_procedure': r.get('x_hr_validate_procedure'),
                    # 'last_approve_uid': r.get('last_approve_uid'),
                    'x_descript': r.get('x_descript'),
                    # 'x_branch_id': r.get('x_branch_id'),
                    # 'action_approve_uid': r.get('action_approve_uid'),
                    'action_approve_date': r.get('action_approve_date'),
                    'x_type_pr': r.get('x_type_pr'),
                    'sap_pr_name': r.get('sap_pr_name'),
                    'synch_sap': r.get('synch_sap'),
                    'using_sap_company': r.get('using_sap_company'),
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))
from odoo import models,fields,_

# các trường comment là cần thiết nhưng có thể chưa được liên kết với model
class XPriceApproval(models.Model):
    _name = 'x.price.approval'

    name = fields.Char(string="Tổng hợp đề nghị đặt hàng")
    x_pr_selected_count = fields.Integer(string="X Pr Selected Count")
    x_po_count = fields.Integer(string="X Po Count")
    # x_user_id = fields.Many2one('res.users',string="Người thực hiện")
    # x_company_id = fields.Many2one('res.company', string="Công ty")
    x_date_create = fields.Date(string="Ngày tạo")
    # x_supplier_selected_id = fields.Many2one('res.partner',string="NCC được chọn")
    state = fields.Selection(
        selection=[
            ('create_pp', 'Tạo duyệt giá'),
            ('to_approve','Chờ duyệt'),
            ('approve','Đã duyệt một phần'),
            ('done','Hoàn thành')
        ],
        string="Trạng thái"
    )
    x_time_cre = fields.Float(string="Thời gian tạo PP từ PR (ngày)")
    x_date_approve = fields.Datetime(string="Ngày hoàn thành")
    x_time_approve = fields.Float(string="Thời gian hoàn thành (ngày)")
    x_leadtime_cre_pp = fields.Selection(
        selection=[
            ('none','Chưa xác định'),
            ('on_time','Trong thời gian quy định'),
            ('late','Trễ'),
        ],
        string="Leadtime Create PP"
    )
    x_leadtime_approve_pp = fields.Selection(
        selection=[
            ('none','Chưa xác định'),
            ('on_time','Trong thời gian quy định'),
            ('late','Trễ'),
        ],
        string="Leadtime Approve PP"
    )
    # x_hr_procedure_id = fields.Many2one('x.hr.validate.procedure',string="Quy trình phê duyệt")
    # x_sum = fields.Monetary(string="Tổng")

    def sync_x_price_approval_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                name,
                x_pr_selected_count,
                x_po_count,
                x_user_id,
                x_company_id,
                x_date_create,
                x_supplier_selected_id,
                state,
                x_time_cre,
                x_date_approve,
                x_time_approve,
                x_leadtime_cre_pp,
                x_leadtime_approve_pp,
                x_hr_procedure_id,
                x_sum
            FROM 
                x_price_approval
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'name' : r.get('name'),
                    'x_pr_selected_count' : r.get('x_pr_selected_count'),
                    'x_po_count' : r.get('x_po_count'),
                    # 'x_user_id' : r.get('x_user_id'),
                    # 'x_company_id' : r.get('x_company_id'),
                    'x_date_create' : r.get('x_date_create'),
                    # 'x_supplier_selected_id' : r.get('x_supplier_selected_id'),
                    'state' : r.get('state'),
                    'x_time_cre' : r.get('x_time_cre'),
                    'x_date_approve' : r.get('x_date_approve'),
                    'x_time_approve' : r.get('x_time_approve'),
                    'x_leadtime_cre_pp' : r.get('x_leadtime_cre_pp'),
                    'x_leadtime_approve_pp' : r.get('x_leadtime_approve_pp'),
                    # 'x_hr_procedure_id' : r.get('x_hr_procedure_id'),
                    # 'x_sum' : r.get('x_sum'),
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))
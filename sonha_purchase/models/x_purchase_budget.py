from odoo import fields, models, _

# các trường cmt là cần thiết nhưng chưa liên kết model
class XPurchaseBudget(models.Model):
    _name = 'x.purchase.budget'

    type = fields.Selection(
        selection=[
            ('dtd','Dùng trừ dần'),
            ('d1l','Dùng 1 lần')
        ],
        string="Kiểu ngân sách"
    )
    name = fields.Char(string="Tên ngân sách")
    state = fields.Selection(
        selection=[
            ('new','Mới'),
            ('confirmed','Đã xác nhận'),
            ('canceled','Hủy'),
        ],
        string="Trạng thái"
    )
    # user_id = fields.Many2one('res.users',string="Người đề nghị")
    # x_department_id = fields.Many2one('hr.department',string="Phòng/Ban")
    # company_id = fields.Many2one('res.company',string="Công ty")
    # x_type_id = fields.Many2one('x.type.budget',string="Loại ngân sách")
    x_date_from = fields.Date(string="Từ ngày")
    x_date_to = fields.Date(string="Đến ngày")
    # x_amount = fields.Monetary(string="Ngân sách")
    # x_used_amount = fields.Monetary(string="Đã sử dụng")
    # x_remain_amount = fields.Monetary(string="Còn lại")

    def sync_x_purchase_budget_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                type,
                name,
                state,
                user_id,
                x_department_id,
                company_id,
                x_type_id,
                x_date_from,
                x_date_to,
                x_amount,
                x_used_amount,
                x_remain_amount
            FROM 
                x_purchase_budget
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'type' : r.get('type'),
                    'name' : r.get('name'),
                    'state' : r.get('state'),
                    # 'user_id' : r.get('user_id'),
                    # 'x_department_id' : r.get('x_department_id'),
                    # # 'company_id' : r.get('company_id'),
                    # 'x_type_id' : r.get('x_type_id'),
                    'x_date_from' : r.get('x_date_from'),
                    'x_date_to' : r.get('x_date_to'),
                    # 'x_amount' : r.get('x_amount'),
                    # 'x_used_amount' : r.get('x_used_amount'),
                    # 'x_remain_amount' : r.get('x_remain_amount'),
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))
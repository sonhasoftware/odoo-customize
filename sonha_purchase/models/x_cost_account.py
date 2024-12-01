from odoo import models, fields, _

# các trường comment là cần thiết nhưng có thể chưa có model liên kết
class XCostAccount(models.Model):
    _name = 'x.cost.account'

    code = fields.Char(string="Số tài khoản")
    cost_center_id = fields.Many2one('x.cost.center',string="Trung tâm chịu chi phí")
    io_code_id = fields.Many2one('internal.order.code',string="Mã lệnh IO")
    name = fields.Char(string="Tài khoản")
    descript = fields.Char(string="Mô tả")
    # company_id = fields.Many2one('res.company',string="Công ty")

    def sync_x_cost_account_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                code,
                cost_center_id,
                io_code_id,
                name,
                descript,
                company_id
            FROM 
                x_cost_account
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'code' : r.get('code'),
                    'cost_center_id' : r.get('cost_center_id'),
                    'io_code_id' : r.get('io_code_id'),
                    'name' : r.get('name'),
                    'descript' : r.get('descript'),
                    # 'company_id' : r.get('company_id')
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))
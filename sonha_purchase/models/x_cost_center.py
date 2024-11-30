from odoo import models, fields, _

# các trường comment là cần thiết nhưng có thể chưa có model liên kết
class XCostCenter(models.Model):
    _name = 'x.cost.center'

    code = fields.Char(string="Mã")
    name = fields.Char(string="Bộ phận")
    descript = fields.Char("Mô tả")
    # company_id = fields.Many2one('res.company',string="Công ty")

    def sync_x_cost_center_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                code,
                name,
                descript,
                company_id
            FROM 
                x_cost_center
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'code' : r.get('name'),
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

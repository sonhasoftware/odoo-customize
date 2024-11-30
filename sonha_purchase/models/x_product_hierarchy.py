from odoo import models,fields,_

# các trường cmt là cần thiết nhưng có thể chưa liên kết model
class XProductHierarchy(models.Model):
    _name = 'x.product.hierarchy'

    x_product_hierarchy = fields.Char(string="Mã PRH")
    x_description = fields.Char(string="Mô tả")
    # x_level_number = fields.Many2one('x.product.level',string="Cấp độ")

    def sync_x_product_hierarchy_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                x_product_hierarchy,
                x_description,
                x_level_number
            FROM 
                x_product_hierarchy
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'x_product_hierarchy' : r.get('x_product_hierarchy'),
                    'x_description' : r.get('x_description'),
                    # 'x_level_number' : r.get('x_level_number'),
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))
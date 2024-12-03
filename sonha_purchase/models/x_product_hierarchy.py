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
                x_product_hierarchy,
                x_description,
                x_level_number
            FROM 
                x_product_hierarchy
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            for r in data:
                records_to_create.append({
                    'x_product_hierarchy' : r.get('x_product_hierarchy'),
                    'x_description' : r.get('x_description'),
                    # 'x_level_number' : r.get('x_level_number'),
                })

        if records_to_create:
            self.sudo().create(records_to_create)
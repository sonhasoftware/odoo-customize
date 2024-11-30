from odoo import models, fields, _

# các trường comment là cần thiêts nhưng có thể chưa có model liên kết
class ProductCategory(models.Model):
    _name = 'product.category.custom'

    name = fields.Char(string="Name")
    complete_name = fields.Char(string="Complete Name")
    # parent_id = fields.Many2one('product.category', string="Parent Category")
    parent_path = fields.Char(string="Parent Path")
    # removal_strategy_id = fields.Many2one('product.removal', string="Force Removal Strategy")
    packaging_reserve_method = fields.Selection(
        selection=[
            ('full', 'Reserve Only Full Packagings'),
            ('partial', 'Reserve Partial Packagings'),
        ],
        string="Reserve Packagings"
    )

    def sync_product_category_custom_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                name,
                complete_name,
                parent_id,
                parent_path,
                removal_strategy_id,
                packaging_reserve_method
            FROM 
                product_category
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'name' : r.get('name'),
                    'complete_name' : r.get('complete_name'),
                    # 'parent_id' : r.get('parent_id'),
                    'parent_path' : r.get('parent_path'),
                    # 'removal_strategy_id' : r.get('removal_strategy_id'),
                    'packaging_reserve_method' : r.get('packaging_reserve_method')
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))


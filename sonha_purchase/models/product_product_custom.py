from odoo import models, fields,_

class ProductProductCustom(models.Model):
    _name = 'product.product.custom'

    default_code = fields.Char(string="Internal Reference")
    active = fields.Boolean(string="Active")
    # product_tmpl_id = fields.Many2one('product.template',string="Product Template")
    barcode = fields.Char(string="Barcode")
    combination_indices = fields.Char(string="Combination Indices")
    volume = fields.Float(string="Volume")
    weight = fields.Float(string="Weight")
    can_image_variant_1024_be_zoomed = fields.Boolean(string="Can Image Variant 1024 Be Zoomed")

    def sync_product_product_custom_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                default_code,
                active,
                product_tmpl_id,
                barcode,
                combination_indices,
                volume,
                weight,
                can_image_variant_1024_be_zoomed
            FROM 
                product_product
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'default_code' : r.get('default_code'),
                    'active' : r.get('active'),
                    # 'product_tmpl_id' : r.get('product_tmpl_id'),
                    'barcode' : r.get('barcode'),
                    'combination_indices' : r.get('combination_indices'),
                    'volume' : r.get('volume'),
                    'weight' : r.get('weight'),
                    'can_image_variant_1024_be_zoomed' : r.get('can_image_variant_1024_be_zoomed'),
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {}
                            SET id = %s
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))

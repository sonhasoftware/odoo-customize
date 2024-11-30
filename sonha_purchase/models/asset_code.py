from odoo import  models, fields, _

# các trường được comment là cần thiết nhưng chưa liên kết model
class AssetCode(models.Model):
    _name = 'asset.code'

    name = fields.Char(string="Mã tài sản")
    # company_id = fields.Many2one('res.company',string="Công ty")
    descript = fields.Char(string="Mô tả")

    def sync_asset_code_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                name,
                company_id,
                descript
            FROM 
                asset_code
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'name' : r.get('name'),
                    # 'company_id' : r.get('company_id'),
                    'descript' : r.get('descript'),
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))
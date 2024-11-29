from odoo import fields,models,_

# các trường comment là cần thiết nhưng có thể chưa được liên kết với model
class InternalOrderCode(models.Model):
    _name = 'internal.order.code'

    name = fields.Char(string="Mã IO")
    # company_id = fields.Many2one('res.company',string="Công ty")
    descript = fields.Char(string="Mô tả")

    def sync_internal_order_code_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                name,
                company_id,
                descript
            FROM 
                internal_order_code
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            for r in data:
                records_to_create.append({
                    'name' : r.get('name'),
                    # 'company_id' : r.get('company_id'),
                    'descript' : r.get('descript'),
                })

        if records_to_create:
            self.sudo().create(records_to_create)

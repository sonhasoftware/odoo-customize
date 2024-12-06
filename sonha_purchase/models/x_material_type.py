from odoo import models, fields, _

class XMaterialType(models.Model):
    _name = 'x.material.type'

    name = fields.Char(string="Tên")
    x_code = fields.Char(string="Mã")
    x_purpose = fields.Char(string="Mục đích sử dụng")
    x_qty_manage = fields.Boolean(string="Quản lý số lượng")
    x_value_manage = fields.Boolean(string="Quản lý giá Trị")
    x_price_type = fields.Selection(
        selection=[
            ('s','S'),
            ('v','V'),
        ],
        string="Loại giá"
    )
    x_odoo_product_type = fields.Selection(
        selection=[
            ('consump','Tiêu dùng'),
            ('service','Dịch vụ'),
            ('stored','Lưu kho'),
        ],
        string="Lọa sản phẩm Odoo"
    )

    def sync_x_material_type_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                name,
                x_code,
                x_purpose,
                x_qty_manage,
                x_value_manage,
                x_price_type,
                x_odoo_product_type
            FROM 
                x_material_type
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'name': r.get('name'),
                    'x_code': r.get('x_code'),
                    'x_purpose': r.get('x_purpose'),
                    'x_qty_manage': r.get('x_qty_manage'),
                    'x_value_manage': r.get('x_value_manage'),
                    'x_price_type': r.get('x_price_type'),
                    'x_odoo_product_type': r.get('x_odoo_product_type')
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))

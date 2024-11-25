from odoo import models, fields, _

class UomUom(models.Model):
    _name = 'uom.uom.custom'

# các trường comment có nhưng chưa có model tham chiếu đến
    name = fields.Char(string="Unit of Measure")
    # category_id = fields.Many2one('uom.category',string="Category")
    factor = fields.Float(string="Ratio")
    rounding = fields.Float(string="Rounding Precision")
    active = fields.Boolean(string="Active")
    uom_type = fields.Selection(
        selection=[
            ('bigger','Bigger than the reference Unit of Measure'),
            ('reference','Reference Unit of Measure for this category'),
            ('smaller','Smaller than the reference Unit of Measure'),
        ],
        string="Type"
    )
    sap_key = fields.Char(string="SAP Key")


    def sync_uom_uom_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT name,factor,rounding,active,uom_type,sap_key FROM uom_uom"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            for r in data:
                records_to_create.append({
                    'name': r.get('name'),
                    'factor':r.get('factor'),
                    'rounding':r.get('rounding'),
                    'active':r.get('active'),
                    'uom_type':r.get('uom_type'),
                    'sap_key':r.get('sap_key')
                })

        if records_to_create:
            self.sudo().create(records_to_create)
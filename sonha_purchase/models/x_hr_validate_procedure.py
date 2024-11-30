from odoo import models, fields, _

class XHrValidateProcedure(models.Model):
    _name = "x.hr.validate.procedure"

    name = fields.Char(string="Quy trình phê duyệt")
    x_validate_license_type = fields.Many2one('ir.model',string="Loại chứng từ")
    model_name = fields.Char(string="Model")
    x_domain = fields.Char(string="Điều kiện")
    x_extend_title = fields.Many2one('x.hr.validate.person',string="Vai trò bổ sung")

    def sync_x_hr_validate_procedure_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT id,name,x_validate_license_type,model_name,x_domain,x_extend_title FROM x_hr_validate_procedure"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'name': r.get('name'),
                    # 'x_validate_license_type': r.get('x_validate_license_type'),
                    'model_name': r.get('model_name'),
                    'x_domain': r.get('x_domain'),
                    # 'x_extend_title': r.get('x_extend_title')
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))
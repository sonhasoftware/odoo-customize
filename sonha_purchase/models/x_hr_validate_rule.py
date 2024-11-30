from odoo import models, fields, _


class XHrValidateRule(models.Model):
    _name = 'x.hr.validate.rule'

# các trường comment là các trường cần thiết, có thể chưa có model liên kết
    name = fields.Char(string="Quy tắc phê duyệt")
    # x_validate_title = fields.Many2one('x.hr.validate.person',string="Vai trò phê duyệt")
    x_sequence = fields.Integer(string="Trình tự")
    # x_validate_department = fields.Many2one('hr.department',string="Phòng/Ban phê duyệt")
    # x_validate_person = fields.Many2one('res.users',string="Người phê duyệt")
    x_validate_person_domain = fields.Char(string="domain Người phê duyệt")
    # procedure_id = fields.Many2one('x.hr.validate.procedure',string='Quy trình')
    x_method = fields.Selection(
        selection=[
            ('by_title','Vai trò'),
            ('by_department','Quản lý Ban/Trung tâm'),
            ('by_manager','Người quản lý'),
            ('by_user','Chỉ định người duyệt'),
            ('qlbttcnt','Quản Lý Ban/Trung tâm của người tạo'),
            ('gdptdvnt','Giám đốc phụ trách đơn vị người tạo'),
            ('by_creator','Bởi người tạo'),
        ],
        string="Phương thức"
    )
    # x_limit = fields.Monetary(string="Hạn mức", currency_field='currency_id')
    # currency_id = fields.Many2one('res.currency', string="Loại tiền tệ",default=lambda self: self.env.company.currency_id)
    # x_report_major_id = fields.Many2one('x.report.field',string="Lĩnh vực tờ tình")
    x_level = fields.Selection(
        selection=[
            ('suggesting','Đề xuất'),
            ('testing','Thẩm tra'),
            ('checking','Soát xét'),
            ('approving','Phê duyệt'),
        ],
        string="Level"
    )

    def sync_x_hr_validate_rule_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                name,
                x_validate_title,
                x_sequence,
                x_validate_department,
                x_validate_person,
                x_validate_person_domain,
                procedure_id,
                x_method,
                x_limit,
                x_report_major_id,
                x_level 
            FROM 
                x_hr_validate_rule
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'name': r.get('name'),
                    # 'x_validate_title': r.get('x_validate_title'),
                    'x_sequence': r.get('x_sequence'),
                    # 'x_validate_department': r.get('x_validate_department'),
                    # 'x_validate_person': r.get('x_validate_person'),
                    'x_validate_person_domain': r.get('x_validate_person_domain'),
                    # 'procedure_id': r.get('procedure_id'),
                    'x_method': r.get('x_method'),
                    # 'x_limit': r.get('x_limit'),
                    # 'x_report_major_id': r.get('x_report_major_id'),
                    'x_level': r.get('x_level')
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))
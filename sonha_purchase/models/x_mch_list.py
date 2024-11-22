from odoo import models, fields, _

class XMCHList(models.Model):
    _name = "x.mch.list"

    id = fields.Integer(string="ID")
    parent_level = fields.Integer(string="Cấp MCH")
    parent_path = fields.Integer(string="Parent Path", index=True )
    name = fields.Char(string="Tên MCH")
    x_mch_code = fields.Char(string="MÃ MCH")
    x_parent_id = fields.Many2one('x.mch.list',string="MCH cha")
    x_user_id = fields.Many2one('res.users',string="Người phụ trách")
    x_buy_group = fields.Boolean(string="Cần mua tập trung")
    target_dio = fields.Float(string="")
    leadtime = fields.Float(string="Leadtime")
    x_matgr_des60 = fields.Char(string="Tên đầy đủ")
    x_des_zmch = fields.Char(string="Diễn giải")

    def sync_x_mch_list_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                id,
                parent_level,
                parent_path,
                name,
                x_mch_code,
                x_parent_id,
                x_user_id,
                x_buy_group,
                target_dio,
                leadtime,
                x_matgr_des60,
                x_des_zmch
            FROM 
                x_mch_list
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            for r in data:
                records_to_create.append({
                    'id': r.get('id'),
                    'parent_level': r.get('parent_level'),
                    'parent_path': r.get('parent_path'),
                    'name': r.get('name'),
                    'x_mch_code': r.get('x_mch_code'),
                    # 'x_parent_id': r.get('x_parent_id'),
                    'x_user_id': r.get('x_user_id'),
                    'x_buy_group': r.get('x_buy_group'),
                    'target_dio': r.get('target_dio'),
                    'leadtime': r.get('leadtime'),
                    'x_matgr_des60': r.get('x_matgr_des60'),
                    'x_des_zmch': r.get('x_des_zmch')
                })

        if records_to_create:
            self.sudo().create(records_to_create)
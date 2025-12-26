from odoo import api, fields, models


class SapUnlock(models.Model):
    _name = 'sap.unlock'

    user_name = fields.Char(string="User", store=True)
    password = fields.Char(string="Mật khẩu", store=True)

    def action_confirm(self):
        self.env.cr.execute("""SELECT * FROM fn_mk_sap();""", ())
        check = self.env.cr.dictfetchall()
        if check:
            result = check[0]
            thong_bao = list(result.values())[0]
            if thong_bao:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Thông báo',
                    'res_model': 'notice.wizard',
                    'view_mode': 'form',
                    'context': {
                        'default_notice': thong_bao,
                    },
                    'target': 'new',
                }



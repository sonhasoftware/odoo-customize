from odoo import api, fields, models


class MDMKhachHangLine(models.Model):
    _name = 'mdm.khach.hang.line'
    _description = 'Bảng con MDM khách hàng'

    khach_hang_id = fields.Many2one('mdm.khach.hang', string='Khách hàng', required=True, ondelete='cascade')
    ma_mdm = fields.Char(string='Mã MDM')
    ma_dv = fields.Char(string='Mã đơn vị')
    dvcs = fields.Many2one('res.company', string='ĐVCS')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_mdm_api_sync'):
            for record in records.filtered('khach_hang_id'):
                record.khach_hang_id.call_api_insert(record.khach_hang_id, line=record)
        return records

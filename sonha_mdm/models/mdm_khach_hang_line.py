from odoo import api, fields, models


class MDMKhachHangLine(models.Model):
    _name = 'mdm.khach.hang.line'
    _description = 'Bảng con MDM khách hàng'

    khach_hang_id = fields.Many2one('mdm.khach.hang', string='Khách hàng', required=True, ondelete='cascade')
    ma_mdm = fields.Char(string='Mã MDM')
    ma_dv = fields.Char(string='Mã đơn vị')
    dvcs = fields.Many2one('res.company', string='ĐVCS')
    da_call_api = fields.Boolean(string="Đã call API", copy=False, readonly=True)
    thoi_gian_call_api = fields.Datetime(string="Thời gian call API", copy=False, readonly=True)
    ket_qua_call_api = fields.Text(string="Kết quả call API", copy=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not self.env.context.get('skip_mdm_api_sync'):
                record.khach_hang_id.call_api_insert(record.khach_hang_id, line=record)
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_mdm_api_sync'):
            for record in self:
                record.khach_hang_id.call_api_update(record.khach_hang_id, line=record)
        return res

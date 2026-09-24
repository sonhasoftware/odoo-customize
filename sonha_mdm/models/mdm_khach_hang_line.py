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

    def _sync_parent_company(self):
        """Keep the customer company aligned with the latest child-line value."""
        parents = self.mapped('khach_hang_id')
        for parent in parents:
            latest_line = self.search(
                [('khach_hang_id', '=', parent.id), ('dvcs', '!=', False)],
                order='create_date desc, id desc',
                limit=1,
            )
            if latest_line and parent.dvcs != latest_line.dvcs:
                # The child line is responsible for API synchronization.  Avoid
                # a parent API update using its previous/default company.
                parent.with_context(
                    skip_mdm_api_sync=True,
                    skip_mdm_parent_company_sync=True,
                ).write({
                    'dvcs': latest_line.dvcs.id,
                })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_parent_company()
        for record in records:
            if not self.env.context.get('skip_mdm_api_sync'):
                record.khach_hang_id.call_api_insert(record.khach_hang_id, line=record)
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'dvcs' in vals:
            self._sync_parent_company()
        if not self.env.context.get('skip_mdm_api_sync'):
            for record in self:
                record.khach_hang_id.call_api_update(record.khach_hang_id, line=record)
        return res

    def unlink(self):
        parents = self.mapped('khach_hang_id')
        res = super().unlink()
        # If the latest row was removed, use the latest remaining child row.
        for parent in parents:
            parent.bang_con_ids._sync_parent_company()
        return res

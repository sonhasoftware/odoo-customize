from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class SonHaResUser(models.Model):
    _inherit = 'res.users'

    device_id = fields.Char("ID thiết bị")

    # def create(self, vals):
    #     res = super(SonHaResUser, self).create(vals)
    #     res.action_create_employee()
    #     return res


class BaseModel(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def export_data(self, fields):
        # Gọi phương thức export_data gốc
        data = super(BaseModel, self).export_data(fields)

        # Thay đổi định dạng ngày trong dữ liệu export
        for record in data['datas']:
            for i, field_name in enumerate(fields):
                field = self._fields.get(field_name)
                if field and field.type == 'date' and record[i]:
                    # Nếu giá trị là datetime.date, chuyển thành chuỗi
                    date_value = record[i] if isinstance(record[i], str) else record[i].strftime('%Y-%m-%d')
                    # Chuyển đổi định dạng từ năm-tháng-ngày sang ngày/tháng/năm
                    record[i] = datetime.strptime(date_value, '%Y-%m-%d').strftime('%d/%m/%Y')

        return data

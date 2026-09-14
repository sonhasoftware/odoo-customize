import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BaoCaoDuAn(models.Model):
    _name = 'sonha.du.an.bao.cao'
    _description = 'Báo cáo dự án'
    _table = 'bao_cao'

    name = fields.Char(
        string='Tên',
        required=True,
        readonly=True,
    )

    tu_ngay = fields.Date(
        string='Từ ngày',
        required=True,
        readonly=True,
    )

    den_ngay = fields.Date(
        string='Đến ngày',
        required=True,
        readonly=True,
    )

    # =========================================================
    # DỰ ÁN CHA
    # =========================================================

    du_an_cha_id = fields.Many2one(
        'project.project',
        string='Dự án cha',
        readonly=True,
        ondelete='restrict',
        index=True,
    )

    # =========================================================
    # THÔNG TIN BÁO CÁO
    # =========================================================

    stt = fields.Integer(
        string='STT',
        readonly=True,
    )

    noi_dung_cv_con = fields.Char(
        string='Nội dung công việc con',
        readonly=True,
    )

    ngay_bat_dau = fields.Date(
        string='Ngày bắt đầu',
        readonly=True,
    )

    ngay_ket_thuc = fields.Date(
        string='Ngày kết thúc',
        readonly=True,
    )

    ngay_hoan_thanh = fields.Date(
        string='Ngày hoàn thành',
        readonly=True,
    )

    so_ngay_qua_han = fields.Integer(
        string='Số ngày quá hạn',
        readonly=True,
    )

    ten_trang_thai = fields.Text(
        string='Tên trạng thái',
        readonly=True,
    )

    tinh_trang_han = fields.Text(
        string='Tình trạng hạn',
        readonly=True,
    )

    pt_cv = fields.Float(
        string='% công việc',
        readonly=True,
    )

    ns_lam = fields.Text(
        string='Nhân sự làm',
        readonly=True,
    )

    # =========================================================
    # LEVEL
    # =========================================================

    in_dam = fields.Integer(
        string='Cấp',
        readonly=True,
        index=True,
    )

    # ID dự án theo dữ liệu trả về từ function
    du_an_con_id = fields.Integer(
        string='Dự án con ID',
        readonly=True,
    )

    # =========================================================
    # GROUP DỰ ÁN
    # =========================================================

    parent_group_id = fields.Integer(
        string='Nhóm dự án cha ID',
        readonly=True,
        index=True,
    )

    child_group_id = fields.Integer(
        string='Nhóm dự án con ID',
        readonly=True,
        index=True,
    )

    parent_group_name = fields.Char(
        string='Nhóm dự án cha',
        readonly=True,
        index=True,
    )

    child_group_name = fields.Char(
        string='Nhóm dự án con',
        readonly=True,
        index=True,
    )

    du_lieu = fields.Text(
        string='Dữ liệu báo cáo',
        required=True,
        readonly=True,
    )

    ngay_tao_bao_cao = fields.Datetime(
        string='Ngày tạo báo cáo',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
    )

    du_an_cha = fields.Many2one('sonha.du.an.bao.cao', string="Dự án cha", compute='get_du_an_cha', index=True, store=True, ondelete='set null',)
    du_an_con = fields.Many2one('sonha.du.an.bao.cao', string="Dự án con", compute='get_du_an_con', index=True, store=True, ondelete='set null',)

    @api.depends('in_dam', 'du_an_con_id')
    def get_du_an_cha(self):
        for r in self:
            if r.in_dam == 1:
                r.du_an_cha = r.id
            elif r.in_dam == 2:
                r.du_an_cha = r.du_an_con_id
            elif r.in_dam == 99:
                number = self.search([('id', '=', r.du_an_con_id)])
                r.du_an_cha = number.du_an_cha.id

    @api.depends('in_dam', 'du_an_con_id')
    def get_du_an_con(self):
        for r in self:
            if r.in_dam == 1:
                r.du_an_con = None
            elif r.in_dam == 2:
                r.du_an_con = r.id
            elif r.in_dam == 99:
                r.du_an_con = r.du_an_con_id




    @staticmethod
    def _find_child_project_id(values, current_index):
        total = len(values)
        for index in range(current_index + 1, total):
            next_value = values[index]
            next_level = next_value.get('in_dam')

            # Gặp dự án cha mới
            if next_level == 1:
                break

            # Gặp dự án con mới
            if next_level == 2:
                break

            # Nhiệm vụ
            if next_level == 99:
                child_project_id = next_value.get('du_an_con_id')
                if child_project_id:
                    return child_project_id

        return False

    @api.model
    def generate_from_function(self, tu_ngay, den_ngay, du_an_cha_id=False):
        if not tu_ngay or not den_ngay:
            raise ValidationError(_("Bạn phải nhập từ ngày và đến ngày."))
        start_date = fields.Date.to_date(tu_ngay)
        end_date = fields.Date.to_date(den_ngay)
        if start_date > end_date:
            raise ValidationError(
                _("Từ ngày không được lớn hơn đến ngày.")
            )
        query_params = (
            start_date.strftime('%d/%m/%Y'),
            end_date.strftime('%d/%m/%Y'),
            du_an_cha_id or None,
        )

        query = """
            SELECT *
            FROM public.fn_bao_cao_du_an(%s, %s, %s)
        """

        self.env.cr.execute(query,query_params)
        rows = self.env.cr.dictfetchall()
        generated_at = fields.Datetime.now()
        project_model = self.env['project.project']
        project_name = _("Tất cả dự án")
        if du_an_cha_id:
            project = project_model.browse(du_an_cha_id)
            if project.exists():
                project_name = project.name

        values = []
        for index, row in enumerate(rows, start=1):
            values.append({
                'name': (row.get('noi_dung_cv_con') or _('%(project)s - dòng %(line)s') % {
                            'project': project_name,
                            'line': index,
                        }
                ),
                'tu_ngay': tu_ngay,
                'den_ngay': den_ngay,
                'du_an_cha_id': du_an_cha_id or False,
                'stt': index,
                'noi_dung_cv_con': row.get('noi_dung_cv_con'),
                'ngay_bat_dau': row.get('ngay_bat_dau'),
                'ngay_ket_thuc': row.get('ngay_ket_thuc'),
                'ngay_hoan_thanh': row.get('ngay_hoan_thanh'),
                'ten_trang_thai': row.get('ten_trang_thai'),
                'tinh_trang_han': row.get('tinh_trang_han'),
                'pt_cv': row.get('pt_cv') or 0,
                'so_ngay_qua_han': row.get('so_ngay_qua_han') or 0,
                'ns_lam': row.get('ns_lam'),
                'in_dam': row.get('in_dam') or 0,
                'du_an_con_id': row.get('du_an_con_id') or False,
                'du_lieu': json.dumps(
                    row,
                    ensure_ascii=False,
                    default=str,
                    sort_keys=True
                ),

                'ngay_tao_bao_cao': generated_at,
            })
        created_records = self.browse()
        current_parent_group_id = False
        current_parent_group_name = False
        current_child_group_id = False
        current_child_group_name = False
        current_child_record = self.browse()

        for index, value in enumerate(values):
            level = value.get('in_dam')
            if level == 1:
                parent_project_id = value.get('du_an_con_id') or False
                current_parent_group_id = parent_project_id
                current_child_group_id = False
                current_child_group_name = False
                current_child_record = self.browse()
                current_parent_group_name = False
                if parent_project_id:
                    parent_project = project_model.browse(parent_project_id)
                    if parent_project.exists():
                        current_parent_group_name = parent_project.name
                    else:
                        current_parent_group_name = 'Dự án %s' % parent_project_id
                value.update({
                    'parent_group_id': current_parent_group_id,
                    'parent_group_name': current_parent_group_name,
                    'child_group_id': False,
                    'child_group_name': False,
                })
                record = self.create(value)
                created_records |= record
            elif level == 2:
                child_project_id = self._find_child_project_id(values, index)
                current_child_group_id = child_project_id or False
                current_child_group_name = False
                if child_project_id:
                    child_project = project_model.browse(child_project_id)
                    if child_project.exists():
                        current_child_group_name = child_project.name
                    else:
                        current_child_group_name = 'Dự án %s' % child_project_id
                value['parent_group_id'] = current_parent_group_id or False
                value['parent_group_name'] = current_parent_group_name or False
                value['child_group_id'] = current_child_group_id or False
                value['child_group_name'] = current_child_group_name or False
                record = self.create(value)
                current_child_record = record
                created_records |= record
            elif level == 99:
                child_project_id = value.get('du_an_con_id') or False
                if child_project_id:
                    current_child_group_id = child_project_id
                    child_project = project_model.browse(child_project_id)
                    if child_project.exists():
                        current_child_group_name = child_project.name
                    else:
                        current_child_group_name = 'Dự án %s' % child_project_id
                    if current_child_record and current_child_record.exists():
                        current_child_record.write({
                            'child_group_id': current_child_group_id,
                            'child_group_name': current_child_group_name,
                        })

                value['parent_group_id'] = current_parent_group_id or False
                value['parent_group_name'] = current_parent_group_name or False
                value['child_group_id'] = current_child_group_id or False
                value['child_group_name'] = current_child_group_name or False
                record = self.create(value)
                created_records |= record
            else:
                value['parent_group_id'] = False
                value['parent_group_name'] = False
                value['child_group_id'] = False
                value['child_group_name'] = False
                record = self.create(value)
                created_records |= record
        return created_records

    def action_open_generate_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạo báo cáo dự án'),
            'res_model': 'sonha.du.an.bao.cao.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
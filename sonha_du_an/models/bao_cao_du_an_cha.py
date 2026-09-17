import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BaoCaoDuAnCha(models.Model):
    _name = 'sonha.du.an.bao.cao.cha'
    _description = 'Báo cáo dự án'
    _table = 'bao_cao_cha'

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

    du_an_cha = fields.Many2one('sonha.du.an.bao.cao.cha', string="Dự án cha", index=True, store=True, ondelete='set null',)
    du_an_con = fields.Many2one('sonha.du.an.bao.cao.cha', string="Dự án con", index=True, store=True, ondelete='set null',)

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
            raise ValidationError(
                _("Bạn phải nhập từ ngày và đến ngày.")
            )

        start_date = fields.Date.to_date(tu_ngay)
        end_date = fields.Date.to_date(den_ngay)

        if start_date > end_date:
            raise ValidationError(
                _("Từ ngày không được lớn hơn đến ngày.")
            )

        user_id = self.env.user.id
        if self.env.user.has_group('sonha_du_an.group_admin_du_an'):
            id_admin = 1
        else:
            id_admin = 0

        query = """
            SELECT *
            FROM public.fn_bao_cao_du_an_cha(%s, %s, %s, %s, %s)
        """

        self.env.cr.execute(
            query,
            (
                start_date.strftime('%d/%m/%Y'),
                end_date.strftime('%d/%m/%Y'),
                du_an_cha_id or None,
                str(user_id),
                id_admin,
            )
        )

        rows = self.env.cr.dictfetchall()

        generated_at = fields.Datetime.now()
        project_model = self.env['project.project']

        # ==========================================================
        # Tên dự án
        # ==========================================================
        project_name = _("Tất cả dự án")

        if du_an_cha_id:
            project = project_model.browse(du_an_cha_id)
            if project.exists():
                project_name = project.name

        values = []

        for index, row in enumerate(rows, start=1):
            values.append({
                'name': (
                        row.get('noi_dung_cv_con')
                        or _('%(project)s - dòng %(line)s') % {
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
                    sort_keys=True,
                ),
                'ngay_tao_bao_cao': generated_at,
            })

        # ==========================================================
        # Tạo record báo cáo
        # ==========================================================
        created_records = self.browse()
        row_records = []

        current_parent_group_id = False
        current_parent_group_name = False
        current_child_group_id = False
        current_child_group_name = False
        current_child_record = self.browse()

        for index, value in enumerate(values):
            level = value.get('in_dam')

            # ------------------------------------------------------
            # Dự án cha
            # ------------------------------------------------------
            if level == 1:
                parent_project_id = value.get('du_an_con_id') or False

                current_parent_group_id = parent_project_id
                current_child_group_id = False
                current_child_group_name = False
                current_child_record = self.browse()

                current_parent_group_name = False

                if parent_project_id:
                    parent_project = project_model.browse(
                        parent_project_id
                    )

                    current_parent_group_name = (
                        parent_project.name
                        if parent_project.exists()
                        else 'Dự án %s' % parent_project_id
                    )

                value.update({
                    'parent_group_id': current_parent_group_id,
                    'parent_group_name': current_parent_group_name,
                    'child_group_id': False,
                    'child_group_name': False,
                })

            # ------------------------------------------------------
            # Dự án con
            # ------------------------------------------------------
            elif level == 2:
                child_project_id = self._find_child_project_id(
                    values,
                    index,
                )

                current_child_group_id = child_project_id or False

                current_child_group_name = False

                if child_project_id:
                    child_project = project_model.browse(
                        child_project_id
                    )

                    current_child_group_name = (
                        child_project.name
                        if child_project.exists()
                        else 'Dự án %s' % child_project_id
                    )

                value.update({
                    'parent_group_id': (
                            current_parent_group_id or False
                    ),
                    'parent_group_name': (
                            current_parent_group_name or False
                    ),
                    'child_group_id': (
                            current_child_group_id or False
                    ),
                    'child_group_name': (
                            current_child_group_name or False
                    ),
                })

            # ------------------------------------------------------
            # Nhiệm vụ
            # ------------------------------------------------------
            elif level == 99:
                child_project_id = value.get(
                    'du_an_con_id'
                ) or False

                if child_project_id:
                    current_child_group_id = child_project_id

                    child_project = project_model.browse(
                        child_project_id
                    )

                    current_child_group_name = (
                        child_project.name
                        if child_project.exists()
                        else 'Dự án %s' % child_project_id
                    )

                value.update({
                    'parent_group_id': (
                            current_parent_group_id or False
                    ),
                    'parent_group_name': (
                            current_parent_group_name or False
                    ),
                    'child_group_id': (
                            current_child_group_id or False
                    ),
                    'child_group_name': (
                            current_child_group_name or False
                    ),
                })

            # ------------------------------------------------------
            # Các loại khác
            # ------------------------------------------------------
            else:
                value.update({
                    'parent_group_id': False,
                    'parent_group_name': False,
                    'child_group_id': False,
                    'child_group_name': False,
                })

            # Tạo record và lưu lại để xử lý quan hệ sau
            record = self.create(value)

            row_records.append(record)
            created_records |= record

            if level == 2:
                current_child_record = record

            elif level == 99 and current_child_record:
                current_child_record.write({
                    'child_group_id': current_child_group_id,
                    'child_group_name': current_child_group_name,
                })

        # ==========================================================
        # Thiết lập du_an_cha / du_an_con
        # Sau khi tất cả record đã được tạo
        # ==========================================================
        current_parent_record = self.browse()
        child_report_map = {}

        # ----------------------------------------------------------
        # Dự án cha và dự án con
        # ----------------------------------------------------------
        for index, value in enumerate(values):
            record = row_records[index]
            level = value.get('in_dam')

            if level == 1:
                current_parent_record = record

                record.write({
                    'du_an_cha': record.id,
                    'du_an_con': False,
                })

            elif level == 2:
                child_project_id = self._find_child_project_id(
                    values,
                    index,
                )

                record.write({
                    'du_an_cha': (
                        current_parent_record.id
                        if current_parent_record
                        else False
                    ),
                    'du_an_con': record.id,
                })

                if child_project_id:
                    child_report_map[child_project_id] = record

        current_parent_record = self.browse()

        for index, value in enumerate(values):
            record = row_records[index]
            level = value.get('in_dam')

            if level == 1:
                current_parent_record = record

            elif level == 99:
                child_project_id = value.get(
                    'du_an_con_id'
                ) or False

                child_record = child_report_map.get(
                    child_project_id
                )

                record.write({
                    'du_an_cha': current_parent_record.id if current_parent_record else False,
                    'du_an_con': child_record.id if child_record else False,
                })
        return created_records

    def action_open_generate_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạo báo cáo dự án'),
            'res_model': 'sonha.du.an.cha.bao.cao.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta, date
from odoo.exceptions import UserError, ValidationError


class RelDonTu(models.Model):
    _name = 'rel.don.tu'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", store=True)
    date = fields.Date("Ngày", store=True)
    leave_more = fields.Float("Phép thêm", store=True)
    leave = fields.Float("Số ngày nghỉ phép", store=True)
    type_leave = fields.Many2one('config.word.slip', string="Loại đơn", store=True)
    key_type_leave = fields.Char(related='type_leave.key', string="Key loại đơn", store=True)
    key = fields.Many2one('word.slip', string="Key ngày", store=True)
    key_char = fields.Char(string="Key", store=True)

    key_form = fields.Many2one('form.word.slip', string="Key", store=True)
    key_form_char = fields.Char(string="Key", store=True)

    is_temp = fields.Boolean(string="Check", store=True)

    status = fields.Selection([
        ('sent', 'Nháp'),
        ('draft', 'Chờ duyệt'),
        ('confirm', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', store=True)

    def phan_ra_all(self):
        self.phan_ra_don_tu()
        self.phan_ra_lam_them()
        self.phan_ra_ca()

    def phan_ra_ca(self):
        self.env['rel.ca'].sudo().search([]).unlink()
        query = """INSERT INTO rel_ca(employee_id, department_id, company_id, date, shift_id, key_form, type)
                    SELECT
                        rel.register_work_id AS employee_id,
                        rw.department_id AS department_id,
                        rw.company_id AS company_id,
                        gs.day::date AS date,
                        rw.shift AS shift_id,
                        rw.id AS key_form,
                        'dang_ky_ca' AS type
                    FROM register_work rw
                    LEFT JOIN register_work_rel rel 
                        ON rel.register_work = rw.id
                    JOIN generate_series(rw.start_date::date, rw.end_date::date, '1 day') AS gs(day) ON TRUE
                    WHERE rw.start_date IS NOT NULL
                    AND rw.end_date IS NOT NULL
                    AND rel.register_work_id IS NOT NULL;"""
        self.env.cr.execute(query, ())
        query = """INSERT INTO rel_ca(employee_id, department_id, company_id, date, shift_id, key, key_form, type)
                    SELECT
                        rs.employee_id AS employee_id,
                        rs.department_id AS department_id,
                        rsr.company_id AS company_id,
                        rsr.date::date AS date,
                        rsr.shift AS shift_id,
                        rsr.id AS key,
                        rsr.register_shift AS key_form,
                        'doi_ca' AS type
                    FROM register_shift_rel rsr
                    JOIN register_shift rs ON rsr.register_shift = rs.id
                    WHERE rsr.shift IS NOT NULL
                    AND rsr.date IS NOT NULL
                    AND rsr.company_id IS NOT NULL;"""
        self.env.cr.execute(query, ())

    def phan_ra_lam_them(self):
        self.env['rel.lam.them'].sudo().search([]).unlink()
        query = """INSERT INTO rel_lam_them(
                        employee_id, department_id, date, start_time, end_time, status, type, time_amount, key, key_form, create_uid, create_date
                    )
                    SELECT
                        CASE
                            WHEN rov.type = 'one' THEN rov.employee_id
                            ELSE rel.overtime_rel
                        END AS emp_id,
                        rov.department_id AS department_id,
                        ovr.date::date AS date,
                        ovr.start_time AS start_time,
                        ovr.end_time AS end_time,
                        CASE
                            WHEN rov.type = 'one' THEN rov.status
                            ELSE rov.status_lv2
                        END AS status,
                        rov.type AS type,
                        ovr.end_time - ovr.start_time AS time_amount,
                        ovr.id AS key,
                        ovr.overtime_id AS key_form,
                        1 AS create_uid,
                        NOW() AS create_date
                    FROM overtime_rel ovr
                    JOIN register_overtime_update rov ON ovr.overtime_id = rov.id
                    LEFT JOIN ir_employee_overtime_rel rel 
                        ON rel.employee_overtime_rel = rov.id
                        AND rov.type != 'one'
                    WHERE ovr.date IS NOT NULL
                    AND ovr.start_time > 0
                    AND ovr.end_time > 0;"""
        self.env.cr.execute(query, ())

    def phan_ra_don_tu(self):
        self.env['rel.don.tu'].sudo().search([]).unlink()
        query = """INSERT INTO rel_don_tu(
                        employee_id, date, leave, type_leave, status, key_type_leave, key, key_form, create_uid, create_date
                    )
                        SELECT
                            CASE
                                WHEN fws.regis_type = 'one' THEN fws.employee_id
                                ELSE rel.slip_rel
                            END AS emp_id,
                            gs.day::date AS date,
                            CASE 
                                WHEN cfw.key = 'NP' THEN  
                                    CASE 
                                        WHEN ws.start_time = ws.end_time THEN 0.5 
                                        ELSE 1 
                                    END
                                ELSE 0
                            END AS leave,
                            cfw.id AS type_leave,
                            CASE
                                WHEN fws.check_level = true THEN fws.status_lv1
                                ELSE fws.status_lv2
                            END AS status,
                            cfw.key AS key_type_leave,
                            ws.id AS key,
                            ws.word_slip AS key_form,
                            1 AS create_uid,
                            NOW() AS create_date
                        FROM word_slip ws
                        JOIN form_word_slip fws ON ws.word_slip = fws.id
                        LEFT JOIN ir_employee_slip_rel rel 
                            ON rel.employee_slip_rel = fws.id
                            AND fws.regis_type = 'many'
                        LEFT JOIN config_word_slip cfw on fws.type = cfw.id
                        JOIN generate_series(ws.from_date::date, ws.to_date::date, '1 day') AS gs(day) ON TRUE
                        WHERE ws.from_date IS NOT NULL
                        AND ws.to_date IS NOT NULL;"""
        self.env.cr.execute(query, ())

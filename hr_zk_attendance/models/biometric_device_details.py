# -*- coding: utf-8 -*-
import datetime
import logging
import pytz
from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)
try:
    from zk import ZK, const
except ImportError:
    _logger.error("Please Install pyzk library.")


class BiometricDeviceDetails(models.Model):
    _name = 'biometric.device.details'
    _description = 'Biometric Device Details'

    name = fields.Char(string='Name', required=True, help='Record Name')
    device_ip = fields.Char(string='Device IP', required=True,
                            help='The IP address of the Device')
    port_number = fields.Integer(string='Port Number', required=True,
                                 help="The Port Number of the Device")
    address_id = fields.Many2one('res.partner', string='Working Address',
                                 help='Working address of the partner')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda
                                     self: self.env.user.company_id.id,
                                 help='Current Company')

    def device_connect(self, zk):
        try:
            conn = zk.connect()
            return conn
        except Exception:
            return False

    def action_test_connection(self):
        zk = ZK(self.device_ip, port=self.port_number, timeout=30,
                password=False, ommit_ping=False)
        try:
            if zk.connect():
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': 'Successfully Connected',
                        'type': 'success',
                        'sticky': False
                    }
                }
        except Exception as error:
            raise ValidationError(f'{error}')

    def action_clear_attendance(self):
        for info in self:
            try:
                machine_ip = info.device_ip
                zk_port = info.port_number
                try:
                    # Connecting with the device
                    zk = ZK(machine_ip, port=zk_port, timeout=30,
                            password=0, force_udp=False, ommit_ping=False)
                except NameError:
                    raise UserError(_(
                        "Please install it with 'pip3 install pyzk'."))
                conn = self.device_connect(zk)
                if conn:
                    conn.enable_device()
                    clear_data = zk.get_attendance()
                    if clear_data:
                        # Clearing data in the device
                        conn.clear_attendance()
                        # Clearing data from attendance log
                        self._cr.execute(
                            """delete from zk_machine_attendance""")
                        conn.disconnect()
                    else:
                        raise UserError(
                            _('Unable to clear Attendance log.Are you sure '
                              'attendance log is not empty.'))
                else:
                    raise UserError(
                        _('Unable to connect to Attendance Device. Please use '
                          'Test Connection button to verify.'))
            except Exception as error:
                raise ValidationError(f'{error}')

    def action_download_attendance(self):
        _logger.info("++++++++++++Cron Executed++++++++++++++++++++++")
        master_attendance = self.env['master.data.attendance']
        hr_employee = self.env['hr.employee']
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            try:
                zk = ZK(machine_ip, port=zk_port, timeout=None, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                conn.disable_device()
                users = conn.get_users()
                attendances = conn.get_attendance()
                if attendances:
                    # Thu thập dữ liệu chấm công theo nhân viên và ngày trong khoảng thời gian từ tháng 6 năm 2024 đến hiện tại
                    for each in attendances:
                        atten_time = each.timestamp
                        current_date = datetime.now()
                        current_year = current_date.year
                        current_month = current_date.month
                        if (atten_time.year == current_year and atten_time.month == current_month) or \
                                (atten_time.year == current_year and atten_time.month == current_month - 1) or \
                                (current_month == 1 and atten_time.year == current_year - 1 and atten_time.month == 12):
                            user_key = each.user_id

                            # Trừ 7 giờ từ thời gian chấm công
                            atten_time_adjusted = atten_time - timedelta(hours=7)

                            # Tìm hoặc tạo nhân viên
                            employee = hr_employee.sudo().search([('device_id_num', '=', user_key)])

                            # Kiểm tra xem dữ liệu chấm công đã tồn tại chưa
                            existing_attendance = master_attendance.sudo().search([
                                ('employee_id', '=', employee.id),
                                ('attendance_time', '=', fields.Datetime.to_string(atten_time_adjusted))
                            ])

                            # Lưu dữ liệu vào master.data.attendance nếu chưa tồn tại
                            if employee and not existing_attendance:
                                master_attendance.sudo().create({
                                    'employee_id': employee.id,
                                    'attendance_time': fields.Datetime.to_string(atten_time_adjusted)
                                })
                    conn.disconnect()
                    return True
                else:
                    raise UserError(_('Unable to get the attendance log, please try again later.'))
            else:
                raise UserError(_('Unable to connect, please check the parameters and network connections.'))

    def download_attendance(self):
        _logger.info("++++++++++++Cron Executed++++++++++++++++++++++")
        master_attendance = self.env['master.data.attendance']
        hr_employee = self.env['hr.employee']
        device_ids = self.sudo().search([])
        for info in device_ids:
            machine_ip = info.device_ip
            zk_port = info.port_number
            try:
                zk = ZK(machine_ip, port=zk_port, timeout=None, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                conn.disable_device()
                today = datetime.today() + timedelta(days=1)
                first_day_last_month = (today - timedelta(days=5))
                attendances = conn.get_attendance()
                attendances = [
                    att for att in attendances
                    if first_day_last_month <= att.timestamp < today
                ]
                if attendances:
                    # Thu thập dữ liệu chấm công theo nhân viên và ngày trong khoảng thời gian từ tháng 6 năm 2024 đến hiện tại
                    for each in attendances:
                        atten_time = each.timestamp
                        user_key = each.user_id

                        # Trừ 7 giờ từ thời gian chấm công
                        atten_time_adjusted = atten_time - timedelta(hours=7)

                        # Tìm hoặc tạo nhân viên
                        employee = hr_employee.sudo().search([('device_id_num', '=', user_key)])

                        # Kiểm tra xem dữ liệu chấm công đã tồn tại chưa
                        existing_attendance = master_attendance.sudo().search([
                            ('employee_id', '=', employee.id),
                            ('attendance_time', '=', fields.Datetime.to_string(atten_time_adjusted))
                        ])

                        # Lưu dữ liệu vào master.data.attendance nếu chưa tồn tại
                        if employee and not existing_attendance:
                            master_attendance.sudo().create({
                                'employee_id': employee.id,
                                'attendance_time': fields.Datetime.to_string(atten_time_adjusted)
                            })
                    conn.disconnect()
                    return True
                else:
                    continue
            else:
                continue


    def action_restart_device(self):
        """For restarting the device"""
        zk = ZK(self.device_ip, port=self.port_number, timeout=15,
                password=0,
                force_udp=False, ommit_ping=False)
        self.device_connect(zk).restart()

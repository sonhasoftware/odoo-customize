# -*- coding: utf-8 -*-
import re
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class TopicChatbotTopic(models.Model):
    _name = 'topic_chatbot.topic'
    _description = 'Chatbot Topic'
    _order = 'name'

    name = fields.Char(string='Topic Name', required=True)
    description = fields.Text(string='Description')
    is_public = fields.Boolean(
        string='Is Public', 
        default=False,
        help="If checked, this topic is visible to all users. Only administrators can set this."
    )
    is_db_query = fields.Boolean(
        string='Hỏi dữ liệu DB (Odoo)',
        default=False,
        help="Nếu bật, chủ đề này sẽ được phép truy vấn dữ liệu trực tiếp trong DB Odoo."
    )
    is_mssql_query = fields.Boolean(
        string='Hỏi dữ liệu SQL Server',
        default=False,
        help="Nếu bật, chủ đề này sẽ được phép truy vấn dữ liệu từ cơ sở dữ liệu Microsoft SQL Server."
    )
    mssql_allowed_tables = fields.Text(string="Danh sách Table/View cho phép", help="Mỗi tên bảng trên 1 dòng hoặc cách nhau bởi dấu phẩy.")
    mssql_connection_id = fields.Many2one('topic_chatbot.mssql_connection', string='SQL Connection', help='Chọn cấu hình kết nối riêng. Nếu bỏ trống sẽ dùng cấu hình mặc định trong Settings.')
    mssql_schema_info = fields.Text(string='Schema Info', readonly=True, help='Cấu trúc bảng được tự động đồng bộ (chỉ đọc).')
    is_admin = fields.Boolean(compute='_compute_is_admin')

    def _compute_is_admin(self):
        is_admin = self.env.user.has_group('topic_chatbot.group_topic_chatbot_admin')
        for rec in self:
            rec.is_admin = is_admin

    document_ids = fields.One2many(
        'topic_chatbot.document', 
        'topic_id', 
        string='Documents'
    )
    chunk_ids = fields.One2many(
        'topic_chatbot.chunk', 
        'topic_id', 
        string='Text Chunks'
    )

    @api.model_create_multi
    def create(self, vals_list):
        is_admin = self.env.user.has_group('topic_chatbot.group_topic_chatbot_admin')
        for vals in vals_list:
            if vals.get('is_public') and not is_admin:
                raise ValidationError("Only administrators can create public topics.")
            # UPGRADE #5: Phân quyền tạo MSSQL topic – chỉ admin mới được bật is_mssql_query
            if vals.get('is_mssql_query') and not is_admin:
                raise ValidationError("Chỉ Administrator mới có thể tạo chủ đề với tính năng Hỏi SQL Server.")
        return super().create(vals_list)

    def write(self, vals):
        is_admin = self.env.user.has_group('topic_chatbot.group_topic_chatbot_admin')
        if 'is_public' in vals and vals.get('is_public') and not is_admin:
            raise ValidationError("Only administrators can make topics public.")
        # UPGRADE #5: Phân quyền chỉnh sửa MSSQL topic – chỉ admin mới được bật is_mssql_query
        if 'is_mssql_query' in vals and vals.get('is_mssql_query') and not is_admin:
            raise ValidationError("Chỉ Administrator mới có thể bật tính năng Hỏi SQL Server cho chủ đề này.")
        return super().write(vals)

    def action_process_all_documents(self):
        """Manually trigger document processing for all draft/error/partial documents in this topic."""
        all_draft_docs = self.env['topic_chatbot.document']
        for topic in self:
            all_draft_docs |= topic.document_ids.filtered(lambda d: d.state in ('draft', 'error', 'partial'))
        if all_draft_docs:
            return all_draft_docs.action_process_document()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Xử lý tài liệu',
                'message': 'Không có tài liệu nào ở trạng thái chờ xử lý.',
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_reprocess_all_documents(self):
        """Force reprocess ALL documents under this topic to upgrade them to Parent-Child chunking."""
        all_docs = self.env['topic_chatbot.document']
        for topic in self:
            all_docs |= topic.document_ids.filtered(lambda d: d.state != 'processing')
        if all_docs:
            all_docs.write({
                'state': 'draft',
                'error_message': False,
                'text_content': False,
                'content_length': 0,
                'word_count': 0,
                'processing_time': 0.0
            })
            return all_docs.action_process_document()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Nâng cấp tất cả tài liệu',
                'message': 'Không có tài liệu nào trong chủ đề này.',
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_sync_mssql_schema(self):
        """Lấy cấu trúc các bảng từ SQL Server và lưu vào mssql_schema_info."""
        self.ensure_one()
        if not self.is_mssql_query or not self.mssql_allowed_tables:
            return

        from odoo.exceptions import UserError
        from . import crypto_utils

        # Parse tables
        allowed_tables = set()
        for table in re.split(r'[\n,;]+', self.mssql_allowed_tables or ''):
            table_name = table.strip().split()[0].strip('[]') if table.strip() else ''
            if table_name:
                allowed_tables.add(table_name)
        
        if not allowed_tables:
            raise UserError("Không tìm thấy tên bảng nào hợp lệ trong danh sách cho phép.")

        # Get connection params
        if self.mssql_connection_id:
            conn_record = self.mssql_connection_id
            host = conn_record.host or 'localhost'
            port = conn_record.port or '1433'
            db = conn_record.database or ''
            user = conn_record.user or ''
            raw_pw = conn_record.password or ''
            password = crypto_utils.decrypt_value(self.env, raw_pw) if crypto_utils.is_encrypted(raw_pw) else raw_pw
            driver = conn_record.driver or 'ODBC Driver 17 for SQL Server'
        else:
            params = self.env['ir.config_parameter'].sudo()
            if not params.get_param('topic_chatbot.mssql_enabled', 'False').lower() in ('true', '1'):
                raise UserError("Tính năng kết nối SQL Server chưa được bật trong cấu hình chung.")
            host = params.get_param('topic_chatbot.mssql_host') or 'localhost'
            port = params.get_param('topic_chatbot.mssql_port') or '1433'
            db = params.get_param('topic_chatbot.mssql_db') or ''
            user = params.get_param('topic_chatbot.mssql_user') or ''
            raw_pw = params.get_param('topic_chatbot.mssql_password') or ''
            password = crypto_utils.decrypt_value(self.env, raw_pw)
            driver = params.get_param('topic_chatbot.mssql_driver') or 'ODBC Driver 17 for SQL Server'

        if not db:
            raise UserError("Không có Database Name trong cấu hình kết nối.")

        try:
            import pyodbc
            if '\\' in host or '/' in host:
                server_str = host.replace('/', '\\')
            else:
                port_str = f",{port}" if port and str(port).strip() not in ("1433", "") else ""
                server_str = f"{host}{port_str}"

            auth_str = f"UID={user};PWD={password};" if user else "Trusted_Connection=yes;"
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={server_str};DATABASE={db};"
                f"{auth_str}TrustServerCertificate=yes;Connection Timeout=10;"
            )
            conn = pyodbc.connect(conn_str, timeout=10)
            cursor = conn.cursor()

            schema_info = []
            for t in allowed_tables:
                # Handle schema if present (e.g., dbo.TableName)
                parts = t.split('.')
                t_name = parts[-1]
                t_schema = parts[-2] if len(parts) > 1 else None

                query = "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?"
                params_tuple = (t_name,)
                if t_schema:
                    query += " AND TABLE_SCHEMA = ?"
                    params_tuple = (t_name, t_schema)

                cursor.execute(query, params_tuple)
                columns = cursor.fetchall()
                if columns:
                    col_strs = [f"{col[0]} ({col[1]})" for col in columns]
                    schema_info.append(f"Table '{t}': " + ", ".join(col_strs))
                else:
                    schema_info.append(f"Table '{t}': (Không tìm thấy bảng hoặc không có quyền xem cấu trúc)")

            conn.close()
            self.mssql_schema_info = "\n\n".join(schema_info)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Thành công',
                    'message': 'Đã đồng bộ xong cấu trúc bảng!',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except ImportError:
            raise UserError("Chưa cài đặt thư viện pyodbc.")
        except Exception as e:
            raise UserError(f"Lỗi khi đồng bộ cấu trúc: {str(e)}")

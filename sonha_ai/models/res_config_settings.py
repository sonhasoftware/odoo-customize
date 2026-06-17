# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sonha_ai_provider = fields.Selection([
        ('ollama', 'Ollama (On-Premise / Local)'),
        ('openai', 'OpenAI (ChatGPT)'),
        ('gemini', 'Google Gemini'),
    ], string='AI Provider', config_parameter='sonha_ai.provider', default='ollama')

    sonha_ai_knowledge_attachment_ids = fields.Many2many(
        related='company_id.sonha_ai_knowledge_attachment_ids', 
        readonly=False, 
        string='Knowledge Base Files'
    )

    sonha_ai_openai_api_key = fields.Char(
        string='OpenAI API Key', 
        config_parameter='sonha_ai.openai_api_key',
        help="Get it from platform.openai.com"
    )
    
    sonha_ai_openai_model = fields.Selection([
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4o-mini', 'GPT-4o-mini')
    ], string='OpenAI Model', config_parameter='sonha_ai.openai_model', default='gpt-4o-mini')

    sonha_ai_gemini_api_key = fields.Char(
        string='Gemini API Key', 
        config_parameter='sonha_ai.gemini_api_key',
        help="Get it from aistudio.google.com"
    )
    
    sonha_ai_gemini_model = fields.Selection([
        # Current Models (2026)
        ('gemini-3.5-flash', 'Gemini 3.5 Flash'),
        ('gemini-3.1-pro-preview', 'Gemini 3.1 Pro (Preview)'),
        ('gemini-2.5-pro', 'Gemini 2.5 Pro'),
        ('gemini-2.5-flash', 'Gemini 2.5 Flash'),
        ('gemini-pro-latest', 'Gemini Pro Latest'),
        ('gemini-flash-latest', 'Gemini Flash Latest'),
        
        # Legacy Models (Keep to prevent DB ValueError)
        ('gemini-1.5-flash', 'Gemini 1.5 Flash (Legacy)'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro (Legacy)'),
        ('gemini-1.5-flash-latest', 'Gemini 1.5 Flash Latest (Legacy)'),
        ('gemini-1.5-pro-latest', 'Gemini 1.5 Pro Latest (Legacy)'),
        ('gemini-pro', 'Gemini 1.0 Pro (Legacy)'),
    ], string='Gemini Model', config_parameter='sonha_ai.gemini_model', default='gemini-3.5-flash')

    # Ollama Settings
    sonha_ai_ollama_url = fields.Char(
        string='Ollama Server URL', 
        config_parameter='sonha_ai.ollama_url',
        default='http://localhost:11434',
        help="Ví dụ: http://localhost:11434"
    )
    sonha_ai_ollama_model = fields.Char(
        string='Ollama Chat Model', 
        config_parameter='sonha_ai.ollama_model',
        default='qwen2.5:3b',
        help="Ví dụ: qwen2.5:3b hoặc llama3"
    )
    sonha_ai_ollama_embed_model = fields.Char(
        string='Ollama Embedding Model', 
        config_parameter='sonha_ai.ollama_embed_model',
        default='nomic-embed-text',
        help="Model chuyên dùng để tạo Vector"
    )

    # SQL Server Settings for Vector DB
    sonha_ai_sql_server = fields.Char(
        string='SQL Server Name',
        config_parameter='sonha_ai.sql_server',
        default='LAPTOP-BP99BUKE\\SQLEXPRESS'
    )
    sonha_ai_sql_database = fields.Char(
        string='SQL Database Name',
        config_parameter='sonha_ai.sql_database',
        default='OdooAI_Vector'
    )
    sonha_ai_sql_user = fields.Char(
        string='SQL Username',
        config_parameter='sonha_ai.sql_user',
        help="Bỏ trống nếu dùng Windows Authentication"
    )
    sonha_ai_sql_password = fields.Char(
        string='SQL Password',
        config_parameter='sonha_ai.sql_password'
    )

    def action_sync_vector_db(self):
        """Action để đồng bộ lại dữ liệu kiến thức vào SQL Server"""
        import threading
        import odoo
        from odoo import api
        
        db_name = self.env.cr.dbname
        def sync_in_bg():
            with odoo.registry(db_name).cursor() as cr:
                env = api.Environment(cr, odoo.SUPERUSER_ID, {})
                env['sonha.ai.bot']._sync_knowledge_to_sql()

        thread = threading.Thread(target=sync_in_bg)
        thread.start()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đang tiến hành đồng bộ',
                'message': 'Hệ thống đang băm nhỏ file và đẩy lên SQL Server ngầm. Vui lòng chờ 1-2 phút trước khi chat.',
                'sticky': False,
            }
        }

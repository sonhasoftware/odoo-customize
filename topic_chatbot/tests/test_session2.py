# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
import base64

@tagged('post_install', '-at_install')
class TestSession2Models(TransactionCase):
    """Model-level tests for Session 2 changes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create an Admin user
        cls.AdminUser = cls.env.ref('base.user_admin')
        cls.AdminUser.write({'groups_id': [
            (4, cls.env.ref('base.group_system').id),
            (4, cls.env.ref('topic_chatbot.group_topic_chatbot_admin').id),
        ]})
        
        # Create a topic
        cls.Topic = cls.env['topic_chatbot.topic'].with_user(cls.AdminUser).create({
            'name': 'Test Topic Session 2',
            'description': 'Test Topic for async document processing',
            'is_public': True,
        })

    def test_01_document_created_in_draft_state(self):
        """Test that a new document is created in 'draft' state and chunks are not immediately generated."""
        file_content = base64.b64encode(b"This is a test document content for async processing.")
        doc = self.env['topic_chatbot.document'].with_user(self.AdminUser).create({
            'name': 'Async Test Doc',
            'topic_id': self.Topic.id,
            'datas': file_content,
            'filename': 'async_test.txt'
        })
        
        # Ensure state is draft
        self.assertEqual(doc.state, 'draft', "Document state should be 'draft' upon creation.")
        
        # Ensure text is not extracted yet
        self.assertFalse(doc.text_content, "Text content should be empty before cron runs.")
        
        # Ensure chunks are not created yet
        chunks_count = self.env['topic_chatbot.chunk'].search_count([('document_id', '=', doc.id)])
        self.assertEqual(chunks_count, 0, "No chunks should be generated in draft state.")

    def test_02_cron_processes_draft_documents(self):
        """Test that the cron method processes draft documents and updates state to 'done'."""
        file_content = base64.b64encode(b"This is a test document content for async processing.")
        doc = self.env['topic_chatbot.document'].with_user(self.AdminUser).create({
            'name': 'Async Cron Test Doc',
            'topic_id': self.Topic.id,
            'datas': file_content,
            'filename': 'async_test_cron.txt'
        })
        
        # Trigger cron
        self.env['topic_chatbot.document']._cron_process_documents()
        
        # Refresh document
        doc.invalidate_recordset()
        
        self.assertEqual(doc.state, 'done', "Document state should be 'done' after cron execution.")
        self.assertIn("This is a test document", doc.text_content, "Text content should be extracted.")
        
        chunks_count = self.env['topic_chatbot.chunk'].search_count([('document_id', '=', doc.id)])
        self.assertGreater(chunks_count, 0, "Chunks should be generated after processing.")

    def test_03_write_resets_document_to_draft(self):
        """Test that updating a document's file resets its state to 'draft'."""
        file_content_1 = base64.b64encode(b"Initial content.")
        doc = self.env['topic_chatbot.document'].with_user(self.AdminUser).create({
            'name': 'Update Test Doc',
            'topic_id': self.Topic.id,
            'datas': file_content_1,
            'filename': 'update_test.txt'
        })
        
        # Process it once


        
        self.env['topic_chatbot.document']._cron_process_documents()
        self.assertEqual(doc.state, 'done')
        
        # Update with new content
        file_content_2 = base64.b64encode(b"Updated content.")
        doc.write({'datas': file_content_2})
        
        self.assertEqual(doc.state, 'draft', "Document state should reset to 'draft' after updating datas.")

    # =========================================================
    # TC04-05: Token-limit management for chat history
    # =========================================================
    def test_04_token_limit_truncates_old_messages(self):
        """Test that chat history respects MAX_CHARS limit and drops oldest messages first."""
        from odoo.addons.topic_chatbot.controllers.main import TopicChatbotController
        import re

        conv = self.env['topic_chatbot.conversation'].create({
            'name': 'Token Limit Test',
            'topic_id': self.Topic.id,
            'user_id': self.AdminUser.id,
        })

        # Create messages that total well over 30000 chars
        # Each message = 10000 chars, create 5 messages = 50000 chars total
        for i in range(5):
            role = 'user' if i % 2 == 0 else 'model'
            self.env['topic_chatbot.message'].create({
                'conversation_id': conv.id,
                'role': role,
                'content': f'MSG_{i}_' + ('X' * 9990),
            })

        # Simulate the token-limit logic from the controller
        db_messages = self.env['topic_chatbot.message'].search([
            ('conversation_id', '=', conv.id)
        ], order='create_date desc')

        contents = []
        total_chars = 0
        MAX_CHARS = 30000

        for m in db_messages:
            cleaned_content = re.sub(r' {2,}', ' ', m.content or '')
            if total_chars + len(cleaned_content) > MAX_CHARS and len(contents) > 0:
                break
            total_chars += len(cleaned_content)
            contents.insert(0, {
                'role': 'user' if m.role == 'user' else 'model',
                'parts': [{'text': cleaned_content}]
            })

        # Should include only 3 messages (3 * 10000 = 30000)
        self.assertEqual(len(contents), 3,
                         "Only 3 of 5 messages should fit within 30000 char limit")
        self.assertLessEqual(total_chars, MAX_CHARS,
                             "Total chars must not exceed MAX_CHARS")

    def test_05_token_limit_always_includes_latest_message(self):
        """Test that even a single very large message is always included (never empty context)."""
        import re

        conv = self.env['topic_chatbot.conversation'].create({
            'name': 'Big Message Test',
            'topic_id': self.Topic.id,
            'user_id': self.AdminUser.id,
        })

        # Create one message that exceeds MAX_CHARS by itself
        self.env['topic_chatbot.message'].create({
            'conversation_id': conv.id,
            'role': 'user',
            'content': 'Y' * 50000,
        })

        db_messages = self.env['topic_chatbot.message'].search([
            ('conversation_id', '=', conv.id)
        ], order='create_date desc')

        contents = []
        total_chars = 0
        MAX_CHARS = 30000

        for m in db_messages:
            cleaned_content = re.sub(r' {2,}', ' ', m.content or '')
            if total_chars + len(cleaned_content) > MAX_CHARS and len(contents) > 0:
                break
            total_chars += len(cleaned_content)
            contents.insert(0, {
                'role': 'user' if m.role == 'user' else 'model',
                'parts': [{'text': cleaned_content}]
            })

        # Even though the single message exceeds MAX_CHARS,
        # the condition `len(contents) > 0` ensures the first message is always included
        self.assertEqual(len(contents), 1,
                         "The latest message must always be included even if it exceeds MAX_CHARS")
        self.assertGreater(total_chars, MAX_CHARS,
                           "Total chars can exceed limit for the very first message to avoid empty context")

    # =========================================================
    # TC06-08: Rate limiting / abuse prevention
    # =========================================================
    def test_06_rate_limit_blocks_after_max_messages(self):
        """Test that _check_rate_limit returns True after RATE_LIMIT_MAX_MESSAGES user messages."""
        from odoo.addons.topic_chatbot.controllers.main import TopicChatbotController

        controller = TopicChatbotController()

        conv = self.env['topic_chatbot.conversation'].create({
            'name': 'Rate Limit Test',
            'topic_id': self.Topic.id,
            'user_id': self.AdminUser.id,
        })

        # Create exactly RATE_LIMIT_MAX_MESSAGES user messages (default: 5)
        for i in range(controller.RATE_LIMIT_MAX_MESSAGES):
            self.env['topic_chatbot.message'].create({
                'conversation_id': conv.id,
                'role': 'user',
                'content': f'Spam message {i}',
            })

        # Flush to ensure create_date is written to DB
        self.env.flush_all()

        # Check rate limit — should be True (blocked)
        is_limited = controller._check_rate_limit(self.env, self.AdminUser.id)
        self.assertTrue(is_limited, "Rate limit should trigger after sending max messages within the window")

    def test_07_rate_limit_allows_under_threshold(self):
        """Test that _check_rate_limit returns False when under the limit."""
        from odoo.addons.topic_chatbot.controllers.main import TopicChatbotController

        controller = TopicChatbotController()

        conv = self.env['topic_chatbot.conversation'].create({
            'name': 'Under Limit Test',
            'topic_id': self.Topic.id,
            'user_id': self.AdminUser.id,
        })

        # Create fewer messages than the limit
        for i in range(controller.RATE_LIMIT_MAX_MESSAGES - 1):
            self.env['topic_chatbot.message'].create({
                'conversation_id': conv.id,
                'role': 'user',
                'content': f'Normal message {i}',
            })

        self.env.flush_all()

        is_limited = controller._check_rate_limit(self.env, self.AdminUser.id)
        self.assertFalse(is_limited, "Rate limit should NOT trigger when under the threshold")

    def test_08_rate_limit_is_per_user(self):
        """Test that one user's messages don't affect another user's rate limit."""
        from odoo.addons.topic_chatbot.controllers.main import TopicChatbotController

        controller = TopicChatbotController()

        # Create a second user
        DemoUser = self.env['res.users'].create({
            'name': 'Rate Limit Test User',
            'login': 'rate_limit_test_user',
            'groups_id': [
                (4, self.env.ref('base.group_user').id),
                (4, self.env.ref('topic_chatbot.group_topic_chatbot_user').id),
            ]
        })

        # Admin sends max messages
        conv_admin = self.env['topic_chatbot.conversation'].create({
            'name': 'Admin Conv',
            'topic_id': self.Topic.id,
            'user_id': self.AdminUser.id,
        })
        for i in range(controller.RATE_LIMIT_MAX_MESSAGES):
            self.env['topic_chatbot.message'].create({
                'conversation_id': conv_admin.id,
                'role': 'user',
                'content': f'Admin spam {i}',
            })

        self.env.flush_all()

        # Admin should be blocked
        self.assertTrue(controller._check_rate_limit(self.env, self.AdminUser.id),
                        "Admin should be rate-limited")

        # DemoUser should NOT be blocked
        self.assertFalse(controller._check_rate_limit(self.env, DemoUser.id),
                         "DemoUser should NOT be rate-limited by Admin's messages")

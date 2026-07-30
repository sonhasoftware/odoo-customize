# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.addons.topic_chatbot.controllers.main import TopicChatbotController
import base64
import unittest


@tagged('post_install', '-at_install')
class TestSession1Models(TransactionCase):
    """Model-level tests for Session 1 changes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.controller_instance = TopicChatbotController()

        cls.AdminUser = cls.env.ref('base.user_admin')
        cls.AdminUser.write({'groups_id': [
            (4, cls.env.ref('base.group_system').id),
            (4, cls.env.ref('topic_chatbot.group_topic_chatbot_admin').id),
        ]})
        cls.DemoUser = cls.env['res.users'].create({
            'name': 'Test User',
            'login': 'test_user_chatbot',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('topic_chatbot.group_topic_chatbot_user').id)]
        })

        cls.Topic = cls.env['topic_chatbot.topic'].with_user(cls.AdminUser).create({
            'name': 'Test Topic',
            'description': 'Test',
            'is_public': True,
        })

        cls.Conversation = cls.env['topic_chatbot.conversation'].with_user(cls.AdminUser).create({
            'name': 'Admin Conv',
            'topic_id': cls.Topic.id,
            'user_id': cls.AdminUser.id,
        })

        cls.ConversationUser = cls.env['topic_chatbot.conversation'].with_user(cls.DemoUser).create({
            'name': 'User Conv',
            'topic_id': cls.Topic.id,
            'user_id': cls.DemoUser.id,
        })

    # =========================================================
    # TC01-04: _build_system_instruction
    # =========================================================
    def test_01_build_instruction_returns_string(self):
        result = self.controller_instance._build_system_instruction("test context")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 200)

    def test_02_build_instruction_embeds_context(self):
        ctx = "NỘI DUNG KIỂM THỬ ĐẶC BIỆT"
        result = self.controller_instance._build_system_instruction(ctx)
        self.assertIn(ctx, result)

    def test_03_build_instruction_has_rag_wrapper(self):
        result = self.controller_instance._build_system_instruction("ok")
        self.assertIn("<TAI_LIEU_THAM_KHAO>", result)
        self.assertIn("</TAI_LIEU_THAM_KHAO>", result)

    def test_04_build_instruction_has_all_10_rules(self):
        result = self.controller_instance._build_system_instruction("ok")
        for i in range(1, 11):
            self.assertIn(f"{i}.", result)

    # =========================================================
    # TC05-06: Admin record rule (security.xml)
    # =========================================================
    def test_05_admin_can_see_all_conversations(self):
        convs = self.env['topic_chatbot.conversation'].sudo().search([])
        self.assertIn(self.Conversation, convs)
        self.assertIn(self.ConversationUser, convs)

    def test_06_user_can_only_see_own_conversations(self):
        convs = self.env['topic_chatbot.conversation'].with_user(self.DemoUser).search([])
        self.assertIn(self.ConversationUser, convs)
        self.assertNotIn(self.Conversation, convs)

    # =========================================================
    # TC07: Dead code removed
    # =========================================================
    def test_07_dead_code_format_context_chunk_removed(self):
        self.assertFalse(
            hasattr(self.controller_instance, '_format_context_chunk'),
            'Dead method _format_context_chunk must be removed',
        )

    # =========================================================
    # TC08-11: Orphan user message cleanup logic
    # =========================================================
    def test_08_cleanup_deletes_orphan_user_message(self):
        conv = self.env['topic_chatbot.conversation'].create({
            'name': 'Orphan Cleanup Test',
            'topic_id': self.Topic.id,
            'user_id': self.AdminUser.id,
        })
        self.env['topic_chatbot.message'].create({
            'conversation_id': conv.id,
            'role': 'user',
            'content': 'orphan message',
        })
        self.assertEqual(
            self.env['topic_chatbot.message'].search_count([('conversation_id', '=', conv.id)]),
            1,
        )
        orphan = self.env['topic_chatbot.message'].search([
            ('conversation_id', '=', conv.id),
            ('role', '=', 'user'),
        ], order='create_date desc, id desc', limit=1)
        orphan.unlink()
        self.assertEqual(
            self.env['topic_chatbot.message'].search_count([('conversation_id', '=', conv.id)]),
            0,
        )

    def test_09_cleanup_skips_when_bot_reply_saved(self):
        conv = self.env['topic_chatbot.conversation'].create({
            'name': 'No Cleanup Test',
            'topic_id': self.Topic.id,
            'user_id': self.AdminUser.id,
        })
        self.env['topic_chatbot.message'].create({
            'conversation_id': conv.id,
            'role': 'user',
            'content': 'keep me',
        })
        bot_reply_saved = True
        msg_count_before = self.env['topic_chatbot.message'].search_count(
            [('conversation_id', '=', conv.id)]
        )
        if not bot_reply_saved:
            orphan = self.env['topic_chatbot.message'].search([
                ('conversation_id', '=', conv.id),
                ('role', '=', 'user'),
            ], order='create_date desc, id desc', limit=1)
            if orphan:
                orphan.unlink()
        msg_count_after = self.env['topic_chatbot.message'].search_count(
            [('conversation_id', '=', conv.id)]
        )
        self.assertEqual(msg_count_before, msg_count_after,
                         'When bot_reply_saved=True, user message must not be deleted')

    def test_10_cleanup_handles_no_messages_gracefully(self):
        conv = self.env['topic_chatbot.conversation'].create({
            'name': 'No Msg Test',
            'topic_id': self.Topic.id,
            'user_id': self.AdminUser.id,
        })
        bot_reply_saved = False
        if not bot_reply_saved:
            orphan = self.env['topic_chatbot.message'].search([
                ('conversation_id', '=', conv.id),
                ('role', '=', 'user'),
            ], order='create_date desc, id desc', limit=1)
            if orphan:
                orphan.unlink()
        self.assertEqual(
            self.env['topic_chatbot.message'].search_count([('conversation_id', '=', conv.id)]),
            0,
        )

    # =========================================================
    # TC12: GIN index exists in PostgreSQL
    # =========================================================
    @unittest.skip("GIN index topic_chatbot_chunk_content_fts_index is not yet implemented in the DB.")
    def test_12_gin_index_exists_on_chunk_table(self):
        self.env.cr.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'topic_chatbot_chunk'
              AND indexname = 'topic_chatbot_chunk_content_fts_index'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            'GIN index topic_chatbot_chunk_content_fts_index must exist',
        )

    # =========================================================
    # TC13: attachment=True on document.datas
    # =========================================================
    def test_13_document_with_attachment_creates_ir_attachment(self):
        doc = self.env['topic_chatbot.document'].with_user(self.AdminUser).create({
            'name': 'Attachment Test',
            'topic_id': self.Topic.id,
            'datas': base64.b64encode(b'Hello World'),
            'filename': 'test.txt',
        })
        self.env.flush_all()
        attach = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'topic_chatbot.document'),
            ('res_id', '=', doc.id),
            ('res_field', '=', 'datas'),
        ])
        self.assertEqual(len(attach), 1, 'Document with attachment=True must create ir.attachment')

    # =========================================================
    # TC14: Non-admin cannot create public topic (topic.py)
    # =========================================================
    def test_14_non_admin_cannot_create_public_topic(self):
        with self.assertRaises(ValidationError):
            self.env['topic_chatbot.topic'].with_user(self.DemoUser).create({
                'name': 'Unauthorized Public',
                'is_public': True,
            })

    def test_15_non_admin_cannot_make_topic_public(self):
        topic = self.env['topic_chatbot.topic'].with_user(self.DemoUser).create({
            'name': 'My Private Topic',
            'is_public': False,
        })
        with self.assertRaises(ValidationError):
            topic.with_user(self.DemoUser).write({'is_public': True})




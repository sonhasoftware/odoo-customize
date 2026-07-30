# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.addons.topic_chatbot.controllers.main import TopicChatbotController
import json
import base64
import unittest
from unittest.mock import patch, MagicMock
from contextlib import contextmanager


@tagged('post_install', '-at_install')
class TestTopicChatbotControllers(TransactionCase):
    """Comprehensive unit tests for TopicChatbotController endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.controller = TopicChatbotController()
        
        # Create users
        cls.AdminUser = cls.env.ref('base.user_admin')
        cls.AdminUser.write({'groups_id': [
            (4, cls.env.ref('base.group_system').id),
            (4, cls.env.ref('topic_chatbot.group_topic_chatbot_admin').id),
        ]})
        
        cls.DemoUser = cls.env['res.users'].create({
            'name': 'Test User Controllers',
            'login': 'test_user_controllers',
            'groups_id': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('topic_chatbot.group_topic_chatbot_user').id),
            ]
        })

        # Create test data
        cls.PublicTopic = cls.env['topic_chatbot.topic'].with_user(cls.AdminUser).create({
            'name': 'Public Topic Controller Test',
            'description': 'Public topic for controller testing',
            'is_public': True,
        })

        cls.PrivateTopic = cls.env['topic_chatbot.topic'].with_user(cls.DemoUser).create({
            'name': 'Private Topic Controller Test',
            'description': 'Private topic for controller testing',
            'is_public': False,
        })

        cls.AdminConversation = cls.env['topic_chatbot.conversation'].create({
            'name': 'Admin Test Conversation',
            'topic_id': cls.PublicTopic.id,
            'user_id': cls.AdminUser.id,
        })

        cls.UserConversation = cls.env['topic_chatbot.conversation'].create({
            'name': 'User Test Conversation', 
            'topic_id': cls.PublicTopic.id,
            'user_id': cls.DemoUser.id,
        })
        
        # Set up config parameters
        cls.env['ir.config_parameter'].sudo().set_param('topic_chatbot.gemini_api_key', 'test_api_key_123')
        cls.env['ir.config_parameter'].sudo().set_param('topic_chatbot.gemini_model', 'gemini-1.5-flash')
        cls.env.flush_all()

    @contextmanager
    def _mock_request(self, env=None, uid=None):
        """Helper to mock request in main controller directly using patch(new=mock)."""
        self.env.flush_all()
        mock = MagicMock()
        target_uid = uid if uid is not None else self.DemoUser.id
        mock.env = env if env is not None else self.env(user=target_uid)
        mock.uid = target_uid
        
        with patch('odoo.addons.topic_chatbot.controllers.main.request', new=mock):
            yield mock

    # =================================================================
    # GET_TOPICS ENDPOINT TESTS
    # =================================================================
    
    def test_01_get_topics_returns_all_accessible_topics(self):
        """Test get_topics returns all topics user has access to."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.get_topics()
            
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            
            topic_ids = [t['id'] for t in result]
            self.assertIn(self.PublicTopic.id, topic_ids)
            
            for topic in result:
                self.assertIn('id', topic)
                self.assertIn('name', topic)
                self.assertIn('description', topic)
                self.assertIn('is_public', topic)
                self.assertIn('owner', topic)

    def test_02_get_topics_empty_result_when_no_access(self):
        """Test get_topics with a user having no accessible topics."""
        NoTopicUser = self.env['res.users'].create({
            'name': 'No Topic User',
            'login': 'no_topic_user',
            'groups_id': [
                (4, self.env.ref('base.group_user').id),
                (4, self.env.ref('topic_chatbot.group_topic_chatbot_user').id),
            ]
        })
        # Create a private topic owned by Admin
        self.env['topic_chatbot.topic'].with_user(self.AdminUser).create({
            'name': 'Admin Only Private Topic',
            'is_public': False,
        })
        self.env.flush_all()
        
        with self._mock_request(self.env(user=NoTopicUser.id), NoTopicUser.id):
            result = self.controller.get_topics()
            self.assertIsInstance(result, list)

    # =================================================================
    # GET_CONVERSATIONS ENDPOINT TESTS  
    # =================================================================
    
    def test_03_get_conversations_valid_topic_returns_user_conversations(self):
        """Test get_conversations returns conversations for valid topic."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.get_conversations(self.PublicTopic.id)
            
            self.assertIsInstance(result, list)
            conversation_ids = [c['id'] for c in result]
            self.assertIn(self.UserConversation.id, conversation_ids)
            self.assertNotIn(self.AdminConversation.id, conversation_ids)
            
            for conv in result:
                self.assertIn('id', conv)
                self.assertIn('name', conv)
                self.assertIn('topic_id', conv)
                self.assertIn('create_date', conv)

    def test_04_get_conversations_invalid_topic_id_returns_empty(self):
        """Test get_conversations with invalid topic ID."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.get_conversations('invalid_id')
            self.assertEqual(result, [])
            
            result = self.controller.get_conversations(99999)
            self.assertEqual(result, [])

    def test_05_get_conversations_nonexistent_topic_returns_empty(self):
        """Test get_conversations with non-existent topic ID."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.get_conversations(99999)
            self.assertEqual(result, [])

    # =================================================================
    # GET_MESSAGES ENDPOINT TESTS
    # =================================================================
    
    def test_06_get_messages_valid_conversation_returns_messages(self):
        """Test get_messages returns messages for valid conversation."""
        user_msg = self.env['topic_chatbot.message'].create({
            'conversation_id': self.UserConversation.id,
            'role': 'user',
            'content': 'Test user message',
        })
        
        model_msg = self.env['topic_chatbot.message'].create({
            'conversation_id': self.UserConversation.id,
            'role': 'model',
            'content': 'Test model response',
        })
        self.env.flush_all()
        
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.get_messages(self.UserConversation.id)
            
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 2)
            
            message_ids = [m['id'] for m in result]
            self.assertIn(user_msg.id, message_ids)
            self.assertIn(model_msg.id, message_ids)
            
            for msg in result:
                self.assertIn('id', msg)
                self.assertIn('role', msg)
                self.assertIn('content', msg)
                self.assertIn('create_date', msg)

    def test_07_get_messages_unauthorized_conversation_returns_empty(self):
        """Test get_messages with unauthorized conversation access."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.get_messages(self.AdminConversation.id)
            self.assertEqual(result, [])

    def test_08_get_messages_invalid_conversation_id_returns_empty(self):
        """Test get_messages with invalid conversation ID."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.get_messages('invalid')
            self.assertEqual(result, [])
            
            result = self.controller.get_messages(99999)
            self.assertEqual(result, [])

    # =================================================================
    # CREATE_CONVERSATION ENDPOINT TESTS
    # =================================================================
    
    def test_09_create_conversation_valid_topic_success(self):
        """Test create_conversation with valid topic."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.create_conversation(self.PublicTopic.id)
            
            self.assertIn('id', result)
            self.assertIn('name', result)
            self.assertIn('topic_id', result)
            self.assertEqual(result['name'], 'New Chat')
            self.assertEqual(result['topic_id'], self.PublicTopic.id)
            
            conv = self.env['topic_chatbot.conversation'].browse(result['id'])
            self.assertTrue(conv.exists())
            self.assertEqual(conv.user_id.id, self.DemoUser.id)

    def test_10_create_conversation_invalid_topic_id_returns_error(self):
        """Test create_conversation with invalid topic ID."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.create_conversation('invalid')
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Topic not found.')

    def test_11_create_conversation_nonexistent_topic_returns_error(self):
        """Test create_conversation with non-existent topic."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.create_conversation(99999)
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Topic not found.')

    # =================================================================
    # DELETE_CONVERSATION ENDPOINT TESTS
    # =================================================================
    
    def test_12_delete_conversation_own_conversation_success(self):
        """Test delete_conversation with user's own conversation."""
        conv = self.env['topic_chatbot.conversation'].create({
            'name': 'To Be Deleted',
            'topic_id': self.PublicTopic.id,
            'user_id': self.DemoUser.id,
        })
        self.env.flush_all()
        
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.delete_conversation(conv.id)
            
            self.assertIn('success', result)
            self.assertTrue(result['success'])
            self.assertFalse(conv.exists())

    def test_13_delete_conversation_unauthorized_returns_error(self):
        """Test delete_conversation with unauthorized access."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.delete_conversation(self.AdminConversation.id)
            
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Conversation not found or access denied.')
            self.assertTrue(self.AdminConversation.exists())

    def test_14_delete_conversation_invalid_id_returns_error(self):
        """Test delete_conversation with invalid conversation ID."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.delete_conversation('invalid')
            self.assertIn('error', result)
            
            result = self.controller.delete_conversation(99999)
            self.assertIn('error', result)

    # =================================================================
    # HELPER METHODS TESTS
    # =================================================================
    
    def test_15_build_system_instruction_contains_context(self):
        """Test _build_system_instruction includes context."""
        context = "Test context content"
        result = self.controller._build_system_instruction(context)
        
        self.assertIsInstance(result, str)
        self.assertIn(context, result)
        self.assertIn('<TAI_LIEU_THAM_KHAO>', result)
        self.assertIn('</TAI_LIEU_THAM_KHAO>', result)
        self.assertGreater(len(result), 1000)

    def test_16_build_system_instruction_empty_context(self):
        """Test _build_system_instruction with empty context."""
        result = self.controller._build_system_instruction("")
        
        self.assertIsInstance(result, str)
        self.assertIn('<TAI_LIEU_THAM_KHAO>', result)
        self.assertIn('</TAI_LIEU_THAM_KHAO>', result)

    def test_17_sanitize_technical_terms_replaces_patterns(self):
        """Test _sanitize_technical_terms replaces technical terms."""
        test_text = (
            "Data from hr.employee and hr.department shows employee_id 123 "
            "with department_id 456 has complete_name John Doe."
        )
        
        result = self.controller._sanitize_technical_terms(test_text)
        
        self.assertNotIn('hr.employee', result)
        self.assertNotIn('hr.department', result)
        self.assertNotIn('employee_id', result)
        self.assertNotIn('department_id', result)
        self.assertNotIn('complete_name', result)
        
        self.assertIn('thông tin nhân viên', result)
        self.assertIn('thông tin phòng ban', result)
        self.assertIn('nhân viên', result)
        self.assertIn('phòng ban', result)
        self.assertIn('tên đầy đủ', result)

    def test_18_sanitize_technical_terms_empty_text(self):
        """Test _sanitize_technical_terms with empty text."""
        result = self.controller._sanitize_technical_terms("")
        self.assertEqual(result, "")
        
        result = self.controller._sanitize_technical_terms(None)
        self.assertIsNone(result)

    def test_19_execute_odoo_query_safe_models_only(self):
        """Test _execute_odoo_query only allows safe models."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller._execute_odoo_query('res.users', [], ['name'])
            self.assertIn('error', result)
            self.assertIn('bị hạn chế vì lý do bảo mật', result['error'])

    def test_20_execute_odoo_query_safe_model_success(self):
        """Test _execute_odoo_query with safe model."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller._execute_odoo_query('hr.department', [], ['name'])
            self.assertIsInstance(result, (list, dict))
            if isinstance(result, dict):
                self.assertNotIn('error', result)

    def test_21_check_rate_limit_under_threshold_allows(self):
        """Test _check_rate_limit allows requests under threshold."""
        for i in range(self.controller.RATE_LIMIT_MAX_MESSAGES - 1):
            self.env['topic_chatbot.message'].create({
                'conversation_id': self.UserConversation.id,
                'role': 'user',
                'content': f'Test message {i}',
            })
        
        self.env.flush_all()
        result = self.controller._check_rate_limit(self.env, self.DemoUser.id)
        self.assertFalse(result)

    def test_22_check_rate_limit_over_threshold_blocks(self):
        """Test _check_rate_limit blocks when over threshold."""
        for i in range(self.controller.RATE_LIMIT_MAX_MESSAGES):
            self.env['topic_chatbot.message'].create({
                'conversation_id': self.UserConversation.id,
                'role': 'user',
                'content': f'Rate limit test {i}',
            })
        
        self.env.flush_all()
        result = self.controller._check_rate_limit(self.env, self.DemoUser.id)
        self.assertTrue(result)

    # =================================================================
    # ASK ENDPOINT TESTS (Mocked API calls)
    # =================================================================
    
    @patch('requests.post')
    def test_23_ask_endpoint_success_flow(self, mock_post):
        """Test ask endpoint success flow with mocked Gemini API."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'Mocked AI response'}]
                },
                'finishReason': 'STOP'
            }]
        }
        mock_post.return_value = mock_response
        
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.ask(self.UserConversation.id, 'Test question')
            
            self.assertIn('response', result)
            self.assertIn('conversation_name', result)
            self.assertEqual(result['response'], 'Mocked AI response')
            mock_post.assert_called_once()

    @patch('requests.post')
    def test_24_ask_endpoint_rate_limit_blocks(self, mock_post):
        """Test ask endpoint blocks when rate limited."""
        for i in range(self.controller.RATE_LIMIT_MAX_MESSAGES):
            self.env['topic_chatbot.message'].create({
                'conversation_id': self.UserConversation.id,
                'role': 'user',
                'content': f'Rate limit message {i}',
            })
        
        self.env.flush_all()
        
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.ask(self.UserConversation.id, 'Should be blocked')
            
            self.assertIn('error', result)
            self.assertIn('quá 5 câu hỏi', result['error'])
            mock_post.assert_not_called()

    def test_25_ask_endpoint_processing_blocks(self):
        """Test ask endpoint blocks when conversation is processing."""
        self.UserConversation.write({'is_processing': True})
        
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.ask(self.UserConversation.id, 'Should be blocked')
            
            self.assertIn('error', result)
            self.assertIn('chờ câu trả lời trước', result['error'])

    def test_26_ask_endpoint_no_api_key_returns_error(self):
        """Test ask endpoint without API key configured."""
        self.env['ir.config_parameter'].sudo().set_param('topic_chatbot.gemini_api_key', '')
        
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.ask(self.UserConversation.id, 'Test without API key')
            
            self.assertIn('response', result)
            self.assertIn('Chưa cấu hình Gemini API Key', result['response'])

    def test_27_ask_endpoint_invalid_conversation_returns_error(self):
        """Test ask endpoint with invalid conversation."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.ask('invalid', 'Test message')
            self.assertIn('error', result)
            
            result = self.controller.ask(99999, 'Test message')
            self.assertIn('error', result)

    @patch('requests.post')
    def test_28_ask_endpoint_api_exception_handling(self, mock_post):
        """Test ask endpoint handles API exceptions gracefully."""
        mock_post.side_effect = Exception('Mocked API error')
        
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.ask(self.UserConversation.id, 'Test API error')
            
            self.assertIn('response', result)
            self.assertIn('lỗi khi kết nối', result['response'])

    def test_29_ask_endpoint_unauthorized_conversation_returns_error(self):
        """Test ask endpoint with unauthorized conversation access."""
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            result = self.controller.ask(self.AdminConversation.id, 'Unauthorized access')
            
            self.assertIn('error', result)
            self.assertIn('not found or access denied', result['error'])

    @patch('requests.post') 
    def test_30_ask_endpoint_conversation_name_update(self, mock_post):
        """Test ask endpoint updates conversation name from 'New Chat'."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'Response to long question'}]
                },
                'finishReason': 'STOP'
            }]
        }
        mock_post.return_value = mock_response
        
        conv = self.env['topic_chatbot.conversation'].create({
            'name': 'New Chat',
            'topic_id': self.PublicTopic.id,
            'user_id': self.DemoUser.id,
        })
        self.env.flush_all()
        
        with self._mock_request(self.env(user=self.DemoUser.id), self.DemoUser.id):
            long_message = 'This is a very long message that should become the conversation name'
            result = self.controller.ask(conv.id, long_message)
            
            self.assertIn('conversation_name', result)
            self.assertNotEqual(result['conversation_name'], 'New Chat')
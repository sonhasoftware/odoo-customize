# -*- coding: utf-8 -*-

import base64
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.topic_chatbot.services.sql_engine import execute_odoo_query


@tagged('post_install', '-at_install')
class TestDecisionArchive(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['decision.document.category'].create({
            'name': 'Nhân sự',
            'code': 'TEST-HR',
            'company_id': cls.env.company.id,
        })
        cls.child_category = cls.env['decision.document.category'].create({
            'name': 'Quyết định bổ nhiệm',
            'code': 'TEST-APPOINT',
            'parent_id': cls.category.id,
            'company_id': cls.env.company.id,
        })
        cls.internal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Decision Archive Test User',
            'login': 'decision_archive_test_user',
            'company_id': cls.env.company.id,
            'company_ids': [(6, 0, cls.env.company.ids)],
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    def _create_document(self, reference, state='draft', with_file=False):
        values = {
            'name': f'Quyết định {reference}',
            'reference': reference,
            'category_id': self.child_category.id,
            'company_id': self.env.company.id,
            'state': state,
        }
        if with_file:
            values.update({
                'file_name': f'{reference}.pdf',
                'file_data': base64.b64encode(b'%PDF-1.4\nTEST\n%%EOF'),
            })
        return self.env['decision.document'].create(values)

    def test_category_path_and_document_counter(self):
        document = self._create_document('TEST-001', with_file=True)
        self.assertEqual(self.child_category.complete_name, 'Nhân sự / Quyết định bổ nhiệm')
        self.assertEqual(self.child_category.document_count, 1)
        self.assertEqual(document.category_id, self.child_category)

    def test_publish_requires_source_and_builds_download_link(self):
        document = self._create_document('TEST-002')
        with self.assertRaises(UserError):
            document.action_publish()

        document.write({
            'file_name': 'quyet_dinh.pdf',
            'file_data': base64.b64encode(b'%PDF-1.4\nTEST\n%%EOF'),
        })
        document.action_publish()

        self.assertEqual(document.state, 'published')
        self.assertTrue(document.has_file)
        self.assertIn('/web/content/decision.document/', document.file_url)
        self.assertEqual(document.action_open_file()['target'], 'new')

    def test_internal_user_only_sees_published_documents(self):
        draft = self._create_document('TEST-003', with_file=True)
        published = self._create_document('TEST-004', with_file=True)
        published.action_publish()

        visible = self.env['decision.document'].with_user(self.internal_user).search([
            ('id', 'in', (draft.id, published.id)),
        ])
        self.assertEqual(visible, published)

        with self.assertRaises(AccessError):
            self.env['decision.document'].with_user(self.internal_user).create({
                'name': 'Không được phép tạo',
                'reference': 'TEST-005',
                'category_id': self.child_category.id,
                'company_id': self.env.company.id,
            })

    def test_chatbot_search_returns_only_published_documents_and_safe_links(self):
        draft = self._create_document('TEST-006', with_file=True)
        published = self._create_document('TEST-007', with_file=True)
        published.action_publish()

        result = execute_odoo_query(
            model='decision_documents',
            domain=json.dumps([['id', 'in', [draft.id, published.id]]]),
            fields=['name', 'reference', 'issue_date', 'file_url', 'file_data'],
            env=self.env,
        )

        self.assertEqual([item['id'] for item in result], [published.id])
        self.assertNotIn('file_data', result[0])
        self.assertIsInstance(result[0]['issue_date'], str)
        self.assertTrue(result[0]['file_url'].startswith('http'))
        self.assertIn('model=decision.document', result[0]['record_url'])
        json.dumps(result)


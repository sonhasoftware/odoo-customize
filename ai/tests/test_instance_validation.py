# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase
from odoo.addons.ai.utils.tools_schema import validators


class TestInstanceValidation(TransactionCase):

    def validate_instance_with_schema(self, schema, instance, required_parameters=None, error_message=''):
        if required_parameters is None:
            required_parameters = list(schema.keys())

        if error_message:
            with self.assertRaisesRegex(ValidationError, re.escape(error_message)):
                validators.validate_params_llm_values_with_schema(
                    instance=instance,
                    schema=schema,
                    required_parameters=required_parameters,
                    env=self.env,
                )
        else:
            return validators.validate_params_llm_values_with_schema(
                instance=instance,
                schema=schema,
                required_parameters=required_parameters,
                env=self.env,
            )

    def test_missing_optional_parameter(self):
        '''
        Assert that when some parameters are not required and are missing from the LLM response, the validation will succeed.
        '''
        schema = {
            'user_name': {
                'type': 'string',
                'description': 'the name of the user',
            },
            'phone_number': {
                'type': 'string',
                'description': 'the phone number of the user',
            },
        }
        instance = {'user_name': 'Mohamed'}
        required_parameters = ['user_name']
        instance = self.validate_instance_with_schema(
            instance=instance,
            schema=schema,
            required_parameters=required_parameters,
        )
        # non required param should have been added
        self.assertEqual(instance['phone_number'], None)

    def test_missing_required_parameter(self):
        '''
        Assert that when some parameters are required but are missing from the LLM response, the validation will fail.
        '''
        schema = {
            'user_name': {
                'type': 'string',
                'description': 'the name of the user',
            },
            'phone_number': {
                'type': 'string',
                'description': 'the phone number of the user',
            },
        }
        instance = {'phone_number': '+32123456789'}
        required_parameters = ['user_name', 'phone_number']
        self.validate_instance_with_schema(
            instance=instance,
            schema=schema,
            required_parameters=required_parameters,
            error_message="Could you please provide info about 'user_name' as it is required to process your request",
        )

    def test_wrong_type_parameter(self):
        param_name = 'user_age'
        param_type = 'number'
        schema = {
            param_name: {
                'type': param_type,
                'description': 'the age of the user',
            }
        }
        instance = {param_name: 'fifteen'}
        self.validate_instance_with_schema(
            schema=schema,
            instance=instance,
            error_message=f"The type of the parameter '{param_name}' is incorrect. It should be '{param_type}'."
        )

    def test_wrong_pattern_parameter(self):
        '''
        Assert that when a parameter doesn't follow the expected pattern, the validation will fail.
        '''
        param_name = 'meeting_date'
        # The pattern validates that the date of the form YYYY-mm-dd
        param_pattern = r'^20\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])'
        schema = {
            param_name: {
                'type': 'string',
                'description': 'the date of the meeting',
                'pattern': param_pattern,
            }
        }
        instance = {param_name: '2025-31-01'}
        self.validate_instance_with_schema(
            schema=schema,
            instance=instance,
            error_message=f"The value '{instance[param_name]}' of the parameter '{param_name}' doesn't match the expected pattern '{param_pattern}'."
        )

    def test_wrong_type_array_item(self):
        param_name = 'numbers_to_sum'
        schema = {
            param_name: {
                'type': 'array',
                'items': {'type': 'number'},
                'description': 'the numbers whose sum is computed',
            }
        }
        instance = {param_name: [15, 20, 'hello']}
        self.validate_instance_with_schema(
            schema=schema,
            instance=instance,
            error_message="The type of the parameter 'numbers_to_sum's item' is incorrect. It should be 'number'.",
        )

    def test_correct_pattern_array_item(self):
        '''
        Assert that when an array item follows the expected pattern, the validation will succeed.
        '''
        param_name = 'meeting_date'
        # The pattern validates that the date of the form YYYY-mm-dd
        param_pattern = r'^20\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])'
        schema = {
            param_name: {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'the date of the meeting',
                'pattern': param_pattern,
            }
        }
        instance = {param_name: ['2025-01-31', '2024-05-29']}
        self.validate_instance_with_schema(
            schema=schema,
            instance=instance,
        )

    def test_wrong_pattern_array_item(self):
        '''
        Assert that when an array item doesn't follow the expected pattern, the validation will fail.
        '''
        param_name = 'meeting_date'
        # The pattern validates that the date of the form YYYY-mm-dd
        param_pattern = r'^20\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])'
        schema = {
            param_name: {
                'type': 'array',
                'items': {'type': 'string', 'pattern': param_pattern},
                'description': 'the date of the meeting',
            }
        }
        invalid_value = '2025-31-01'
        instance = {param_name: ['2025-01-31', invalid_value]}
        self.validate_instance_with_schema(
            schema=schema,
            instance=instance,
            error_message=f"The value '{invalid_value}' of the parameter 'meeting_date's item' doesn't match the expected pattern '{param_pattern}'."
        )

    def test_missing_optional_object_property(self):
        '''
        Assert that when some properties of an object parameter are not required and are missing from the LLM response, the validation will succeed.
        '''
        param_name = 'object_param'
        schema = {
            param_name: {
                'type': 'object',
                'description': 'user contact details',
                'properties': {
                    'email': {
                        'type': 'string',
                        'description': 'the email of the user',
                    },
                    'phone': {
                        'type': 'string',
                        'description': 'the phone number of the user',
                    },
                },
                'required': ['email'],
            }
        }
        instance = {param_name: {'email': 'Mohamed@gmail.com'}}
        self.validate_instance_with_schema(
            schema=schema,
            instance=instance,
        )

    def test_missing_required_object_property(self):
        '''
        Assert that when some properties of an object parameter are required but are missing from the LLM response, the validation will fail.
        '''
        param_name = 'object_param'
        schema = {
            param_name: {
                'type': 'object',
                'description': 'user contact details',
                'properties': {
                    'email': {
                        'type': 'str',
                        'description': 'the email of the user',
                    },
                    'phone': {
                        'type': 'str',
                        'description': 'the phone number of the user',
                    },
                },
                'required': ['email']
            }
        }
        instance = {param_name: {'phone': '+32123456789'}}
        self.validate_instance_with_schema(
            schema=schema,
            instance=instance,
            error_message="Could you please provide info about 'email' as it is required to process your request",
        )

    def test_wrong_type_object_property(self):
        param_name = 'object_param'
        property_name = 'email'
        property_type = 'string'
        schema = {
            param_name: {
                'type': 'object',
                'description': 'user contact details',
                'properties': {
                    property_name: {
                        'type': property_type,
                        'description': 'the email of the user',
                    },
                },
                'required': [property_name]
            }
        }
        instance = {param_name: {'email': 123}}
        self.validate_instance_with_schema(
            schema=schema,
            instance=instance,
            error_message=f"The type of the parameter '{property_name}' is incorrect. It should be '{property_type}'.",
        )

    def test_wrong_format_object_property(self):
        '''
        Assert that when an object property doesn't follow the expected pattern, the validation will fail.
        '''
        param_name = 'object_param'
        property_name = 'email'
        property_type = 'string'
        property_pattern = r'\w+@\w+\.\w+'
        property_value = 'saif_genidy@odoo'
        schema = {
            param_name: {
                'type': 'object',
                'description': 'user contact details',
                'properties': {
                    property_name: {
                        'type': property_type,
                        'description': 'the email of the user',
                        'pattern': property_pattern,
                    },
                },
                'required': [property_name]
            }
        }
        instance = {param_name: {property_name: property_value}}
        self.validate_instance_with_schema(
            schema=schema,
            instance=instance,
            error_message=f"The value '{property_value}' of the parameter '{property_name}' doesn't match the expected pattern '{property_pattern}'.",
        )

    def test_truncate(self):
        schema = {
            'object_param': {
                'type': 'object',
                'description': 'object root',
                'properties': {
                    'str_value': {
                        'type': 'string',
                        'description': 'str value',
                        'maxLength': 5,
                    },
                    'sub_obj': {
                        'type': 'object',
                        'description': 'sub object',
                        'properties': {
                            'str_value_2': {
                                'type': 'string',
                                'description': 'str value',
                                'maxLength': 3,
                            },
                        },
                        'required': ['str_value_2'],
                    },
                },
                'required': ['str_value'],
            },
        }
        instance = {'object_param': {'str_value': '123456789', 'sub_obj': {'str_value_2': 'abcdefg'}}}
        ret = self.validate_instance_with_schema(
            schema=schema,
            instance=instance,
        )
        self.assertEqual(ret, {'object_param': {'str_value': '12345...', 'sub_obj': {'str_value_2': 'abc...'}}})

    def test_enum(self):
        schema = {'state': {'type': 'string', 'description': 'the date of the meeting', 'enum': ['done', 'ready']}}
        self.validate_instance_with_schema(schema=schema, instance={'state': 'done'})
        self.validate_instance_with_schema(
            schema=schema,
            instance={'state': 'invalid'},
            error_message="Wrong value invalid, should be in: done, ready",
        )

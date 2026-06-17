# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo.tests import TransactionCase
from odoo.addons.ai.utils.tools_schema import validators

DUMMY_ATTRIBUTES = {'type': 'string', 'description': '...'}
DUMMY_ARRAY_ATTRIBUTES = {
    'type': 'array',
    'items': {
        'anyOf': [{'type': 'string'}, {'type': 'number'}]}}
DUMMY_OBJECT_ATTRIBUTES = {
    'type': 'object',
    'properties': {
        'email': {
            'type': 'string',
            'description': 'The email of the user',
        }
    },
    'required': []
}


class TestParamSchemaValidation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wrong_array_item_type_error_message = (
            "The types of the items of the 'array' param 'array_param' are not defined correctly. "
            "The types of the items must be defined as ('items': {'type': 'string'}) if all items are of the same type "
            "or ('items': { 'anyOf': [ {'type': 'string'}, {'type': 'number'} ] }) if items are of different types"
        )

    def create_param(self, param_name='param', param_attributes=None, excluded_attributes=None):
        """
        The required attributes of a parameter are filled automatically with dummy values from DUMMY_ATTRIBUTES
        unless they are excluded in excluded_attributes.
        """
        if param_attributes is None:
            param_attributes = {}
        if excluded_attributes is None:
            excluded_attributes = []

        param_attributes = {**DUMMY_ATTRIBUTES, **param_attributes}
        for excluded_attribute in excluded_attributes:
            param_attributes.pop(excluded_attribute)

        schema = {}
        for attribute_name, attribute_value in param_attributes.items():
            schema[attribute_name] = attribute_value

        return {param_name: schema}

    def create_array_param(self, param_name='array_param', param_attributes=None, excluded_attributes=None):
        if param_attributes is None:
            param_attributes = {}
        if excluded_attributes is None:
            excluded_attributes = []

        param_attributes = {**DUMMY_ARRAY_ATTRIBUTES, **param_attributes}
        schema = self.create_param(
            param_name=param_name,
            param_attributes=param_attributes,
            excluded_attributes=excluded_attributes,
        )
        return schema

    def create_object_param(self, param_name='object_param', param_attributes=None, excluded_attributes=None):
        if param_attributes is None:
            param_attributes = {}
        if excluded_attributes is None:
            excluded_attributes = []

        param_attributes = {**DUMMY_OBJECT_ATTRIBUTES, **param_attributes}
        schema = self.create_param(
            param_name=param_name,
            param_attributes=param_attributes,
            excluded_attributes=excluded_attributes,
        )
        return schema

    def validate_schema(self, schema, error_type=ValueError, error_message=''):
        full_schema = {
            'type': 'object',
            'properties': schema,
            'required': list(schema.keys()),
        }

        if error_message:
            with self.assertRaisesRegex(error_type, re.escape(error_message)):
                validators.validate_schema(full_schema)
        else:
            validators.validate_schema(full_schema)

    def test_valid_schema(self):
        schema = {
            'user_id': {
                'type': 'string',
                'description': 'The unique identifier of the user whose profile is being updated. This is a permanent and immutable identifier.',
                'pattern': '^[a-zA-Z0-9-]+$',
            },
            'preferences': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'A list of the user\'s preferred categories or interests. These could be used for content filtering or recommendations.',
            },
            'contact_info': {
                'type': 'object',
                'description': 'An object containing the user\'s contact details.',
                'properties': {
                    'email': {
                        'type': 'string',
                        'description': 'The primary email address for the user. Must be a valid email format.',
                        'pattern': '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$',
                    },
                    'phone': {
                        'type': 'string',
                        'description': 'The user\'s primary phone number. Should follow a standard international format (e.g., +[country code][area code][local number]).',
                        'pattern': r'^\+\d{1,3}\s?\d+$',
                    },
                },
                'required': ['email'],
            },
        }

        self.validate_schema(schema=schema)

    def test_schema_with_no_params(self):
        schema = {}
        self.validate_schema(
            schema=schema,
        )

    def test_unsupported_type(self):
        schema = self.create_param(
            param_attributes={'type': 'method'}
        )
        self.validate_schema(
            schema=schema,
            error_message="The type 'method' of parameter 'param' is wrong.",
        )

    def test_missing_required_attribute(self):
        # Description attribute is missing
        schema = self.create_param(
            excluded_attributes=['type']
        )
        self.validate_schema(
            schema=schema,
            error_message="The attributes '['type']' must be defined for the parameter 'param'.",
        )

    def test_unsupported_attribute(self):
        param_name = 'param_with_unsupported_attributes'
        schema = self.create_param(
            param_name=param_name,
            param_attributes={'state': 'active'}
        )
        self.validate_schema(
            schema=schema,
            error_message=f"The attributes '['state']' defined for the param '{param_name}' are not supported."
        )

    def test_pattern_with_non_string_parameter(self):
        schema = self.create_param(
            param_attributes={'type': 'number', 'pattern': r'\d*'}
        )
        self.validate_schema(
            schema=schema,
            error_message=(
                "The pattern attribute cannot be defined for the parameter 'param'. "
                "The pattern attribute can only be defined for string parameters or arrays whose items are only of the type string."
            )
        )

    def test_array_parameter_with_different_item_types(self):
        schema = self.create_array_param()
        self.validate_schema(schema=schema)

    def test_array_parameter_without_item_types(self):
        # items attribute is missing.
        schema = self.create_array_param(
            excluded_attributes={'items'}
        )
        self.validate_schema(
            schema=schema,
            error_message="The attributes '['items']' must be defined for a parameter of type 'array'. They are missing for the parameter 'array_param'.",
        )

    def test_array_parameter_incorrect_item_types_definition_1(self):
        # items attribute must be a dict
        schema = self.create_array_param(
            param_attributes={'items': ['number', 'string']}
        )
        self.validate_schema(
            schema=schema,
            error_message=self.wrong_array_item_type_error_message
        )

    def test_array_parameter_incorrect_item_types_definition_2(self):
        # The dict can only have one key, either type or anyOf
        schema = self.create_array_param(
            param_attributes={
                'items': {'anyOf': [{'type': 'string'}], 'type': 'string'}
            }
        )
        self.validate_schema(
            schema=schema,
            error_message=self.wrong_array_item_type_error_message
        )

    def test_array_parameter_incorrect_item_types_definition_3(self):
        # The value of anyOf must be a list
        schema = self.create_array_param(
            param_attributes={
                'items': {'anyOf': {'type': 'string'}}
            }
        )
        self.validate_schema(
            schema=schema,
            error_message=self.wrong_array_item_type_error_message
        )

    def test_array_parameter_incorrect_item_types_definition_4(self):
        # No keys other than type or anyOf are allowed
        schema = self.create_array_param(
            param_attributes={
                'items': {'item': 'string'}
            }
        )
        self.validate_schema(
            schema=schema,
            error_message=self.wrong_array_item_type_error_message
        )

    def test_array_parameter_incorrect_item_types_definition_5(self):
        # The values inside the list of anyOf must be dicts
        schema = self.create_array_param(
            param_attributes={
                'items': {'anyOf': ['string']}
            }
        )
        self.validate_schema(
            schema=schema,
            error_message=self.wrong_array_item_type_error_message
        )

    def test_array_parameter_incorrect_item_types_definition_6(self):
        # The types of array items can be one of ['string', 'number', 'boolean']
        schema = self.create_array_param(
            param_attributes={
                'items': {'anyOf': [{'type': 'string'}, {'type': 'array'}]}
            }
        )
        self.validate_schema(
            schema=schema,
            error_message="The type '{'type': 'array'}' of the items of the 'array' parameter 'array_param' is wrong."
        )

    def test_2d_array_parameter(self):
        schema = self.create_array_param(
            param_attributes={
                'items': {
                    'anyOf': [{'type': 'array'}, {'type': 'string'}]
                }
            }
        )
        self.validate_schema(
            schema=schema,
            error_message="The type '{'type': 'array'}' of the items of the 'array' parameter 'array_param' is wrong.",
        )

    def test_pattern_with_string_array_items(self):
        schema = self.create_array_param(
            param_attributes={
                'type': 'array',
                'items': {'type': 'string'},
                'pattern': r'\d*'
            }
        )
        self.validate_schema(schema=schema)

    def test_pattern_with_non_string_array_items(self):
        schema = self.create_array_param(
            param_attributes={
                'type': 'array',
                'items': {'anyOf': [{'type': 'string'}, {'type': 'number'}]},
                'pattern': r'\d*'
            }
        )
        self.validate_schema(
            schema=schema,
            error_message=(
                "The pattern attribute cannot be defined for the parameter 'array_param'. "
                "The pattern attribute can only be defined for string parameters or arrays whose items are only of the type string."
            )
        )

    def test_object_parameter_with_array_property(self):
        property_definition = self.create_array_param()
        schema = self.create_object_param(
            param_attributes={
                'properties': property_definition,
            }
        )
        self.validate_schema(schema=schema)

    def test_object_parameter_without_properties_attribute(self):
        schema = self.create_object_param(
            excluded_attributes=['properties']
        )
        self.validate_schema(
            schema=schema,
            error_message="The attributes '['properties']' must be defined for a parameter of type 'object'. They are missing for the parameter 'object_param'.",
        )

    def test_object_parameter_without_required_attribute(self):
        schema = self.create_object_param(
            excluded_attributes=['required']
        )
        self.validate_schema(
            schema=schema,
            error_message="The attributes '['required']' must be defined for a parameter of type 'object'. They are missing for the parameter 'object_param'.",
        )

    def test_object_required_attribute_incorrect_definition(self):
        schema = self.create_object_param(
            param_attributes={'required': False}
        )
        self.validate_schema(
            schema=schema,
            error_type=TypeError,
            error_message=(
                "The attribute 'required' for the object param 'object_param' must be a 'list' containing "
                "the required properties of the object or empty if all of them are not required."
            )
        )

    def test_object_parameter_with_pattern_attribute(self):
        schema = self.create_object_param(
            param_attributes={'pattern': '^[a-zA-Z0-9]+$'}
        )
        self.validate_schema(
            schema=schema,
            error_message=(
                "The pattern attribute cannot be defined for the parameter 'object_param'."
                " The pattern attribute can only be defined for string parameters or arrays whose items are only of the type string."
            ),
        )

    def test_nested_object_parameter(self):
        inner_object_definition = self.create_object_param(
            param_name='inner_object'
        )
        outer_object_definition = self.create_object_param(
            param_attributes={
                'properties': inner_object_definition,
            }
        )
        self.validate_schema(
            schema=outer_object_definition,
            error_message="Nested objects are not supported. The parameter 'inner_object' is defined as an object inside another object.",
        )

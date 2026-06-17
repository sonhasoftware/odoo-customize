import re
from types import NoneType

from odoo.exceptions import ValidationError

from .param_schema_validator import ParamSchemaValidator


def validate_input(input_schema, required_parameters):
    if (
        required_parameters is None
        or not isinstance(required_parameters, list)
    ):
        raise ValueError(
            "The required properties should be specified as a list. i.e. 'required': [<property1_name>, <property2_name>, ...]."
            "If no properties are required, set required to an empty list 'required': []"
        )
    if any(
        required_property not in input_schema
        for required_property in required_parameters
    ):
        raise ValueError(
            "Some properties are required but their definition is missing in the schema"
        )


def validate_schema(schema):
    parameters = schema.get("properties")
    required_parameters = schema.get("required")
    validate_input(parameters, required_parameters)
    for param_name, param_definition in parameters.items():
        param_validator = ParamSchemaValidator(param_name, param_definition)
        param_validator._validate()


def validate_params_llm_values_with_schema(instance, schema, required_parameters, env):
    JSON_SCHEMA_TO_PYTHON_TYPE = {
        'string': str,
        'integer': int,
        'number': (float, int),
        'boolean': bool,
        'array': list,
        'object': dict,
        'null': NoneType,
    }

    for required in required_parameters:
        if required not in instance:
            raise ValidationError(env._("Could you please provide info about '%s' as it is required to process your request", required))

    instance.update({param: None for param in schema if param not in instance})

    for name, value in instance.items():
        if name not in schema:
            raise ValidationError(env._("Missing definition for %(name)s", name=name))
        if name not in required_parameters and value is None:
            continue

        if schema[name]['type'] not in JSON_SCHEMA_TO_PYTHON_TYPE or not isinstance(value, JSON_SCHEMA_TO_PYTHON_TYPE[schema[name]['type']]):
            raise ValidationError(env._(
                "The type of the parameter '%(name)s' is incorrect. It should be '%(expected_param_type)s'.",
                name=name,
                expected_param_type=schema[name]['type'],
            ))

        expected_pattern = schema[name]['type'] == 'string' and schema[name].get('pattern')
        if expected_pattern and not re.fullmatch(expected_pattern, value):
            raise ValidationError(env._(
                "The value '%(value)s' of the parameter '%(name)s' doesn't match the expected pattern '%(expected_pattern)s'.",
                value=value,
                name=name,
                expected_pattern=expected_pattern,
            ))

        if (enum := schema[name].get('enum')) and value not in enum:
            raise ValidationError(env._("Wrong value %(value)s, should be in: %(enum)s", value=value, enum=", ".join(map(str, enum))))

        max_length = schema[name]['type'] == 'string' and schema[name].get('maxLength')
        if isinstance(value, str) and max_length and len(value) > max_length:
            # As of July 31, Gemini does not respect the `maxLength` JSON schema
            # (while OpenAI does), so we manually truncate the arguments if needed
            instance[name] = value[:max_length] + "..."

        if schema[name]['type'] == 'object':
            instance[name] = validate_params_llm_values_with_schema(
                value,
                schema[name].get('properties', {}),
                schema[name].get('required', []),
                env,
            )

        if schema[name]['type'] == 'array':
            item_name = f"{name}'s item"
            for item_value in value:
                validate_params_llm_values_with_schema(
                    {item_name: item_value},
                    {item_name: schema[name]['items']},
                    [item_name],
                    env,
                )

    return instance

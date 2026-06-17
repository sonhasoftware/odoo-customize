# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import pytz
import requests
from datetime import datetime
from dateutil.parser import isoparse
from markupsafe import Markup

try:
    from markdown2 import markdown
except ImportError:
    markdown = None
from lxml import html

from odoo import fields
from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.exceptions import UserError
from odoo.tools import html_sanitize
from odoo.tools.mail import html_to_inner_content

AI_FIELDS_INSTRUCTIONS = """# Identity
You are an intelligent assistant integrated into an ERP system, specializing in generating accurate and relevant values for various data fields.

# Instructions
Your task is to resolve a single value for a specific ERP field based on the user's request or value description.

## Input Format
You will receive free-text prompts referring to ERP-related entities, values, or attributes, which may contain:
- Field references: {{field_path}} - their values are added in a context dict, provided below
- A context dict: it is an ORM snapshot that has the following structure:
    {
        <model_name>: [
                'id': <record_id>
                <field_name>: value | {'model': <model_name>, 'ids': [<res_id>]}
            ]
        }
    }
Where {'model': <model_name>, 'ids': [<res_id>]} are relational values and <file_#idx> refers to the additional inputs in the input array.

## Output Format
You must return a structured output:
- `value`: the value to assign.
- `could_not_resolve`: `true` if the value is missing, unverifiable, or cannot be determined reliably
- `unresolved_cause`: a brief explanation if the request could not be resolved

## Rules
- Rely on internal knowledge only for unchanging historical facts. In all other cases, do a web search to retrieve the necessary information.
- After searching, make sure the results truly match the user's request. If not, set `could_not_resolve` to `true`.
- Do not guess, fabricate, or complete missing information based on assumptions. If a value cannot be determined reliably, set `could_not_resolve` to `true`.
- Never include internal field names, record IDs, or system-specific labels in your final value.
- Before resolving any value, verify that the entity (company, product, location, or other referenced subject) exists in reality or is verifiable.
- If the entity is fictional, unknown, or unverifiable, do not attempt to guess or fabricate any values.
- In such cases, set `value: null`, `could_not_resolve: true`, and include a `resolution_note`.
- Answer in the same language as the user’s request, unless the task explicitly asks for an output in another language.
"""

OPENAI_ENDPOINT = '/responses'
OPENAI_MODEL = 'gpt-4.1'  # prompts are usually tweaked for a model. Double check behavior if changed.


class UnresolvedQuery(UserError):
    pass


def get_ai_value(record, field_type, user_prompt, context_fields, allowed_values):
    """Query a LLM with the given prompt and return the cast value.

    :param record: the record for which the value should be obtained
    :param field_type: the field type for which the response should be cast
    :param user_prompt: the "user prompt" to pass to the LLM (the request)
    :param context_fields: list of field paths that needs to be included in the context dict
    :param allowed_values: a dict containing the values that are allowed

    :return: the value with the type expected for the given field type, or False if the value
        could not be cast or is not in allowed_values
    """
    if field_type in ('many2many', 'many2one', 'selection', 'tags') and not allowed_values:
        raise UnresolvedQuery(record.env._("No allowed values are provided in the prompt."))
    record_context, files = record._get_ai_context(context_fields)
    llm_api = LLMApiService(record.env, 'openai')
    if field_type == 'boolean':
        field_schema = {
            'type': 'boolean',
        }
    elif field_type == 'char':
        field_schema = {
            'type': 'string',
            'description': 'A short, concise string, without any Markdown formatting.'
        }
    elif field_type == 'date':
        field_schema = {
            'type': ['string', 'null'],
            'format': 'date',
            'description': 'A date (year, month and day should be correct), or null to leave empty',
        }
    elif field_type == 'datetime':
        field_schema = {
            'type': ['string', 'null'],
            'format': 'date-time',
            'description': 'A datetime (year, month and day should be correct), including the correct timezone or null to leave empty'
        }
    elif field_type == 'integer':
        field_schema = {
            'type': 'integer',
            'description': "A whole number. If a number is expressed in words (e.g. '6.67 billion'), it must be converted into its full numeric form (e.g. '6670000000')"
        }
    elif field_type in ('float', 'monetary'):
        field_schema = {
            'type': 'number'
        }
    elif field_type == 'html':
        field_schema = {
            'type': 'string',
            'description': 'A well-structured Markdown (it may contain tables). It will be converted to HTML after generation'
        }
    elif field_type == 'text':
        field_schema = {
            'type': 'string',
            'description': 'A few sentences, without any Markdown formatting'
        }
    elif field_type == 'many2many':
        field_schema = {
            'type': 'array',
            'items': {
                'type': 'integer',
                'enum': list(allowed_values)
            },
            'description': 'The list of IDs of records to select. Leave empty to leave the field empty'
        }
    elif field_type == 'many2one':
        field_schema = {
            'type': ['integer', 'null'],
            'enum': list(allowed_values) + [None],
            'description': 'The ID of the record to select. null to leave the field empty if no value matches the user query'
        }
    elif field_type == 'selection':
        field_schema = {
            'type': ['string', 'null'],
            'enum': list(allowed_values) + [None],
            'description': 'Key of the value to select. null to leave the field empty'
        }
    elif field_type == 'tags':
        field_schema = {
            'type': 'array',
            'items': {
                'type': 'string',
                'enum': list(allowed_values)
            },
            'description': 'List of keys of the tags to select. Leave empty to leave the field empty'
        }
    else:
        field_schema = {'type': 'text'}

    schema = {
        'type': 'object',
        'properties': {
            'value': field_schema,
            'could_not_resolve': {
                'type': 'boolean',
                'description': 'True if the model could not confidently determine a value due to missing information, ambiguity, or unknown references in the input.'
            },
            'unresolved_cause': {
                'type': ['string', 'null'],
                'description': 'Short explanation of what is missing or why no value could be generated. Required if could_not_resolve is true.'
            },
        },
        'required': ['value', 'could_not_resolve', 'unresolved_cause'],
        'additionalProperties': False
    }

    instructions = f"{AI_FIELDS_INSTRUCTIONS}\n# Context"
    if allowed_values:
        instructions += f"\n## Allowed Values\n{json.dumps(allowed_values)}"
    instructions += f"\n The current date is {datetime.now(pytz.utc).astimezone().replace(second=0, microsecond=0).isoformat()}"

    if record_context != '{}':
        user_prompt += f"\n# Context Dict\n{record_context}"
        user_prompt += f"\nThe current record is {{'model': {record._name}, 'id': {record.id}}}"

    try:
        response, *__ = llm_api._request_llm(
            llm_model=OPENAI_MODEL,
            system_prompts=[instructions],
            user_prompts=[user_prompt],
            files=files,
            schema=schema,
            web_grounding=True,
        )
    except requests.exceptions.Timeout:
        raise UserError(record.env._("Oops, the request timed out."))
    except requests.exceptions.ConnectionError:
        raise UserError(record.env._("Oops, the connection failed."))

    if not response:
        raise UserError(record.env._("Oops, an unexpected error occurred."))

    try:
        response = json.loads(response[0], strict=False)
    except json.JSONDecodeError:
        raise UserError(record.env._("Oops, the response could not be processed."))
    if response.get('could_not_resolve'):
        raise UnresolvedQuery(response.get('unresolved_cause'))

    return parse_ai_response(
        response.get('value'),
        field_type,
        allowed_values,
    )


def get_field_prompt_vals(env, field, field_prompt=None):
    """Get the parsed prompt, the field paths inserted in the prompt and the allowed values for the
    given field. If field_prompt is given, the values are obtained from this prompt instead of the
    one defined on the field.

    :param field: the field from which to get the values
    :param field_prompt: prompt to use instead of the one defined on the field

    :return: (user_prompt, fields, allowed_values)
    """
    user_prompt, fields, allowed_values = parse_ai_prompt_values(env, field_prompt or field.ai, field.comodel_name)
    if field.type == 'selection':
        allowed_values = field._selection
    return user_prompt, fields, allowed_values  # do we need html_to_inner_content?


def get_property_prompt_vals(env, property_definition):
    """Get the parsed prompt, the field paths inserted in the prompt and the allowed values for the
    given property_definition.

    :param property_definition: the property definition from which to get the values

    :return: (user_prompt, fields, allowed_values)
    """
    property_type = property_definition.get('type')
    user_prompt = property_definition.get('system_prompt')
    user_prompt, fields, allowed_values = parse_ai_prompt_values(env, user_prompt, property_definition.get('comodel'))
    if property_type == 'selection':
        allowed_values = dict(property_definition.get('selection', {}))
    elif property_type == 'tags':
        allowed_values = {name: label for name, label, color in (property_definition.get('tags') or [])}
    return user_prompt, fields, allowed_values  # do we need html_to_inner_content?


def parse_ai_prompt_values(env, prompt, comodel, replace_prompt=True):
    """Parse the given prompt to extract the inserted field paths and record references.
    Replace fields paths by {{path}} placeholders and records by their display names if
    replace_prompt is True.

    Considering the following prompt:
    <p>
        Based on the document <span data-ai-field="attachment_id">Content</span> and
        <span data-ai-field="name">Name</span>, place it inside
        <span data-ai-record-id="17">Finance</span> or <span data-ai-record-id="19">Billing</span>
    </p>
    Where
    - "attachment_id" and "name" are inserted in the prompt by the end user with the /field command
    and are extracted and returned by this method so that they can be validated (ensure read access
    when the end user edits the prompt) or interpreted and added as context to the LLM to resolve
    the user query.

    - "Finance" and "Billing" records are inserted in the prompt by the end user with the /record
    command and are extracted and returned by this method so that they can be validated (ensure
    read access when the end user edits the prompt) or added as allowed values when resolving the
    user query (for relational fields)

    The method will return (prompt, field_paths, formatted_allowed_records|inserted_record_ids) as
    follows:
    - prompt: either the original prompt, either a cleaned prompt (field path replaced by brackets,
        html to text, records replaced by their display names) based on replace_prompt
    - field_paths: list of field paths from the prompt (from example: ['attachment_id', 'name'])
    - formatted_allowed_records: dict of allowed existing records from the prompt formatted with
        :meth:`_ai_format_records` if replace_prompt is True
    - inserted_record_ids: set of record ids inserted in the prompt, if replace_prompt is False
        (used for validation, should not filter non-existing records to raise missing errors)
    """
    tree = html.fromstring(prompt)

    prompt_fields = set()
    for prompt_field_element in tree.xpath('//span[@data-ai-field]'):
        field_path = prompt_field_element.attrib.get('data-ai-field')
        if replace_prompt:
            if field_path:
                prompt_field_element.text = f"{{{{{field_path}}}}}"
            else:
                prompt_field_element.drop_tree()
        prompt_fields.add(field_path)

    inserted_record_ids = set()
    formatted_allowed_records = {}
    if comodel:
        inserted_record_elements = tree.xpath('//span[@data-ai-record-id]')
        inserted_record_ids = {
            int(record_id)
            for inserted_record_element
            in inserted_record_elements
            if (record_id := inserted_record_element.attrib.get('data-ai-record-id'))
        }
        if replace_prompt:
            allowed_records_by_id = env[comodel].browse(inserted_record_ids).exists().grouped("id")
            for inserted_record_element in inserted_record_elements:
                if allowed_record := allowed_records_by_id.get(int(inserted_record_element.attrib.get('data-ai-record-id'))):
                    inserted_record_element.text = allowed_record._ai_truncate(allowed_record.display_name)
                else:
                    inserted_record_element.drop_tree()
            formatted_allowed_records = env[comodel].browse(allowed_records_by_id.keys())._ai_format_records()

    if replace_prompt:
        return html_to_inner_content(html.tostring(tree, encoding='unicode')), prompt_fields, formatted_allowed_records
    return prompt, prompt_fields, inserted_record_ids


def parse_ai_response(response, field_type, allowed_values):
    """Parse and cast a LLM response into the type expected for the given field type and checks
    that the value is in the set of allowed_values if given.

    :param response: a LLM response
    :param str field_type: the type of the field for which the response should be cast
    :param set allowed_values: a set of values that are allowed

    :return: the value with the type expected for the given field type, or False if the value
        could not be cast or is not in allowed_values
    """
    if not allowed_values:
        allowed_values = {}

    if field_type == 'datetime':
        if not response:
            return False
        try:
            return fields.Datetime.to_string(isoparse(response).astimezone(pytz.utc))
        except ValueError:
            return False
        return response
    elif field_type == 'date':
        if not response:
            return False
        try:
            return fields.Datetime.to_string(isoparse(response))
        except ValueError:
            return False
        return response
    elif field_type in ('selection', 'many2one'):
        return response if response in allowed_values else False
    elif field_type in ('tags', 'many2many'):
        return [value for value in response if value in allowed_values]
    elif field_type == 'html':
        if markdown:
            raw_html = markdown(response, extras=['fenced-code-blocks', 'tables', 'strike']).rstrip('\n')
            return html_sanitize(raw_html or "")
        return html_sanitize(response or "")
    else:
        return response


def ai_field_insert(field_path, field_label):
    return Markup('<span data-ai-field="%s">%s</span>') % (field_path, field_label)

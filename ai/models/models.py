# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import datetime
import pytz
import json

from odoo import models
from odoo.models import NewId
from odoo.exceptions import AccessError
from odoo.tools import OrderedSet
from odoo.tools.mail import html_to_inner_content
from odoo.tools.misc import formatLang
from odoo.tools.mimetypes import guess_mimetype

AI_SUPPORTED_IMG_TYPES = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


class Model(models.AbstractModel):
    _inherit = 'base'

    def _ai_truncate(self, value, size=60):
        # Limit the size of the field we can, to try to limit prompt injection...
        if not isinstance(value, str) or len(value) < size:
            return value
        return value[:max(0, size - 3)] + "..."

    def _ai_field_names_to_truncate(self):
        return ('name', 'display_name')

    def _ai_serialize_fields_data(self):
        fields_info = self.fields_get()
        result = {}

        for field_name, field_attrs in fields_info.items():
            field_type = field_attrs["type"]
            field_value = self[field_name]

            if field_type == 'char' and field_name in self._ai_field_names_to_truncate():
                field_value = self._ai_truncate(field_value)

            try:
                # Handle relational fields
                if field_type == "many2one":
                    result[field_name] = (
                        self._ai_truncate(field_value.display_name) if field_value else None
                    )
                elif field_type in ["one2many", "many2many"]:
                    linked_records = self.env[field_value._name].browse(field_value.ids)
                    if (
                        len(linked_records) > 50
                    ):  # there have been cases were too many linked records have flooded the context - avoid that by filtering them out
                        continue
                    else:
                        result[field_name] = [
                            self._ai_truncate(record.display_name) for record in linked_records
                        ]
                elif field_type == "binary":
                    continue  # we don't include binary fields in the record info JSON
                else:
                    # Handle basic field types (dates, etc.)
                    if isinstance(field_value, datetime.datetime):
                        user_tz = pytz.timezone(self.env.user.tz)
                        result[field_name] = (
                            field_value.astimezone(user_tz).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            if field_value
                            else None
                        )
                    elif isinstance(field_value, models.BaseModel):
                        # Handle unexpected recordset returns (shouldn't happen for non-relational fields)
                        result[field_name] = field_value.ids
                    else:
                        result[field_name] = field_value
            except AccessError:  # if the user doesn't have access to a field, don't include it in the AI's context
                continue

        return json.dumps(result, default=str)

    def _ai_initialise_context(
        self, caller_component, text_selection=None, front_end_info=None
    ):
        context = []

        # If we have record info available from the front-end, pass it to the model's context
        if caller_component in ["html_field_record", "chatter_ai_button"]:
            context.append(f"You were called within an Odoo {self._name} record. Your answers should take the record's details into account. The following JSON contains all of the record's details: {front_end_info}")

        # If we don't have record info from the front-end and it's required, fetch the record information and pass it to the model's context
        if caller_component == "mail_composer":
            context.append(f"You were called within an Odoo {self._name} record. Your answers should take the record's details into account. The following JSON contains all of the records details: {self._ai_serialize_fields_data()}")

        # Add some additional details for some special cases and finish the context by the "first" message sent by the assistant
        if caller_component == "html_field_text_select":
            context.append(f"The text that you will be rewritting is the following: {text_selection}")
        else:
            context.append("ALWAYS FORMAT YOUR ANSWERS USING MARKDOWN, AVOID USING HTML. Don't use unecessary formatting like code blocks if not needed.")

        return context

    ################
    #  Extensions  #
    ################
    def _ai_read(self, fnames, files_dict):
        """Retrieve and format field values for LLM processing.
        If no field names are given, return the display name.
        This method can be overridden on any model that requires sending more than just the display
        name when its records are included in a prompt (such as attachments).
        Files are handled separately, as they must be sent independently to LLMs.

        :param fnames: list of field names to read and format
        :param files_dict: dict mapping file checksums to metadata dicts each with keys:
            'mimetype', 'value', and 'file_ref'

        :return: (vals_list, files_dict) where vals_list is a list of dicts mapping field names to
            their formatted values with one dictionary per record, and files_dict is a dict mapping
            file checksums to metadata dicts each with keys 'mimetype', 'value' and 'fileref'
        """
        if not fnames:
            fnames = ['display_name']  # by default, send display names
        vals_list = self.read(fnames, load=None)
        for fname in fnames:
            field = self._fields.get(fname)
            if field.type in ('binary', 'image'):
                if field.attachment and self.ids:  # attachment is not created yet in quick creation
                    attachments = self.env['ir.attachment'].search([
                        ('res_model', '=', self._name),
                        ('res_field', '=', fname),
                        ('res_id', 'in', self.ids)  # ._origin?
                    ])
                    __, files_dict = attachments._ai_read(None, files_dict)  # populate file dict
                    attachments_by_resid = {att.res_id: att for att in attachments}
                    for vals in vals_list:
                        if not vals[fname] or (res_id := vals['id'] or vals['id'].origin) not in attachments_by_resid:
                            continue
                        vals[fname] = files_dict[attachments_by_resid[res_id].checksum]['file_ref']
                else:
                    for vals in vals_list:
                        if not vals[fname]:
                            continue
                        checksum = self.env['ir.attachment']._compute_checksum(vals[fname])
                        if checksum not in files_dict:
                            raw = base64.b64decode(vals[fname])
                            mimetype = guess_mimetype(raw)
                            extension = mimetype.split("/")[-1]
                            file_ref = f'<file_#{len(files_dict) + 1}>'
                            if extension in (*AI_SUPPORTED_IMG_TYPES, 'pdf'):
                                # todo: keep 5 pages max and resize images
                                value = vals[fname].decode()
                            else:
                                try:
                                    value = self.env['ir.attachment']._index(vals[fname], mimetype, checksum=checksum)
                                except TypeError:
                                    value = self.env['ir.attachment']._index(vals[fname], mimetype)
                            files_dict[checksum] = {
                                'mimetype': mimetype,
                                'value': value,
                                'file_ref': file_ref,
                            }
                        vals[fname] = files_dict[checksum]['file_ref']
            elif field.type in ('date', 'datetime'):
                for vals in vals_list:
                    vals[fname] = field.to_string(vals[fname])
            elif field.type == 'html':
                for vals in vals_list:
                    vals[fname] = html_to_inner_content(vals[fname])
            elif field.type in ('many2many', 'many2one', 'many2one_reference', 'one2many', 'reference'):
                # can't use result of read because we might have temporary records (with NewId), so
                # the ids won't be the ids we expect (origin ids or none for virtual records)
                vals_by_ids = {vals['id']: vals for vals in vals_list}
                for record in self:
                    record_vals = vals_by_ids[record.id]
                    co_records = record[fname]
                    if not co_records:
                        record_vals[fname] = False  # keep falsy values consistent for the LLM
                    if field.type == 'many2one_reference':
                        record_vals[fname] = {'model': model, 'ids': record_vals[fname]} if (model := record[field.model_field]) else False
                    else:
                        record_vals[fname] = {'model': co_records._name, 'ids': co_records._ids}
            elif field.type == 'monetary':
                currency_field = field.get_currency_field(self)
                if currency_field:
                    currency = self[currency_field]
                    for vals in vals_list:
                        vals[fname] = formatLang(self.env, vals[fname], currency_obj=currency)
            elif field.type == 'char' and field.name in self._ai_field_names_to_truncate():
                for vals in vals_list:
                    vals[fname] = self._ai_truncate(vals[fname])

        return vals_list, files_dict

    def _get_ai_context(self, field_paths):
        """ Get the json-encoded context dict for a record given a list of field paths.
        The context dict is a mini-orm snapshot with values formatted for LLM usage.
        It is a dictionary of the form:

        .. code-block:: python

            {
                "model_A": [
                    {
                        "id": 1,
                        "field_A": "val_1",
                        "field_B": {"model": "model_B", "ids": [3]},
                    },
                    {
                        "id": 2,
                        "field_A": "val_2",
                        "field_B": {"model": "model_B", "ids": [4]},
                    }
                ],
                "model_B": [
                    {
                        "id": 3,
                        "field_C": "val_3"
                    },
                    {
                        "id": 4,
                        "field_C": "val_4"
                    }
                ]
            }
        """
        self.ensure_one()
        models = {}

        def _map_to_models(records, path):
            model = records._name
            ids = OrderedSet(records._ids)
            if model not in models:
                models[model] = {'fields': OrderedSet(), 'ids': ids}
            else:
                models[model]['ids'] |= ids
            if not path:
                return
            fname = path[0]
            field = records._fields.get(fname)
            if not field:
                return
            if field.type in ('many2many', 'many2one', 'one2many'):
                _map_to_models(records[fname], path[1:])
            elif field.type == 'reference':
                for record in records:
                    if record[fname]:
                        _map_to_models(record[fname], path[1:])
            elif field.type == 'many2one_reference':
                for record in records:
                    if (ref_model := record[field.model_field]) and (ref_id := record[fname]):
                        _map_to_models(self.env[ref_model].browse(ref_id), path[1:])
            models[model]['fields'].add(fname)

        # get a mapping {model: {fields, ids}} to know which fields to read on which records
        for path in field_paths:
            _map_to_models(self, path.split("."))

        snapshot = {}
        files_dict = {}  # files are sent separately to LLMs
        for model, info in models.items():
            records = self.env[model].browse(info['ids'])
            snapshot[model], files_dict = records._ai_read(info['fields'], files_dict)

        def _ai_context_json_default(obj):
            """NewId is not json serializable, use its string representation"""
            if isinstance(obj, NewId):
                return obj.origin or str(obj)
            return obj

        return json.dumps(snapshot, default=_ai_context_json_default, ensure_ascii=False, indent=2), list(files_dict.values())

    def _ai_format_records(self):
        """Format what will be in the prompt when we inserted records.

        It needs to return a dict which keys are the records ids, and
        the value of the dict can be anything.
        """
        return {record.id: record.display_name for record in self}

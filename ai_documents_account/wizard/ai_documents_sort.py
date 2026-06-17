# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import Command, api, models
from odoo.addons.ai_fields.tools import ai_field_insert


class AiDocumentsSort(models.TransientModel):
    _inherit = "ai_documents.sort"

    @api.model
    def default_get(self, fields):
        values = super().default_get(fields)
        _ = self.env._

        if "ai_sort_prompt" not in fields:
            return values

        if "folder_id" in values:
            existing_ir_action = self.env["ir.actions.server"].search(
                [("ai_autosort_folder_id", "=", values["folder_id"])],
                limit=1,
            )

            if existing_ir_action:
                # Don't set the default prompt
                return values

        if "ai_tool_ids" not in values:
            values["ai_tool_ids"] = [Command.set([])]

        create_vendor_bill = self.env.ref("documents_account.ir_actions_server_create_vendor_bill_code", raise_if_not_found=False)
        create_customer_invoice = self.env.ref("documents_account.ir_actions_server_create_customer_invoice_code", raise_if_not_found=False)
        prompt_lines = []
        if create_customer_invoice:
            prompt_lines.append(_("If it is a customer invoice, trigger the action to create one."))
            values["ai_tool_ids"][0][2].append(create_customer_invoice.id)

        if create_vendor_bill:
            prompt_lines.append(
                _(
                    "If the customer is %s it means it is a vendor bill, trigger the Create Vendor Bill action.",
                    ai_field_insert("company_id.name", _("Company > Name")),
                ),
            )
            values["ai_tool_ids"][0][2].append(create_vendor_bill.id)

        if values.get("ai_sort_prompt", ""):
            prompt_lines.append(_("Otherwise, %s", values.get("ai_sort_prompt", "")))

        # Change the default value for the prompt
        values["ai_sort_prompt"] = Markup("<br/>").join(prompt_lines)
        return values

    @api.model
    def _activate_demo_prompt(self, folder_id):
        """Activate the default prompt on the given folder."""
        _ = self.env._
        create_vendor_bill = self.env.ref(
            "documents_account.ir_actions_server_create_vendor_bill_code",
            raise_if_not_found=False,
        )
        create_customer_invoice = self.env.ref(
            "documents_account.ir_actions_server_create_customer_invoice_code",
            raise_if_not_found=False,
        )
        add_tags = self.env.ref("ai_documents.ir_actions_server_add_tags", raise_if_not_found=False)
        finance_folder = self.env.ref("documents.document_finance_folder", raise_if_not_found=False)
        legal_folder = self.env.ref("documents.document_legal_folder", raise_if_not_found=False)
        insurances_folder = self.env.ref("documents.document_insurances_folder", raise_if_not_found=False)
        ai_folder_insert = self.env["documents.document"]._ai_folder_insert

        ai_tool_ids = self.env["ir.actions.server"]

        move_in_folder = self.env.ref(
            "ai_documents.ir_actions_server_move_in_folder",
            raise_if_not_found=False,
        )
        if move_in_folder:
            ai_tool_ids |= move_in_folder

        prompt_lines = []
        if add_tags:
            prompt_lines.append(Markup("""
                <div>%(instruction_1)s<br/><div>
                <div>%(instruction_2)s<div>
                <ul>
                    <li>%(instruction_3)s</li>
                    <li>%(instruction_4)s</li>
                </ul>
            """) % {
                "instruction_1": _("First, check the file to see if it contains a single document or if several documents are collated together."),
                "instruction_2": _("For this, use this field: %s", ai_field_insert("is_multipage", _("Is considered multipage"))),
                "instruction_3": _(
                    """If it is true, add the tag %(b_open)s"To Split"%(b_close)s and stop there. This way, we'll know we first need to manually split it into different files.""",
                    b_open=Markup("<b>"),
                    b_close=Markup("</b>"),
                ),
                "instruction_4": _("If it is false, continue with the normal process"),
            })
            ai_tool_ids |= add_tags

        if finance_folder:
            finance_lines = []
            if create_vendor_bill:
                finance_lines.append(
                    Markup("<li>%s</li>")
                    % _(
                        "If the customer of the invoice is us (%(company_name)s, with email %(company_email)s), create a Vendor Bill.",
                        company_name=ai_field_insert("ai_document_or_env_company_id.name", _("Company > Name")),
                        company_email=ai_field_insert("ai_document_or_env_company_id.email", _("Company > Email")),
                    ),
                )
                ai_tool_ids |= create_vendor_bill
            if create_customer_invoice:
                finance_lines.append(
                    Markup("<li>%s</li>")
                        % _(
                            "If the customer is %(b_open)sanyone else%(b_close)s, create a Customer Invoice.",
                            b_open=Markup("<b>"),
                            b_close=Markup("</b>"),
                        ),
                )
                ai_tool_ids |= create_customer_invoice

            prompt_lines.append(
                Markup("""
                    <div>%(instruction)s</div>
                    <ul>
                        %(finance_lines)s
                    </ul>
                """)
                % {
                    "instruction":
                        _(
                            "If the document is an %(b_open)sinvoice%(b_close)s, move it to the %(finance)s folder then trigger the relevant action:",
                            b_open=Markup("<b>"),
                            b_close=Markup("</b>"),
                            finance=ai_folder_insert(finance_folder.id),
                        ),
                    "finance_lines": Markup("").join(finance_lines),
                },
            )

        prompt_lines.append(Markup("""
            <div>%(instruction_1)s</div>
            <ul>
                <li>%(instruction_2)s</li>
                <li>%(instruction_3)s</li>
            </ul>
        """) % {
            "instruction_1": _(
                "If the document is %(b_open)snot an invoice%(b_close)s, move it to the correct folder:",
                b_open=Markup("<b>"),
                b_close=Markup("</b>"),
            ),
            "instruction_2": _(
                "%(b_open)sContracts & NDAs%(b_close)s go to the %(legal)s folder.",
                b_open=Markup("<b>"),
                b_close=Markup("</b>"),
                legal=ai_folder_insert(legal_folder.id),
            ),
            "instruction_3": _(
                "%(b_open)sInsurance contracts%(b_close)s go to the %(insurance)s folder.",
                b_open=Markup("<b>"),
                b_close=Markup("</b>"),
                insurance=ai_folder_insert(insurances_folder.id),
            ),
        })

        # Change the default value for the prompt
        self.create({
            "folder_id": folder_id,
            "ai_sort_prompt": Markup("<br/>").join(prompt_lines),
            "ai_tool_ids": ai_tool_ids.ids,
        }).action_setup_folder()

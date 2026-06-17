/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { AiPrompt } from "./ai_prompt";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

export class AiPromptField extends Component {
    static template = "ai.AiPromptField";
    static props = {
        ...standardFieldProps,
        // Field containing the model name that will be updated
        modelReferenceField: { type: String },
        // Field containing the field name that will be updated
        fieldReferenceField: { type: String, optional: true },

        placeholder: { type: String, optional: true },

        // If we update a relational field, field containing the model for which we will choose candidate values
        recordSelectorRelationField: { type: String, optional: true },
        recordSelectorDomain: { type: String, optional: true },

        showMissingRecordsWarning: { Boolean: String, optional: true },
    };
    static components = { AiPrompt };

    get updatedFieldName() {
        return this.props.record.data[this.props.fieldReferenceField];
    }

    get recordSelectorRelation() {
        return this.props.record.data[this.props.recordSelectorRelationField];
    }

    get missingRecordsMessage() {
        return _t("Insert records the AI can use with the '/record' command");
    }

    get modelName() {
        return this.props.record.data[this.props.modelReferenceField];
    }

    get prompt() {
        return this.props.record.data[this.props.name] || "";
    }

    onChange() {
        this.props.record.model.bus.trigger("FIELD_IS_DIRTY", true);
    }

    updatePrompt(value) {
        if (value !== this.prompt) {
            this.props.record.update({ [this.props.name]: value });
        }
    }
}

export const aiPrompt = {
    component: AiPromptField,
    supportedTypes: ["html"],
    additionalClasses: ["d-inline"],

    extractProps: ({ attrs, options }) => {
        return {
            placeholder: attrs.placeholder,
            modelReferenceField: options.model_reference_field,
            fieldReferenceField: options.field_reference_field,
            recordSelectorRelationField: options.record_selector_relation_field,
            recordSelectorDomain: options.record_selector_domain,
            showMissingRecordsWarning: Boolean(options.show_missing_records_warning),
        };
    },
};

registry.category("fields").add("ai_prompt", aiPrompt);

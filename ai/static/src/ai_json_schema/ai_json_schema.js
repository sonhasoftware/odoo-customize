/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
import { Component, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useAutoresize } from "@web/core/utils/autoresize";
import { useService } from "@web/core/utils/hooks";

/**
 * Widget to edit the JSON schema sent to the LLM provider.
 *
 * See https://json-schema.org/understanding-json-schema/reference
 */
export class AiJsonSchema extends Component {
    static template = "ai.AiJsonSchema";
    static props = { ...standardFieldProps };

    setup() {
        this.tableEl = useRef("table");
        this.textareaEl = useRef("textarea");
        this.notification = useService("notification");
        this.state = useState({
            technical_mode: false,
            // There's no order in the arguments, so we try to not move them when editing
            orderArguments: Object.keys(this.value?.properties || {}).sort(),
        });
        useAutoresize(this.textareaEl);
    }

    get types() {
        return [
            ["boolean", "Boolean"],
            ["integer", "Integer"],
            ["number", "Number"],
            ["string", "String"],
            ["enum_integer", "Integer Enum"],
            ["enum_number", "Number Enum"],
            ["enum_string", "String Enum"],
            ["regex", "Regex"],
            ["array_boolean", "Array of Boolean"],
            ["array_integer", "Array of Integer"],
            ["array_number", "Array of Number"],
            ["array_string", "Array of String"],
        ];
    }

    get value() {
        let value;
        try {
            value = JSON.parse(this.props.record.data[this.props.name] || "{}");
        } catch {
            value = {};
        }
        const defaultKeys = {
            properties: {},
            required: [],
            type: "object",
        };
        return { ...defaultKeys, ...value };
    }

    get arguments() {
        const value = this.value;
        if (!value) {
            return [];
        }
        const required = value.required || [];
        const keys = Object.keys(value.properties).sort(
            (a, b) => this.state.orderArguments.indexOf(a) - this.state.orderArguments.indexOf(b)
        );
        return keys.map((k) => [
            k,
            value.properties[k],
            required.includes(k),
            this.getEffectiveType(value.properties[k]),
        ]);
    }

    getEffectiveType(properties) {
        if (
            properties.enum !== undefined &&
            ["integer", "number", "string"].includes(properties.type)
        ) {
            return `enum_${properties.type}`;
        }
        if (properties.pattern !== undefined) {
            return "regex";
        }
        if (
            properties.type === "array" &&
            ["boolean", "integer", "number", "string"].includes(properties.items.type)
        ) {
            return `array_${properties.items.type}`;
        }
        return properties.type;
    }

    onNameChange(newName, oldName, target) {
        const recordValue = this.value;
        if (recordValue.properties[newName]) {
            this.notification.add(_t("The name should be unique"), { type: "warning" });
            target.value = oldName;
            return;
        }
        recordValue.properties[newName] = recordValue.properties[oldName];
        delete recordValue.properties[oldName];
        recordValue.required = recordValue.required.map((n) => (n === oldName ? newName : n));
        this.state.orderArguments = this.state.orderArguments.map((n) =>
            n === oldName ? newName : n
        );
        this.props.record.update({ [this.props.name]: JSON.stringify(recordValue) });
    }

    onDescriptionChange(value, name) {
        const recordValue = this.value;
        recordValue.properties[name].description = value;
        this.props.record.update({ [this.props.name]: JSON.stringify(recordValue) });
    }

    onTypeChange(value, name) {
        const recordValue = this.value;

        delete recordValue.properties[name].enum;
        delete recordValue.properties[name].pattern;
        delete recordValue.properties[name].items;
        delete recordValue.properties[name].maxLength;

        if (value.startsWith("enum_")) {
            recordValue.properties[name].type = value.split("_").at(-1);
            recordValue.properties[name].enum = [];
        } else if (value === "regex") {
            recordValue.properties[name].type = "string";
            recordValue.properties[name].pattern = "";
        } else if (value.startsWith("array_")) {
            recordValue.properties[name].type = "array";
            recordValue.properties[name].items = { type: value.split("_").at(-1) };
        } else {
            recordValue.properties[name].type = value;
        }

        if (value === "string") {
            recordValue.properties[name].maxLength = 60;
        }
        this.props.record.update({ [this.props.name]: JSON.stringify(recordValue) });
    }

    onEnumChange(value, name) {
        const recordValue = this.value;
        const cast =
            {
                integer: (v) => parseInt(v) || 0,
                number: (v) => parseFloat(v) || 0.0,
            }[recordValue.properties[name].type] || ((v) => v);
        recordValue.properties[name].enum = (value || "").split(",").map((v) => cast(v.trim()));
        this.props.record.update({ [this.props.name]: JSON.stringify(recordValue) });
    }

    onRegexChange(value, name) {
        const recordValue = this.value;
        recordValue.properties[name].type = "string";
        recordValue.properties[name].pattern = value;
        this.props.record.update({ [this.props.name]: JSON.stringify(recordValue) });
    }

    onMaxLengthChange(maxLength, name) {
        maxLength = parseInt(maxLength);
        const recordValue = this.value;
        if (!maxLength) {
            delete recordValue.properties[name].maxLength;
        } else {
            recordValue.properties[name].maxLength = maxLength;
        }
        this.props.record.update({ [this.props.name]: JSON.stringify(recordValue) });
    }

    onRequiredChange(value, name) {
        const recordValue = this.value;
        if (!value) {
            recordValue.required = recordValue.required.filter((n) => n !== name);
        } else if (!recordValue.required.includes(name)) {
            recordValue.required.push(name);
        }
        this.props.record.update({ [this.props.name]: JSON.stringify(recordValue) });
    }

    onDelete(name) {
        const recordValue = this.value;
        recordValue.required = recordValue.required.filter((n) => n !== name);
        this.state.orderArguments = this.state.orderArguments.filter((n) => n !== name);
        delete recordValue.properties[name];
        this.props.record.update({
            [this.props.name]: Object.keys(recordValue.properties).length
                ? JSON.stringify(recordValue)
                : false,
        });
    }

    onNewArgument() {
        const recordValue = this.value;
        if (recordValue.properties[""]) {
            this.tableEl.el.querySelector("td:first-child input:placeholder-shown").focus();
            return;
        }
        recordValue.properties[""] = { type: "string", maxLength: 60 };
        if (!recordValue.required.includes("")) {
            recordValue.required.push("");
        }
        this.state.orderArguments.push("");
        this.props.record.update({ [this.props.name]: JSON.stringify(recordValue) });
    }

    onBlur(ev) {
        const value = ev.target.value;
        this.props.record.update({ [this.props.name]: value });
    }
}

const aiJsonSchema = {
    component: AiJsonSchema,
};

registry.category("fields").add("ai_json_schema", aiJsonSchema);

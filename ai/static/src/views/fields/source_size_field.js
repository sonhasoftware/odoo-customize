/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { formatFloat } from "@web/core/utils/numbers";
import { IntegerField } from "@web/views/fields/integer/integer_field";

export class SourceSizeIntegerField extends IntegerField {
    get formattedValue() {
        if (!this.value) {
            return "";
        }
        return `${formatFloat(this.value, { humanReadable: true })}B`;
    }
}

const sourceSizeIntegerField = {
    component: SourceSizeIntegerField,
    displayName: _t("SourceSizeIntegerField"),
    supportedTypes: ["integer"],
};

registry.category("fields").add("source_size", sourceSizeIntegerField);

/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class PreserveWhitespaceField extends Component {
    static template = "sonha_du_an.PreserveWhitespaceField";

    get value() {
        return this.props.record.data[this.props.name] || "";
    }
}

registry.category("fields").add("preserve_whitespace", {
    component: PreserveWhitespaceField,
    supportedTypes: ["char", "text"],
});
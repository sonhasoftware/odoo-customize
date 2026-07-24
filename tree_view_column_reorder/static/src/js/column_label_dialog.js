/** @odoo-module */

import { Dialog } from "@web/core/dialog/dialog";
import { Component, onMounted, useRef, useState } from "@odoo/owl";

export class ColumnLabelDialog extends Component {
    static template = "tree_view_column_reorder.ColumnLabelDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        title: String,
        label: String,
        defaultLabel: String,
        canReset: Boolean,
        save: Function,
        reset: Function,
    };

    setup() {
        this.inputRef = useRef("labelInput");
        this.state = useState({ label: this.props.label, saving: false });
        onMounted(() => {
            const input = this.inputRef.el;
            if (input) {
                input.focus();
                input.setSelectionRange(input.value.length, input.value.length);
            }
        });
    }

    get normalizedLabel() {
        return this.state.label.trim();
    }

    async save() {
        if (!this.normalizedLabel || this.state.saving) {
            return;
        }
        this.state.saving = true;
        const result = await this.props.save(this.normalizedLabel);
        this.state.saving = false;
        if (result) {
            this.props.close();
        }
    }

    async reset() {
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        const result = await this.props.reset();
        this.state.saving = false;
        if (result) {
            this.props.close();
        }
    }
}

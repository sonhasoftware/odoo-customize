/** @odoo-module **/

import { Component, useState, useSubEnv } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class DuAnTreeListRenderer extends ListRenderer {
    static rowsTemplate = "sonha_du_an.DuAnTreeListRenderer.Rows";

    setup() {
        super.setup();
        this.expanded = useState({});
        this.treeInfo = new Map();
        useSubEnv({
            duAnTree: {
                expanded: this.expanded,
                getInfo: (record) => this.treeInfo.get(record.resId),
                toggle: (record) => {
                    this.expanded[record.resId] = !this.expanded[record.resId];
                },
            },
        });
    }

    getVisibleRecords(list) {
        const records = list.records;
        const visible = [];
        const stack = [];
        for (let i = 0; i < records.length; i++) {
            const record = records[i];
            const level = record.data.in_dam;
            while (stack.length && stack[stack.length - 1].level >= level) {
                stack.pop();
            }
            const next = records[i + 1];
            const hasChildren = Boolean(next && next.data.in_dam > level);
            const expanded = hasChildren && Boolean(this.expanded[record.resId]);
            this.treeInfo.set(record.resId, { depth: stack.length, hasChildren });
            if (stack.every((node) => node.expanded)) {
                visible.push(record);
            }
            stack.push({ level, expanded });
        }
        return visible;
    }

    isSortable() {
        return false;
    }
}

export class DuAnTreeNameField extends Component {
    static template = "sonha_du_an.DuAnTreeNameField";
    static props = { ...standardFieldProps };

    setup() {
        this.tree = this.env.duAnTree;
        this.expanded = useState(this.tree ? this.tree.expanded : {});
    }

    get info() {
        return (this.tree && this.tree.getInfo(this.props.record)) || { depth: 0, hasChildren: false };
    }

    get isExpanded() {
        return Boolean(this.expanded[this.props.record.resId]);
    }

    get label() {
        return (this.props.record.data[this.props.name] || "").trim();
    }

    onToggle() {
        this.tree.toggle(this.props.record);
    }
}

registry.category("fields").add("du_an_tree_name", {
    component: DuAnTreeNameField,
    supportedTypes: ["char", "text"],
});

registry.category("views").add("sonha_du_an_tree_list", {
    ...listView,
    Renderer: DuAnTreeListRenderer,
});

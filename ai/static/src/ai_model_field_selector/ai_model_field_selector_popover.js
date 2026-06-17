/** @odoo-module */
import { ModelFieldSelectorPopover } from "@web/core/model_field_selector/model_field_selector_popover";
import { useService } from "@web/core/utils/hooks";

import { useState, onWillStart } from "@odoo/owl";

export class AiModelFieldSelectorPopover extends ModelFieldSelectorPopover {
    static template = "ai.AiModelFieldSelectorPopover";
    static props = {
        ...ModelFieldSelectorPopover.props,
        updateBatch: Function,
        fieldsPath: { type: Array, optional: true },
        aiFieldPath: { type: String, optional: true },
    };
    static defaultProps = {
        ...ModelFieldSelectorPopover.defaultProps,
        readProperty: true,
    };

    setup() {
        super.setup();
        this.aiFieldsState = useState({ selected: [] });

        this.orm = useService("orm");
        this.user = useService("user");

        onWillStart(async () => {
            if (this.props.fieldsPath) {
                await this._loadFields(this.props.fieldsPath);
            }
        });
        this.isTemplateEditor = null;
        this.allowedQwebExpressions = null;
        return super.setup();
    }

    get fieldNames() {
        const selected = this.aiFieldsState.selected.map((s) => s.map((f) => f.name).join("."));

        // Can not use `page.path`, because properties have custom code
        const currentPath = [];
        let page = this.state.page.previousPage;
        while (page) {
            currentPath.push(page.selectedName);
            page = page.previousPage;
        }
        const currentPathStr = currentPath.reverse().join(".");

        return super.fieldNames.filter((f) => {
            const path = currentPathStr ? `${currentPathStr}.${f}` : f;
            if (selected.includes(path) || currentPathStr === f) {
                return false;
            }
            if (this.props.aiFieldPath && this.props.aiFieldPath === path) {
                return false;
            }
            return true;
        });
    }

    async selectField(field) {
        if (field.type === "properties") {
            return this.followRelation(field);
        }
        this.state.page.selectedName = field.name;
        const fullPath = this.state.page.path;
        if (this.aiFieldsState.selected.find((f) => f[0] === fullPath)) {
            return;
        }

        this.keepLast.add(Promise.resolve());

        this.aiFieldsState.selected.push([...this.fieldsChain, field]);

        if (!(await user.hasGroup("mail.group_mail_template_editor"))) {
            // If the user is not template editor, he won't be able to select many fields
            this.onInsert();
        }
    }

    get fieldsChain() {
        let page = this.state.page.previousPage;
        const fieldsChain = [];
        while (page) {
            fieldsChain.push(page.fieldDefs[page.selectedName]);
            page = page.previousPage;
        }
        return fieldsChain.reverse();
    }

    onInsert() {
        this.props.updateBatch(this.aiFieldsState.selected);
        this.props.close();
    }

    onRemoveField(path) {
        this.aiFieldsState.selected = this.aiFieldsState.selected.filter((f) => f[0] !== path);
    }

    async beforeFilter() {
        if (this.isTemplateEditor === null) {
            const getAllowedQwebExpressions = this.env.services["allowed_qweb_expressions"];
            this.isTemplateEditor = await user.hasGroup("mail.group_mail_template_editor");
            this.allowedQwebExpressions = await getAllowedQwebExpressions(this.props.resModel);
        }
    }

    async followRelations() {
        await this.beforeFilter();
        return super.followRelations(...arguments);
    }
    async loadPages() {
        await this.beforeFilter();
        return super.loadPages(...arguments);
    }

    filter(fieldDefs, path) {
        fieldDefs = super.filter(fieldDefs, path);
        const filteredKeys = Object.keys(fieldDefs).filter((key) => {
            const fullPath = `object${path ? `.${path}` : ""}.${fieldDefs[key].name}`;
            if (!this.isTemplateEditor && !this.allowedQwebExpressions?.includes(fullPath)) {
                return false;
            }
            if (fieldDefs[key].type === "separator") {
                // Don't show separator property
                return false;
            }
            return fieldDefs[key].searchable;
        });
        return Object.fromEntries(filteredKeys.map((k) => [k, fieldDefs[k]]));
    }

    /**
     * Load the list of field path in the popover state.
     */
    async _loadFields(fieldsPath) {
        const fieldsInfos = Object.fromEntries(
            await Promise.all(
                fieldsPath.map(async (path) => [
                    path,
                    await this.fieldService.loadPath(this.props.resModel, path, true),
                ])
            )
        );

        const selected = [];
        for (const path of fieldsPath) {
            const { names, modelsInfo } = await fieldsInfos[path];
            const fieldsInfo = [];
            for (let i = 0; i < names.length; i++) {
                const f = modelsInfo[i].fieldDefs[names[i]];
                fieldsInfo.push(f);
            }
            selected.push(fieldsInfo);
        }
        this.aiFieldsState.selected = selected;
    }
}

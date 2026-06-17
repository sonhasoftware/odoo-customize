/** @odoo-module */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Field } from "@web/views/fields/field";

export class SourceViewLink extends Field {
    static template = "ai.SourceViewLink";

    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    get isClickable() {
        return this.props.record.data.status === 'indexed' && this.props.record.data.user_has_access;
    }

    async onClickField(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        if (!this.isClickable) {
            return;
        }
        const action = {
            context: this.props.record.context,
            resModel: this.props.record.resModel,
            name: "action_access_source",
            type: "object",
            resId: this.props.record.resId,
        };
        await this.actionService.doActionButton(action);
    }
}

registry.category("fields").add("source_view_link", {component: SourceViewLink,});

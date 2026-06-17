/** @odoo-module */
import { registry } from "@web/core/registry";
import { BadgeField, badgeField } from "@web/views/fields/badge/badge_field";

export class StatusBadgeTooltip extends BadgeField {
    static template = "ai.StatusBadgeTooltip";

    get showTooltip() {
        return this.props.record.data[this.props.name] === 'failed' &&
            this.props.record.data.error_details;
    }

    get errorDetails() {
        return this.props.record.data.error_details || '';
    }
}

registry.category("fields").add("status_badge_tooltip", {
    ...badgeField,
    component: StatusBadgeTooltip,
});

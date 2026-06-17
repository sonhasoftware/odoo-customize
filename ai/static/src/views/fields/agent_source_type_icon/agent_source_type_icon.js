/** @odoo-module */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class AgentSourceTypeIcon extends Component {
    static template = "ai.AgentSourceTypeIcon";
    static props = { ...standardFieldProps };

    setup() {
        this.type = this.props.record.data.type;
        this.mimetype = this.props.record.data.mimetype;
    }

    get iconConfig() {
        const type = this.type;
        const mimetype = this.mimetype;

        if (type === 'url') {
            return {
                type: 'fontawesome',
                class: 'fa fa-link ms-1',
                title: 'Link'
            };
        } else if (type === 'binary' && mimetype) {
            return {
                type: 'mimetype',
                class: 'o_agent_source_icon o_image',
                dataMimetype: mimetype,
                title: mimetype
            };
        } else {
            return {
                type: 'fontawesome',
                class: 'fa fa-file-o ms-1',
                title: 'File'
            };
        }
    }
}

const agentSourceTypeIcon = {
    component: AgentSourceTypeIcon,
};

registry.category("fields").add("agent_source_type_icon", agentSourceTypeIcon);

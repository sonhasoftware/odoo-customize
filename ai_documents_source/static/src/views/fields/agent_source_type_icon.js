import { AgentSourceTypeIcon } from "@ai/views/fields/agent_source_type_icon/agent_source_type_icon";
import { patch } from "@web/core/utils/patch";

patch(AgentSourceTypeIcon.prototype, {
    get iconConfig() {
        const type = this.type;
        if (type === 'document') {
            return {
                type: 'image',
                src: '/ai_documents_source/static/img/icon.png',
                title: 'Documents'
            };
        }
        return super.iconConfig;
    }
});

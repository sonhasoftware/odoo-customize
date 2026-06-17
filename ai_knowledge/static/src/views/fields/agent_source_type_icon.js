import { AgentSourceTypeIcon } from "@ai/views/fields/agent_source_type_icon/agent_source_type_icon";
import { patch } from "@web/core/utils/patch";

patch(AgentSourceTypeIcon.prototype, {
    get iconConfig() {
        const type = this.type;
        if (type === 'knowledge_article') {
            return {
                type: 'image',
                src: '/ai_knowledge/static/img/icon.png',
                title: 'Knowledge Article'
            };
        }
        return super.iconConfig;
    }
});

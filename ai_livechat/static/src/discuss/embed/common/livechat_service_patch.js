import { LivechatService } from "@im_livechat/embed/common/livechat_service";
import { patch } from "@web/core/utils/patch";

patch(LivechatService.prototype, {
    getSessionExtraParams(thread, options) {
        let extraParams = super.getSessionExtraParams(thread, options);
        // 1. The agent options.ai_agent_id has higher priority than the agent specified on
        // the livechat rule matching the current URL.
        extraParams['ai_agent_id'] = options.ai_agent_id ?? this.store.livechat_rule?.ai_agent_id;
        return extraParams;
    },
});

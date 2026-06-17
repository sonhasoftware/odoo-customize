/** @odoo-module */
import { SuggestionService } from "@mail/core/common/suggestion_service";

import { patch } from "@web/core/utils/patch";

patch(SuggestionService.prototype, {
    /** @override */
    searchSuggestions({ delimiter, term }, { thread } = {}) {
        if (
            ["ai_composer", "ai_chat"].includes(thread?.type) &&
            ["#", "@"].includes(delimiter)
        ) {
            return {
                type: undefined,
                suggestions: [],
            };
        }
        return super.searchSuggestions(...arguments);
    },
});

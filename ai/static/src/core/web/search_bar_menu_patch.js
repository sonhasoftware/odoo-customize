/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { SearchBarMenu } from "@web/search/search_bar_menu/search_bar_menu";
import { AskAIButton } from "@ai/core/web/ask_ai_button";

patch(SearchBarMenu, {
    components: { ...SearchBarMenu.components, AskAIButton },
});

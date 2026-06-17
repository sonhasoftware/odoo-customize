/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const commandProviderRegistry = registry.category("command_provider");

commandProviderRegistry.add("sonha_ask_ai", {
    provide: (env, options) => {
        const result = [];
        const searchValue = options.searchValue.toLowerCase();
        
        if ("hỏi ai".includes(searchValue) || "/ai".includes(searchValue) || "ask ai".includes(searchValue)) {
            result.push({
                name: _t("Hỏi AI... (/ai)"),
                action() {
                    window.dispatchEvent(new Event("open-ask-ai"));
                },
            });
        }
        return result;
    }
});

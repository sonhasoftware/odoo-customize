/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
import { Plugin } from "@html_editor/plugin";
import { DYNAMIC_PLACEHOLDER_PLUGINS } from "@html_editor/backend/plugin_sets";
import { isHtmlContentSupported } from "@html_editor/core/selection_plugin";

export class PromptPlugin extends Plugin {
    static id = "prompt";
    static dependencies = ["banner"];
    resources = {
        user_commands: [
            {
                id: "prompt",
                title: _t("Prompt"),
                description: _t("Insert an AI prompt"),
                icon: "fa-bolt",
                run: () => {
                    this.dependencies.banner.insertBanner(
                        _t("Prompt"),
                        "⚡",
                        "primary",
                        "o_editor_prompt",
                        "o_editor_prompt_content"
                    );
                },
                isAvailable: isHtmlContentSupported,
            },
        ],
        powerbox_items: [
            {
                commandId: "prompt",
                categoryId: "ai",
            },
        ],
    };
}

DYNAMIC_PLACEHOLDER_PLUGINS.push(PromptPlugin);

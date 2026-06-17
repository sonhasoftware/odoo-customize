import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { aiPrompt } from "@ai/ai_prompt/ai_prompt_field";

class AiSortDocumentsPromptField extends aiPrompt.component {
    get missingRecordsMessage() {
        return _t("⚠️ Tell the AI where to sort your documents with /record.");
    }
}

registry.category("fields").add("ai_sort_documents_prompt", {
    ...aiPrompt,
    component: AiSortDocumentsPromptField,
});

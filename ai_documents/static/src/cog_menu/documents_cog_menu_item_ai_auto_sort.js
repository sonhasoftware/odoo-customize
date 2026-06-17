import { DocumentsCogMenuItem } from "@documents/views/cog_menu/documents_cog_menu_item";
import { useService } from "@web/core/utils/hooks";

export class DocumentsCogMenuItemAiAutoSort extends DocumentsCogMenuItem {
    static template = "ai_documents.DocumentsCogMenuItemAiAutoSort";

    setup() {
        super.setup();
        this.action = useService("action");
        this.folder = this.env.searchModel.getSelectedFolder();
    }

    async onSelected() {
        if (!this.folder || typeof this.folder.id !== "number") {
            return;
        }

        this.action.doAction("ai_documents.ai_documents_sort_action", {
            additionalContext: {
                default_folder_id: this.folder.id,
            },
            onClose: async () => {
                await this.env.searchModel._reloadSearchPanel();
            },
        });
    }
}

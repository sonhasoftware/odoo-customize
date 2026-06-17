import { patch } from "@web/core/utils/patch";
import { DocumentsCogMenu } from "@documents/views/cog_menu/documents_cog_menu";
import { DocumentsCogMenuItemAiAutoSort } from "./documents_cog_menu_item_ai_auto_sort";
import { STATIC_COG_GROUP_ACTION_PIN } from "@documents/views/cog_menu/documents_cog_menu_group";
import { useService } from "@web/core/utils/hooks";

patch(DocumentsCogMenu.prototype, {
    setup() {
        this.documentService = useService("document.document");
        return super.setup(...arguments);
    },

    async _registryItems() {
        const ret = await super._registryItems();
        if (this.documentService.userIsErpManager) {
            ret.push({
                Component: DocumentsCogMenuItemAiAutoSort,
                groupNumber: STATIC_COG_GROUP_ACTION_PIN,
                key: DocumentsCogMenuItemAiAutoSort.name,
            });
        }
        return ret;
    },
});

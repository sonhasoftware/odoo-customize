/** @odoo-module */
import { BannerPlugin } from "@html_editor/main/banner_plugin";
import { closestElement } from "@html_editor/utils/dom_traversal";
import { patch } from "@web/core/utils/patch";

patch(BannerPlugin.prototype, {
    onBannerEmojiChange(iconElement) {
        if (closestElement(iconElement, ".o_editor_prompt")) {
            return;
        }
        return super.onBannerEmojiChange(iconElement);
    },
});

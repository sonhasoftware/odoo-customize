/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { ComposerAction } from "@mail/core/common/composer_actions";

patch(ComposerAction.prototype, {
    _condition({ composer }) {
        const requiredActions = ["send-message"];
        if (
            composer.targetThread?.correspondent?.persona.im_status === "agent" &&
            !requiredActions.includes(this.id)
        ) {
            return false;
        }
        return super._condition(...arguments);
    },
});

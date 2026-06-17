/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useEffect } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup();
        useEffect(
            () => {
                const onDataRequest = (event) => {
                    this.env.bus.trigger("AI.SEND_MODEL_DETAILS", this.model);
                };
                this.env.bus.addEventListener("AI.REQUEST_MODEL_DETAILS", onDataRequest);
                return () =>
                    this.env.bus.removeEventListener("AI.REQUEST_MODEL_DETAILS", onDataRequest);
            },
            () => []
        );
    },
});

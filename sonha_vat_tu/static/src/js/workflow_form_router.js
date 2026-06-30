/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
import { FormController } from "@web/views/form/form_controller";
import { onMounted } from "@odoo/owl";

const WORKFLOW_MODEL = "ke.hoach.vat.tu";

patch(WebClient.prototype, {
    async loadRouterState() {
        const router = this.env.services.router;
        const state = router.current.hash;
        if (
            state.model === WORKFLOW_MODEL &&
            state.id &&
            state.view_type === "form" &&
            !state.view_id &&
            !state.action
        ) {
            const viewId = await this.env.services.orm.call(
                WORKFLOW_MODEL,
                "get_formview_id",
                [[parseInt(state.id, 10)]]
            );
            if (viewId) {
                router.pushState({ view_id: viewId }, { replace: true });
            }
        }
        return super.loadRouterState(...arguments);
    },
});

patch(FormController.prototype, {
    setup() {
        super.setup();
        onMounted(() => {
            if (this.props.resModel !== WORKFLOW_MODEL || !this.props.resId || !this.props.viewId) {
                return;
            }
            const { view_id: currentViewId } = this.env.services.router.current.hash;
            if (String(currentViewId || "") === String(this.props.viewId)) {
                return;
            }
            this.env.services.router.pushState({ view_id: this.props.viewId }, { replace: true });
        });
    },
});

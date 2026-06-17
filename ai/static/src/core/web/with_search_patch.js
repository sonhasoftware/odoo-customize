/** @odoo-module */
import { WithSearch } from "@web/search/with_search/with_search";
import { patch } from "@web/core/utils/patch";
import { useViewDetailsGetter } from "@ai/discuss/core/common/view_details";

patch(WithSearch, {
    props: {
        ...WithSearch.props,
        ai: { type: Object, optional: true },
    },
});

patch(WithSearch.prototype, {
    setup() {
        super.setup(...arguments);
        useViewDetailsGetter(() => this.getCurrentViewInfo());
    },
    async getCurrentViewInfo() {
        const config = this.env.config;
        const searchModel = this.env.searchModel;
        const result = {};
        // if in form view, no need to return anything
        if (config.viewType === "form") {
            return;
        }
        result.action_id = config.actionId;
        result.view_id = config.viewId;
        result.model = searchModel.resModel;
        result.available_view_types = config.viewSwitcherEntries.map((v) => v.type);
        result.view_type = config.viewType;
        result.order_by = searchModel.orderBy;
        result.facets = searchModel.facets;
        return result;
    },
});

/** @odoo-module */
import { SearchBar } from "@web/search/search_bar/search_bar";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";

function isDefined(value) {
    return value !== undefined && value !== null;
}

patch(SearchBar.prototype, {
    setup() {
        super.setup(...arguments);
        useBus(this.env.bus, "APPLY_AI_ADJUST_SEARCH", async ({ detail }) => {
            const searchModel = this.env.searchModel;
            for (const facetGroupId of detail.removeFacets) {
                searchModel.deactivateGroup(facetGroupId);
            }
            const {
                toggleFilters,
                toggleGroupBys,
                applySearches,
                customDomain,
                measures,
                mode,
                order,
                stacked,
                cumulated,
            } = detail;
            await searchModel.applyAISearch({
                filters: toggleFilters,
                groupBys: toggleGroupBys,
                fieldSearches: applySearches,
                customDomain,
            });
            if (
                (measures && measures.length) ||
                [mode, order, stacked, cumulated].some(isDefined)
            ) {
                this.env.bus.trigger("APPLY_AI_ADJUST_MODEL", {
                    measures: measures ?? [],
                    mode,
                    order,
                    stacked,
                    cumulated,
                });
            }
            const chatboxInput = document.querySelector(".o-mail-Composer-input");
            if (chatboxInput) {
                chatboxInput.focus();
            }
        });
    },
});

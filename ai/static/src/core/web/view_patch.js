/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { View } from "@web/views/view";
import { useSubEnv } from "@odoo/owl";

patch(View.prototype, {
    setup(...args) {
        super.setup(...args);
        useSubEnv({
            config: {
                ...this.env.config,
                disableSearchBarAutofocus: this.props.ai
                    ? true
                    : this.env.config.disableSearchBarAutofocus,
            },
        });
    },
    async loadView(props) {
        await super.loadView(props);
        if ("ai" in this.componentProps) {
            const aiProps = this.componentProps.ai;
            if (this.props.type === "pivot") {
                if (aiProps.measures && aiProps.measures.length > 0) {
                    this.componentProps.modelParams.metaData.activeMeasures = aiProps.measures;
                }
                if (aiProps.colGroupBys && aiProps.colGroupBys.length > 0) {
                    this.componentProps.modelParams.metaData.colGroupBys = aiProps.colGroupBys;
                }
                if (aiProps.sortedColumn) {
                    // Set up sorted column with empty groupId for total column sorting
                    this.componentProps.modelParams.metaData.sortedColumn = {
                        groupId: [[], []], // Empty groupId means sort by total column
                        measure: aiProps.sortedColumn.measure,
                        order: aiProps.sortedColumn.order,
                    };
                }
            } else if (this.props.type === "graph") {
                if (aiProps.measure) {
                    this.componentProps.modelParams.measure = aiProps.measure;
                }
                if (aiProps.mode) {
                    this.componentProps.modelParams.mode = aiProps.mode;
                }
                if (aiProps.order) {
                    this.componentProps.modelParams.order = aiProps.order;
                }
                if (aiProps.stacked !== undefined) {
                    this.componentProps.modelParams.stacked = aiProps.stacked;
                }
                if (aiProps.cumulated !== undefined) {
                    this.componentProps.modelParams.cumulated = aiProps.cumulated;
                }
                if (aiProps.groupBys && aiProps.groupBys.length > 0) {
                    this.componentProps.modelParams.groupBy = aiProps.groupBys;
                }
            }
            // Remove ai from componentProps to avoid passing it to the component
            delete this.componentProps.ai;
        }
    },
});

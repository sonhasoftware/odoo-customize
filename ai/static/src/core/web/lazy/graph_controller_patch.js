/** @odoo-module */
import { GraphController } from "@web/views/graph/graph_controller";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";
import { GraphModel } from "@web/views/graph/graph_model";

patch(GraphController.prototype, {
    setup() {
        super.setup(...arguments);
        useBus(this.env.bus, "APPLY_AI_ADJUST_MODEL", async ({ detail }) => {
            const { measures, mode, order, stacked, cumulated } = detail;
            if (this.model instanceof GraphModel) {
                const defaultMetaData = this.model._buildMetaData();
                const metaData = this.model._buildMetaData({
                    measures,
                    mode: mode ?? defaultMetaData.mode,
                    order: order ?? defaultMetaData.order,
                    stacked: stacked ?? defaultMetaData.stacked,
                    cumulated: cumulated ?? defaultMetaData.stacked,
                });
                const validMeasures = measures.filter((m) => m in metaData.measures);
                const activeMeasures = metaData.activeMeasures || [];
                const measuresToActivate = validMeasures.filter((m) => !activeMeasures.includes(m));
                // It should only be at most one item, so just take the first.
                // This is because graph only allows one active measure.
                const measure = measuresToActivate[0] ?? metaData.measure;
                if (measure) {
                    await this.model.updateMetaData({ measure });
                }
                this.model.updateMetaData({
                    mode: mode ?? metaData.mode,
                    order: order ?? metaData.order,
                    stacked: stacked ?? metaData.stacked,
                    cumulated: cumulated ?? metaData.cumulated,
                });
            }
        });
    },
});

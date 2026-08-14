/** @odoo-module */

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";
import { EventBus } from "@odoo/owl";

const MODEL = "tree.view.column.layout";
const NOTIFICATION_TYPE = "tree_view_column_layout/updated";

function normalizeLayout(layout) {
    if (!layout) {
        return null;
    }
    const storageKey =
        typeof layout.storageKey === "string" && layout.storageKey
            ? layout.storageKey
            : Number.isInteger(layout.viewId)
            ? `view:${layout.viewId}`
            : null;
    if (!storageKey) {
        return null;
    }
    return {
        storageKey,
        viewId: layout.viewId,
        resModel: layout.resModel || "",
        scope: layout.scope || "view",
        parentViewId: layout.parentViewId || null,
        parentModel: layout.parentModel || "",
        parentField: layout.parentField || "",
        order: Array.isArray(layout.order) ? layout.order : [],
        widths:
            layout.widths && typeof layout.widths === "object" && !Array.isArray(layout.widths)
                ? layout.widths
                : {},
        labels:
            layout.labels && typeof layout.labels === "object" && !Array.isArray(layout.labels)
                ? layout.labels
                : {},
        revision: Number.isInteger(layout.revision) ? layout.revision : 0,
    };
}

export const columnLayoutService = {
    dependencies: ["bus_service", "notification", "orm", "user"],

    start(env, { bus_service: busService, notification, orm, user }) {
        const eventBus = new EventBus();
        const layouts = new Map();
        let saveQueue = Promise.resolve();

        for (const layout of Object.values(session.tree_view_column_layouts || {})) {
            const normalized = normalizeLayout(layout);
            if (normalized) {
                layouts.set(normalized.storageKey, normalized);
            }
        }

        const applyLayout = (layout) => {
            const normalized = normalizeLayout(layout);
            if (!normalized) {
                return null;
            }
            const current = layouts.get(normalized.storageKey);
            if (current && current.revision >= normalized.revision) {
                return current;
            }
            layouts.set(normalized.storageKey, normalized);
            eventBus.trigger("updated", normalized);
            return normalized;
        };

        const enqueueSave = (storageKey, values, layoutContext = {}) => {
            if (!user.isAdmin || typeof storageKey !== "string" || !storageKey) {
                return Promise.resolve(null);
            }
            const execute = async () => {
                try {
                    const layout = await orm.call(
                        MODEL,
                        "save_layout_by_key",
                        [storageKey],
                        { ...values, layout_context: layoutContext }
                    );
                    return applyLayout(layout);
                } catch (error) {
                    notification.add(_t("Could not save the shared column layout."), {
                        type: "danger",
                    });
                    return null;
                }
            };
            saveQueue = saveQueue.then(execute, execute);
            return saveQueue;
        };

        busService.subscribe(NOTIFICATION_TYPE, applyLayout);
        busService.start();

        return {
            bus: eventBus,
            isAdmin: user.isAdmin,
            get(storageKey) {
                return typeof storageKey === "string" ? layouts.get(storageKey) || null : null;
            },
            saveOrder(storageKey, order, layoutContext) {
                return enqueueSave(storageKey, { column_order: order }, layoutContext);
            },
            saveWidth(storageKey, fieldName, width, layoutContext) {
                return enqueueSave(
                    storageKey,
                    { width_updates: { [fieldName]: width } },
                    layoutContext
                );
            },
            saveLabel(storageKey, columnKey, label, layoutContext) {
                return enqueueSave(
                    storageKey,
                    { label_updates: { [columnKey]: label } },
                    layoutContext
                );
            },
            reset(storageKey, layoutContext) {
                return enqueueSave(storageKey, { reset: true }, layoutContext);
            },
        };
    },
};

registry.category("services").add("tree_view_column_layout", columnLayoutService);

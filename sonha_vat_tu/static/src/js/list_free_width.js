/** @odoo-module */

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched } from "@odoo/owl";

function hasFreeWidthTreeClass(renderer) {
    const className = renderer.props.archInfo?.className || "";
    if (className.split(/\s+/).filter(Boolean).includes("sh_free_width_tree")) {
        return true;
    }
    return Boolean(renderer.rootRef?.el?.closest?.(".sh_free_width_tree"));
}

function resetTableColumnSizing(table) {
    if (!table) {
        return;
    }
    table.style.tableLayout = "auto";
    table.style.width = null;
    table.querySelectorAll("thead th, tbody td, tfoot td").forEach((cell) => {
        cell.style.width = null;
        cell.style.minWidth = null;
        cell.style.maxWidth = null;
    });
}

function applyFreeWidthTreeSizing(renderer) {
    if (!hasFreeWidthTreeClass(renderer)) {
        return;
    }
    resetTableColumnSizing(renderer.tableRef?.el);
    renderer.columnWidths = null;
    renderer.keepColumnWidths = false;
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        onMounted(() => applyFreeWidthTreeSizing(this));
        onPatched(() => applyFreeWidthTreeSizing(this));
    },

    freezeColumnWidths() {
        if (hasFreeWidthTreeClass(this)) {
            applyFreeWidthTreeSizing(this);
            return;
        }
        return super.freezeColumnWidths(...arguments);
    },

    _applySavedColumnWidths(table) {
        if (hasFreeWidthTreeClass(this)) {
            resetTableColumnSizing(table);
            return;
        }
        return super._applySavedColumnWidths(...arguments);
    },

    _persistCurrentColumnWidths(table) {
        if (hasFreeWidthTreeClass(this)) {
            return;
        }
        return super._persistCurrentColumnWidths(...arguments);
    },

    _setupColumnWidthPersistence(table) {
        if (hasFreeWidthTreeClass(this)) {
            return;
        }
        return super._setupColumnWidthPersistence(...arguments);
    },
});

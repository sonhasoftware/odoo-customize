/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched } from "@odoo/owl";

/** Cột cuối cùng được ghim (scroll bắt đầu sau cột này). */
const STICKY_END_FIELD = "don_vi_tinh";

/** B3 pivot: Mã NVL, Tên NVL, ĐVT. */
const B3_STICKY_COL_COUNT = 3;

/** Biểu 2: Mã NVL → Khổ rộng. */
const VTCD_STICKY_COL_COUNT = 6;

function isStickyNvlContext(table) {
    if (!table) {
        return false;
    }
    if (table.closest(".o_vat_tu_approval_steps")) {
        return false;
    }
    if (table.closest(".o_vat_tu_b3_pivot")) {
        return true;
    }
    if (table.closest(".o_vat_tu_vtcd_pivot")) {
        return true;
    }
    if (table.closest(".o_vat_tu_merged_list")) {
        return true;
    }
    return Boolean(table.closest(".o_vat_tu_sticky_nvl"));
}

function clearStickyCells(table) {
    table.querySelectorAll(".o_vat_tu_sticky_col").forEach((cell) => {
        cell.classList.remove("o_vat_tu_sticky_col", "o_vat_tu_sticky_col_last");
        cell.style.left = "";
        cell.style.position = "";
        cell.style.zIndex = "";
    });
}

function stickCells(cells, { header = false } = {}) {
    if (!cells.length) {
        return;
    }
    const baseZ = header ? 20 : 10;
    let left = 0;
    cells.forEach((cell, idx) => {
        cell.classList.add("o_vat_tu_sticky_col");
        if (idx === cells.length - 1) {
            cell.classList.add("o_vat_tu_sticky_col_last");
        }
        cell.style.position = "sticky";
        cell.style.left = `${left}px`;
        cell.style.zIndex = String(baseZ + idx);
        left += cell.offsetWidth;
    });
}

function stickyCountFromRenderer(renderer) {
    const columns = renderer.state?.columns || [];
    let endIdx = -1;
    for (let i = 0; i < columns.length; i++) {
        const col = columns[i];
        if (col.type === "field" && col.name === STICKY_END_FIELD) {
            endIdx = i;
            break;
        }
    }
    if (endIdx < 0) {
        return 0;
    }
    const selectorOffset = renderer.hasSelectors ? 1 : 0;
    return selectorOffset + endIdx + 1;
}

function applyStickyHeaderRow(table, stickyCount) {
    const row1 = table.querySelector("thead tr");
    if (!row1) {
        return;
    }
    let leaf = 0;
    const stickyThs = [];
    for (const th of row1.children) {
        if (leaf >= stickyCount) {
            break;
        }
        stickyThs.push(th);
        leaf += parseInt(th.getAttribute("colspan") || "1", 10);
    }
    stickCells(stickyThs, { header: true });
}

function applyStickyBodyRows(table, stickyCount) {
    for (const row of table.querySelectorAll("tbody tr, tfoot tr")) {
        const cells = [...row.children].slice(0, stickyCount);
        stickCells(cells, { header: false });
    }
}

function applyStickyByColumnCount(table, stickyCount) {
    if (!stickyCount) {
        return;
    }
    applyStickyHeaderRow(table, stickyCount);
    applyStickyBodyRows(table, stickyCount);
}

function applyStickyNvlColumns(renderer) {
    const table = renderer.tableRef?.el;
    if (!table || !isStickyNvlContext(table)) {
        return;
    }
    clearStickyCells(table);

    if (table.closest(".o_vat_tu_b3_pivot")) {
        applyStickyByColumnCount(table, B3_STICKY_COL_COUNT);
        return;
    }

    if (table.closest(".o_vat_tu_vtcd_pivot")) {
        applyStickyByColumnCount(table, VTCD_STICKY_COL_COUNT);
        return;
    }

    const stickyCount = stickyCountFromRenderer(renderer);
    applyStickyByColumnCount(table, stickyCount);
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            applyStickyNvlColumns(this);
        });
        onPatched(() => {
            applyStickyNvlColumns(this);
        });
    },
});

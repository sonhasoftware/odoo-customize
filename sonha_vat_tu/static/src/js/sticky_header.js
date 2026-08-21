/** @odoo-module */

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

/**
 * Ghim tiêu đề bảng (sticky header) cho one2many tree view có class
 * `sh_free_width_tree` khi nằm trong form view.
 */


function _isFormFreeWidth(renderer) {
    const table = renderer.tableRef?.el;
    if (!table) {
        return false;
    }
    if (!table.closest(".o_form_view")) {
        return false;
    }
    if (table.closest(".o_vat_tu_approval_steps")) {
        return false;
    }
    const archClass = renderer.props.archInfo?.className || "";
    if (archClass.split(/\s+/).some((c) => c === "sh_free_width_tree")) {
        return true;
    }
    return Boolean(table.closest(".sh_free_width_tree"));
}

function _findScrollParent(el) {
    return el.closest(".o_content") || el.closest(".modal-body");
}

function _clearStyles(thead) {
    if (!thead) {
        return;
    }
    thead.style.transform = "";
    thead.style.removeProperty("position");
    thead.style.zIndex = "";
    thead.classList.remove("o_vat_tu_sticky_header_active");
}

// ---------------------------------------------------------------------------
// Core
// ---------------------------------------------------------------------------

/**
 * Khởi tạo (hoặc cập nhật) sticky header cho một ListRenderer.
 *
 * Nếu đã setup rồi với cùng scroll container + thead → chỉ re-check vị trí.
 * Nếu DOM thay đổi (tab switch, re-render) → dọn cũ, setup mới.
 */
function _initStickyHeader(renderer) {
    const table = renderer.tableRef?.el;
    if (!_isFormFreeWidth(renderer)) {
        _destroyStickyHeader(renderer);
        return;
    }

    const scrollParent = _findScrollParent(table);
    if (!scrollParent) {
        _destroyStickyHeader(renderer);
        return;
    }

    const thead = table.querySelector("thead");
    if (!thead) {
        _destroyStickyHeader(renderer);
        return;
    }

    const st = renderer.__stickyHeaderState;
    if (st && st.scrollParent === scrollParent && st.thead === thead) {
        st.doUpdate();
        return;
    }

    _destroyStickyHeader(renderer);

    let ticking = false;

    const doUpdate = () => {
        const containerRect = scrollParent.getBoundingClientRect();
        const tableRect = table.getBoundingClientRect();

        if (tableRect.height === 0) {
            _clearStyles(thead);
            ticking = false;
            return;
        }

        const theadH = thead.getBoundingClientRect().height;
        const tableBottom = tableRect.top + tableRect.height;

        // Ghim khi:
        //   1) Đỉnh bảng đã trôi lên trên đỉnh scroll container
        //   2) Vẫn còn ít nhất 1 dòng body hiện dưới thead
        const shouldStick =
            tableRect.top < containerRect.top &&
            tableBottom > containerRect.top + theadH + 10;

        if (shouldStick) {
            const offset = Math.round(containerRect.top - tableRect.top);
            thead.style.transform = `translateY(${offset}px)`;
            thead.style.setProperty("position", "relative", "important");
            thead.style.zIndex = "20";
            thead.classList.add("o_vat_tu_sticky_header_active");
        } else {
            _clearStyles(thead);
        }

        ticking = false;
    };

    const onScroll = () => {
        if (!ticking) {
            requestAnimationFrame(doUpdate);
            ticking = true;
        }
    };

    scrollParent.addEventListener("scroll", onScroll, { passive: true });

    renderer.__stickyHeaderState = {
        scrollParent,
        thead,
        doUpdate,
        onScroll,
    };

    onScroll();
}

function _destroyStickyHeader(renderer) {
    const st = renderer.__stickyHeaderState;
    if (!st) {
        return;
    }
    st.scrollParent.removeEventListener("scroll", st.onScroll);
    _clearStyles(st.thead);
    renderer.__stickyHeaderState = null;
}

// ---------------------------------------------------------------------------
// Patch
// ---------------------------------------------------------------------------

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => _initStickyHeader(this));
        onPatched(() => _initStickyHeader(this));
        onWillUnmount(() => _destroyStickyHeader(this));
    },
});

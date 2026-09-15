/** @odoo-module */

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

/**
 * Ghim tiêu đề bảng (sticky header) cho tree view có class `sh_free_width_tree`
 * trong form view.
 *
 * Không dùng `position: sticky` của Odoo được vì `.o_list_renderer` bị đặt
 * `overflow-x: auto` (để ghim cột) => CSS tính `overflow-y` thành `auto`, biến
 * renderer thành scrollport dọc nhưng chiều cao lại `auto` nên không bao giờ
 * scroll => thead sticky dính vào một khung không scroll và trôi theo trang.
 *
 * Thay vào đó: tự tính "mép trên vùng còn nhìn thấy" của bảng bằng cách giao
 * (intersect) rect của mọi ancestor có clip dọc, rồi dịch thead xuống đúng
 * khoảng đó. Cách này không cần biết phần tử nào đang scroll nên hoạt động
 * giống nhau dù chatter nằm bên phải (o_xxl_form_view, scroll ở
 * `.o_form_sheet_bg`), nằm dưới (scroll ở `.o_content`), hay trong modal.
 */

/** Chừa lại tối thiểu 1 dòng body dưới thead, nếu không thì thôi ghim. */
const MIN_BODY_VISIBLE = 24;

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

function _clipsVertically(el) {
    const overflowY = getComputedStyle(el).overflowY;
    return overflowY !== "visible" && overflowY !== "clip";
}

/** Các ancestor chặn tầm nhìn dọc của bảng. Tính 1 lần, chỉ tính lại khi layout đổi. */
function _collectClippers(table) {
    const clippers = [];
    for (let el = table.parentElement; el && el !== document.body; el = el.parentElement) {
        if (_clipsVertically(el)) {
            clippers.push(el);
        }
    }
    return clippers;
}

/**
 * Vùng dọc còn nhìn thấy của bảng: giao rect của mọi ancestor clip dọc,
 * chặn dưới bởi viewport.
 */
function _visibleBand(clippers) {
    let top = 0;
    let bottom = window.innerHeight || document.documentElement.clientHeight;

    for (const el of clippers) {
        const rect = el.getBoundingClientRect();
        if (rect.height === 0) {
            continue;
        }
        top = Math.max(top, rect.top);
        bottom = Math.min(bottom, rect.bottom);
    }

    return { top, bottom };
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

function _initStickyHeader(renderer) {
    const table = renderer.tableRef?.el;
    if (!_isFormFreeWidth(renderer)) {
        _destroyStickyHeader(renderer);
        return;
    }

    const thead = table.querySelector("thead");
    if (!thead) {
        _destroyStickyHeader(renderer);
        return;
    }

    const st = renderer.__stickyHeaderState;
    if (st && st.table === table && st.thead === thead) {
        st.requestUpdate();
        return;
    }

    _destroyStickyHeader(renderer);

    let ticking = false;
    let clippers = _collectClippers(table);

    const update = () => {
        ticking = false;

        if (!table.isConnected) {
            return;
        }

        const tableRect = table.getBoundingClientRect();
        if (tableRect.height === 0) {
            _clearStyles(thead);
            return;
        }

        const band = _visibleBand(clippers);
        const theadH = thead.getBoundingClientRect().height;

        // Chỉ ghim khi đỉnh bảng đã trôi lên trên vùng nhìn thấy và vẫn còn
        // chỗ cho thead + ít nhất một phần dòng body.
        const needStick =
            tableRect.top < band.top &&
            tableRect.bottom > band.top + theadH + MIN_BODY_VISIBLE &&
            band.bottom > band.top + theadH;

        if (!needStick) {
            _clearStyles(thead);
            return;
        }

        // Không đẩy thead vượt quá phần thân bảng còn lại.
        const maxOffset = tableRect.height - theadH - MIN_BODY_VISIBLE;
        const offset = Math.min(Math.round(band.top - tableRect.top), Math.round(maxOffset));

        if (offset <= 0) {
            _clearStyles(thead);
            return;
        }

        thead.style.transform = `translateY(${offset}px)`;
        thead.style.setProperty("position", "relative", "important");
        thead.style.zIndex = "20";
        thead.classList.add("o_vat_tu_sticky_header_active");
    };

    const requestUpdate = () => {
        if (!ticking) {
            ticking = true;
            requestAnimationFrame(update);
        }
    };

    // Layout đổi (chatter phải <-> dưới, đổi tab, resize) => chuỗi ancestor
    // chặn tầm nhìn có thể khác, phải dò lại.
    const relayout = () => {
        clippers = _collectClippers(table);
        requestUpdate();
    };

    // Capture: bắt scroll của mọi phần tử (o_content, o_form_sheet_bg,
    // modal-body, notebook...) mà không cần đoán phần tử nào đang scroll.
    document.addEventListener("scroll", requestUpdate, { capture: true, passive: true });
    window.addEventListener("resize", relayout, { passive: true });

    // Chatter đổi vị trí (phải <-> dưới), đổi tab, thêm/bớt dòng => đổi layout.
    const resizeObserver = new ResizeObserver(relayout);
    resizeObserver.observe(table);
    const sheet = table.closest(".o_form_sheet_bg") || table.closest(".o_content");
    if (sheet) {
        resizeObserver.observe(sheet);
    }

    renderer.__stickyHeaderState = {
        table,
        thead,
        requestUpdate,
        relayout,
        resizeObserver,
    };

    relayout();
}

function _destroyStickyHeader(renderer) {
    const st = renderer.__stickyHeaderState;
    if (!st) {
        return;
    }
    document.removeEventListener("scroll", st.requestUpdate, { capture: true });
    window.removeEventListener("resize", st.relayout);
    st.resizeObserver.disconnect();
    _clearStyles(st.thead);
    renderer.__stickyHeaderState = null;
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => _initStickyHeader(this));
        onPatched(() => _initStickyHeader(this));
        onWillUnmount(() => _destroyStickyHeader(this));
    },
});

/** @odoo-module */

import { ListRenderer } from "@web/views/list/list_renderer";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import { ColumnLabelDialog } from "./column_label_dialog";

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.columnLayoutService = useService("tree_view_column_layout");
        this.dialogService = useService("dialog");
        this._columnReorderHandlers = [];
        this._columnResizePersistenceHandlers = [];
        useBus(this.columnLayoutService.bus, "updated", this._onSharedColumnLayoutUpdated);
        onMounted(() => this._setupColumnCustomization());
        onPatched(() => this._setupColumnCustomization());
        onWillUnmount(() => {
            this._cleanupColumnReorderHandlers();
            this._cleanupColumnResizePersistenceHandlers();
        });
    },

    _getColumnStorageViewId() {
        const viewId = this.env.config.viewId;
        return Number.isInteger(viewId) ? viewId : null;
    },

    _getColumnStorageKey() {
        const viewId = this._getColumnStorageViewId();
        const nested = this.props.nestedKeyOptionalFieldsData;
        const resModel = this.props.list?.resModel;
        if (viewId && nested?.field && nested?.model && resModel) {
            return `x2many:${viewId}:${nested.model}:${nested.field}:${resModel}`;
        }
        return viewId ? `view:${viewId}` : null;
    },

    _getColumnLayoutContext() {
        const storageKey = this._getColumnStorageKey();
        const nested = this.props.nestedKeyOptionalFieldsData;
        const resModel = this.props.list?.resModel || "";
        if (storageKey?.startsWith("x2many:")) {
            return {
                scope: "x2many",
                parentViewId: this._getColumnStorageViewId(),
                parentModel: nested.model,
                parentField: nested.field,
                resModel,
            };
        }
        return {
            scope: "view",
            viewId: this._getColumnStorageViewId(),
            resModel,
        };
    },

    _getColumnLayout() {
        return this.env.services.tree_view_column_layout.get(this._getColumnStorageKey());
    },

    _getColumnHeaders(table) {
        return [...table.querySelectorAll("thead > tr:first-child > th")].filter(
            (th) => th.dataset.name && !th.classList.contains("o_list_record_selector")
        );
    },

    _canCustomizeColumns() {
        return Boolean(
            this.env.services.tree_view_column_layout.isAdmin && this._getColumnStorageKey()
        );
    },

    getActiveColumns(list) {
        const columns = this._withColumnLayoutMetadata(super.getActiveColumns(list));
        return this._sortColumnsBySharedOrder(this._applySharedColumnLabels(columns));
    },

    _withColumnLayoutMetadata(columns) {
        const occurrences = new Map();
        const keysByColumnId = new Map();
        for (const column of this.allColumns || columns) {
            if (column.type !== "field") {
                continue;
            }
            const occurrence = occurrences.get(column.name) || 0;
            keysByColumnId.set(column.id, `${column.name}#${occurrence}`);
            occurrences.set(column.name, occurrence + 1);
        }
        return columns.map((column) => {
            if (column.type !== "field") {
                return column;
            }
            return {
                ...column,
                layoutKey: keysByColumnId.get(column.id) || `${column.name}#0`,
                defaultLabel: column.label,
            };
        });
    },

    _applySharedColumnLabels(columns) {
        const labels = this._getColumnLayout()?.labels || {};
        return columns.map((column) => {
            const label = column.layoutKey ? labels[column.layoutKey] : null;
            return typeof label === "string" && label ? { ...column, label } : column;
        });
    },

    _sortColumnsBySharedOrder(columns) {
        const savedOrder = this._getColumnLayout()?.order || [];
        if (!savedOrder.length) {
            return columns;
        }

        const savedRank = new Map(savedOrder.map((key, index) => [key, index]));
        const indexes = [];
        const orderedColumns = [];
        columns.forEach((column, index) => {
            if (
                column.type === "field" &&
                (savedRank.has(column.layoutKey) || savedRank.has(column.name))
            ) {
                indexes.push(index);
                orderedColumns.push(column);
            }
        });
        const getRank = (column) =>
            savedRank.has(column.layoutKey)
                ? savedRank.get(column.layoutKey)
                : savedRank.get(column.name);
        orderedColumns.sort((left, right) => getRank(left) - getRank(right));
        if (orderedColumns.length < 2) {
            return columns;
        }

        const result = [...columns];
        indexes.forEach((columnIndex, index) => {
            result[columnIndex] = orderedColumns[index];
        });
        return result;
    },

    _setupColumnCustomization() {
        const table = this.tableRef?.el;
        if (!table || !table.querySelector("thead")) {
            return;
        }

        this._cleanupColumnReorderHandlers();
        table.classList.toggle("o_column_customization_disabled", !this._canCustomizeColumns());
        this._applySharedColumnWidths(table);
        if (!this._canCustomizeColumns()) {
            return;
        }

        for (const header of this._getColumnHeaders(table)) {
            header.setAttribute("draggable", "true");
            header.classList.add("o_col_reorder_draggable");

            const onDragStart = (ev) => {
                if (ev.target.closest(".o_column_label_edit")) {
                    ev.preventDefault();
                    return;
                }
                ev.dataTransfer.effectAllowed = "move";
                ev.dataTransfer.setData(
                    "text/plain",
                    header.dataset.layoutKey || header.dataset.name || ""
                );
                header.classList.add("o_col_reorder_dragging");
            };
            const onDragEnd = () => {
                header.classList.remove("o_col_reorder_dragging");
                this._clearDragIndicators(table);
            };
            const onDragOver = (ev) => {
                ev.preventDefault();
                header.classList.add("o_col_reorder_over");
            };
            const onDragLeave = () => header.classList.remove("o_col_reorder_over");
            const onDrop = (ev) => {
                ev.preventDefault();
                const sourceKey = ev.dataTransfer.getData("text/plain");
                const targetKey = header.dataset.layoutKey || header.dataset.name;
                this._clearDragIndicators(table);
                this._reorderColumnsByKey(sourceKey, targetKey);
            };

            const listeners = [
                ["dragstart", onDragStart],
                ["dragend", onDragEnd],
                ["dragover", onDragOver],
                ["dragleave", onDragLeave],
                ["drop", onDrop],
            ];
            for (const [eventName, fn] of listeners) {
                header.addEventListener(eventName, fn);
            }
            this._columnReorderHandlers.push({ element: header, listeners });
        }
    },

    _clearDragIndicators(table) {
        table
            .querySelectorAll(".o_col_reorder_over")
            .forEach((el) => el.classList.remove("o_col_reorder_over"));
    },

    _cleanupColumnReorderHandlers() {
        for (const entry of this._columnReorderHandlers) {
            for (const [eventName, fn] of entry.listeners) {
                entry.element.removeEventListener(eventName, fn);
            }
            entry.element.removeAttribute("draggable");
            entry.element.classList.remove("o_col_reorder_draggable");
        }
        this._columnReorderHandlers = [];
    },

    _cleanupColumnResizePersistenceHandlers() {
        for (const [eventName, fn] of this._columnResizePersistenceHandlers) {
            window.removeEventListener(eventName, fn);
        }
        this._columnResizePersistenceHandlers = [];
    },

    onStartResize(ev) {
        if (!this._canCustomizeColumns()) {
            return;
        }

        const header = ev.target.closest("th[data-name]");
        const columnKey = header?.dataset.layoutKey || header?.dataset.name;
        super.onStartResize(ev);
        if (!header || !columnKey) {
            return;
        }

        this._cleanupColumnResizePersistenceHandlers();
        const persistWidth = () => {
            this._cleanupColumnResizePersistenceHandlers();
            if (!header.isConnected) {
                return;
            }
            const width =
                parseInt(header.style.width, 10) ||
                parseInt(header.style.maxWidth, 10) ||
                Math.round(header.getBoundingClientRect().width);
            if (width > 0) {
                this.columnLayoutService.saveWidth(
                    this._getColumnStorageKey(),
                    columnKey,
                    width,
                    this._getColumnLayoutContext()
                );
            }
        };
        for (const eventName of ["pointerup", "keydown"]) {
            window.addEventListener(eventName, persistWidth);
            this._columnResizePersistenceHandlers.push([eventName, persistWidth]);
        }
    },

    _reorderColumnsByKey(sourceKey, targetKey) {
        if (
            !this._canCustomizeColumns() ||
            !sourceKey ||
            !targetKey ||
            sourceKey === targetKey
        ) {
            return;
        }

        const columns = [...this.state.columns];
        const sourceIndex = columns.findIndex(
            (column) =>
                column.type === "field" && (column.layoutKey || column.name) === sourceKey
        );
        const targetIndex = columns.findIndex(
            (column) =>
                column.type === "field" && (column.layoutKey || column.name) === targetKey
        );
        if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) {
            return;
        }

        const [sourceColumn] = columns.splice(sourceIndex, 1);
        columns.splice(targetIndex, 0, sourceColumn);
        this.state.columns = columns;
        const order = columns
            .filter((column) => column.type === "field" && column.layoutKey)
            .map((column) => column.layoutKey);
        this.columnLayoutService.saveOrder(
            this._getColumnStorageKey(),
            order,
            this._getColumnLayoutContext()
        );
    },

    _applySharedColumnWidths(table) {
        const widths = this._getColumnLayout()?.widths || {};
        if (!Object.keys(widths).length) {
            return;
        }

        const getPositiveWidth = (...values) => values.find((value) => value > 0) || 0;
        let tableWidth = 0;
        for (const header of this._getColumnHeaders(table)) {
            const width = getPositiveWidth(
                widths[header.dataset.layoutKey] ??
                    widths[header.dataset.name],
                parseInt(header.style.width, 10),
                parseInt(header.style.minWidth, 10)
            );
            if (!(width > 0)) {
                continue;
            }
            const widthValue = `${width}px`;
            header.style.width = widthValue;
            header.style.minWidth = widthValue;
            header.style.maxWidth = widthValue;
            tableWidth += width;
        }
        if (tableWidth > 0) {
            table.style.width = `${tableWidth}px`;
            table.style.tableLayout = "fixed";
        }
    },

    _onSharedColumnLayoutUpdated({ detail: layout }) {
        if (layout.storageKey !== this._getColumnStorageKey()) {
            return;
        }
        this.keepColumnWidths = false;
        this.columnWidths = null;
        this.state.columns = this.getActiveColumns(this.props.list);
    },

    openColumnLabelEditor(ev, column) {
        ev.stopPropagation();
        ev.preventDefault();
        if (!this._canCustomizeColumns() || !column.layoutKey) {
            return;
        }
        const labels = this._getColumnLayout()?.labels || {};
        this.dialogService.add(ColumnLabelDialog, {
            title: _t("Đổi tên cột"),
            label: column.label || "",
            defaultLabel: column.defaultLabel || column.label || "",
            canReset: Object.prototype.hasOwnProperty.call(labels, column.layoutKey),
            save: (label) =>
                this.columnLayoutService.saveLabel(
                    this._getColumnStorageKey(),
                    column.layoutKey,
                    label,
                    this._getColumnLayoutContext()
                ),
            reset: () =>
                this.columnLayoutService.saveLabel(
                    this._getColumnStorageKey(),
                    column.layoutKey,
                    null,
                    this._getColumnLayoutContext()
                ),
        });
    },

    resetColumnLayout() {
        if (this._canCustomizeColumns()) {
            this.columnLayoutService.reset(
                this._getColumnStorageKey(),
                this._getColumnLayoutContext()
            );
        }
    },
});

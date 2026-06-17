/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { usePopover } from "@web/core/popover/popover_hook";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { Component, useState, onWillStart, onWillDestroy, onMounted } from "@odoo/owl";

/* ===================== POPOVER ===================== */
export class UserPopover extends Component {
    static props = {
        resIds: { type: Array, optional: true },
        record: { type: Object, optional: true },
        fieldName: { type: String, optional: true },
        close: { type: Function, optional: true },
        '*': true,
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.action = useService("action");

        this.isAlive = true;
        this.record = this.props.record;
        this.fieldName = this.props.fieldName;
        this.currentIds = [...(this.props.resIds || [])];
        this.scrollElement = null;

        this.state = useState({
            users: [],
            isLoading: false,
        });

        onWillStart(async () => {
            await this.loadUsers();
        });

        onMounted(() => {
            if (this.el && this.el.isConnected) {
                this._setupPassiveScroll();
            }
        });

        onWillDestroy(() => {
            this.isAlive = false;
            if (this.scrollElement) {
                this.scrollElement = null;
            }
        });
    }

    _setupPassiveScroll() {
        try {
            if (!this.el || !this.el.isConnected) return;

            const scrollContainer = this.el.querySelector('.o_popover_scroll');
            if (scrollContainer && scrollContainer.isConnected) {
                this.scrollElement = scrollContainer;
                scrollContainer.addEventListener('wheel', () => {}, { passive: true });
                scrollContainer.addEventListener('touchstart', () => {}, { passive: true });
                scrollContainer.addEventListener('touchmove', () => {}, { passive: true });
            }
        } catch (error) {
            console.warn("Error setting up passive scroll:", error);
        }
    }

    loadUsers = async () => {
        if (!this.isAlive) return;

        try {
            this.state.isLoading = true;
            const ids = this.currentIds;

            if (!ids.length) {
                if (this.isAlive) {
                    this.state.users = [];
                }
                return;
            }

            const users = await this.orm.read("res.users", ids, ["name"]);

            if (this.isAlive) {
                this.state.users = (users || []).filter(u => u && u.id);
            }
        } catch (error) {
            console.error("Error loading users:", error);
            if (this.isAlive) {
                this.state.users = [];
            }
        } finally {
            if (this.isAlive) {
                this.state.isLoading = false;
            }
        }
    }

    removeUser = async (userId) => {
        if (!this.isAlive) return;

        const newIds = this.currentIds.filter(id => id !== userId);

        try {
            await this.record.update({
                [this.fieldName]: [[6, 0, newIds]],
            });

            if (this.isAlive) {
                this.currentIds = newIds;
                this.props.resIds = newIds;
                await this.loadUsers();
            }
        } catch (error) {
            console.error("Error removing user:", error);
            this.notification.add("Có lỗi xảy ra khi xóa người xem", { type: "danger" });
        }
    }

    addUsers = () => {
        if (!this.isAlive) return;

        const record = this.record;
        const fieldName = this.fieldName;
        const currentIds = [...this.currentIds];
        const notification = this.notification;
        const self = this;
        const closePopover = this.props.close; // Lấy hàm close để đóng popover

        // Sử dụng setTimeout để đảm bảo an toàn
        setTimeout(() => {
            if (!self.isAlive) return;

            self.dialog.add(SelectCreateDialog, {
                resModel: "res.users",
                title: "Chọn người xem hợp đồng",
                multiSelect: true,
                domain: [["id", "not in", currentIds]],
                context: {
                    search_default_hide_archived: true,
                    create: false,
                },
                onSelected: async (selectedRecords) => {
                    try {
                        if (!selectedRecords || !selectedRecords.length) {
                            return;
                        }

                        const selectedIds = Array.isArray(selectedRecords) ? selectedRecords : [selectedRecords];
                        const newIds = [...new Set([...currentIds, ...selectedIds])];

                        await record.update({
                            [fieldName]: [[6, 0, newIds]],
                        });

                        if (self.isAlive) {
                            self.currentIds = newIds;
                            self.props.resIds = newIds;
                            await self.loadUsers();
                        }

                        // Đóng popover sau khi thêm thành công
                        if (closePopover && typeof closePopover === 'function') {
                            closePopover();
                        }
                    } catch (error) {
                        console.error("Error in onSelected:", error);
                        notification.add("Có lỗi xảy ra khi thêm người xem", {
                            type: "danger",
                        });
                    }
                },
            });
        }, 0);
    }
}

UserPopover.template = "sonha_ql_xuat_khau.UserPopover";

/* ===================== MAIN WIDGET ===================== */
export class M2MUserWidget extends Component {
    static props = {
        record: { type: Object, optional: true },
        name: { type: String, optional: true },
        readonly: { type: Boolean, optional: true },
        id: { type: String, optional: true },
        className: { type: String, optional: true },
        fieldInfo: { type: Object, optional: true },
        mode: { type: String, optional: true },
        '*': true,
    };

    setup() {
        this.popover = usePopover(this.constructor.components.Popover, {
            position: "top",
        });
        this.isAlive = true;

        onWillDestroy(() => {
            this.isAlive = false;
        });
    }

    get value() {
        if (!this.props.record || !this.props.name) {
            return { resIds: [] };
        }
        const val = this.props.record.data?.[this.props.name];
        return val && val.resIds ? val : { resIds: [] };
    }

    get count() {
        return this.value.resIds?.length || 0;
    }

    get isReadonly() {
        return this.props.readonly || false;
    }

    showPopup = (ev) => {
        if (this.isReadonly || !this.isAlive) return;

        const currentValue = this.value;
        const target = ev.currentTarget;

        if (!target || !target.isConnected) return;

        // Sử dụng setTimeout để defer việc mở popover
        setTimeout(() => {
            if (!this.isAlive) return;

            this.popover.open(target, {
                resIds: [...(currentValue.resIds || [])],
                record: this.props.record,
                fieldName: this.props.name,
            });
        }, 0);
    }
}

M2MUserWidget.components = { Popover: UserPopover };
M2MUserWidget.template = "sonha_ql_xuat_khau.M2MUserWidget";

/* ===================== REGISTER ===================== */
registry.category("fields").add("m2m_user_widget", {
    component: M2MUserWidget,
});
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, onWillStart, onWillDestroy, status } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ProcessingCountdownField extends Component {
    static template = "topic_chatbot.ProcessingCountdownField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.busService = this.env.services.bus_service;
        this.actionService = useService("action");
        
        this.state = useState({
            statusText: "",
            remainingSeconds: 0,
            percent: 0,
            isCompleted: false,
            isError: false,
            errorMessage: "",
            realtimeActive: false,
        });

        this.interval = null;

        onWillStart(() => {
            this.updateCountdown();
            this.startTimer();

            // Subscribe to bus notifications for realtime progress and completion
            if (this.busService) {
                this.busService.addChannel("broadcast");
                this.busService.subscribe("topic_chatbot.document/status_changed", (payload) => {
                    this.onStatusChanged(payload);
                });
                this.busService.subscribe("topic_chatbot.document/progress", (payload) => {
                    this.onProgress(payload);
                });
            }
        });

        onWillDestroy(() => {
            this.clearTimer();
        });
    }

    get record() {
        return this.props.record;
    }

    get documentState() {
        return this.record.data.state;
    }

    get documentId() {
        return this.record.resId;
    }

    startTimer() {
        this.clearTimer();
        this.interval = setInterval(() => {
            this.updateCountdown();
        }, 1000);
    }

    clearTimer() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    onProgress(payload) {
        if (!payload || payload.document_id !== this.documentId) {
            return;
        }
        if (status(this) === "destroyed") {
            return;
        }

        this.state.realtimeActive = true;
        const progressPct = Math.min(99, Math.max(1, Math.round(payload.progress_pct || 0)));
        this.state.percent = progressPct;

        const processed = (payload.processed_chunks || 0).toLocaleString();
        const total = (payload.total_chunks || 0).toLocaleString();
        const eta = payload.eta_str || "";

        let text = `Đang tạo vector embeddings: ${processed}/${total} đoạn (${progressPct}%)`;
        if (eta) {
            text += ` — Còn khoảng ${eta}`;
        }
        this.state.statusText = text;
    }

    onStatusChanged(payload) {
        if (!payload || payload.document_id !== this.documentId) {
            return;
        }
        if (status(this) === "destroyed") {
            return;
        }

        if (payload.state === "done" || payload.state === "partial") {
            this.clearTimer();
            this.state.isCompleted = true;
            this.state.percent = 100;
            this.state.statusText = "Tài liệu đã sẵn sàng! Bạn có thể bắt đầu đặt câu hỏi với Chatbot.";
            if (status(this) !== "destroyed" && this.actionService) {
                this.actionService.doAction({ type: "ir.actions.client", tag: "reload" });
            }
        } else if (payload.state === "error") {
            this.clearTimer();
            this.state.isError = true;
            this.state.errorMessage = payload.error_message || "Đã xảy ra lỗi trong quá trình xử lý.";
            if (status(this) !== "destroyed" && this.actionService) {
                this.actionService.doAction({ type: "ir.actions.client", tag: "reload" });
            }
        }
    }

    updateCountdown() {
        const state = this.documentState;
        if (state !== "processing") {
            if (state === "done" || state === "partial") {
                this.state.isCompleted = true;
                this.state.percent = 100;
                this.state.statusText = "Tài liệu đã sẵn sàng! Bạn có thể bắt đầu đặt câu hỏi với Chatbot.";
            } else if (state === "error") {
                this.state.isError = true;
                this.state.errorMessage = this.record.data.error_message || "Xử lý tài liệu thất bại.";
            }
            this.clearTimer();
            return;
        }

        // If realtime batch events are actively updating the UI, keep the realtime display
        if (this.state.realtimeActive) {
            return;
        }

        const totalEstSeconds = this.record.data.estimated_seconds || 30;
        const startTimeStr = this.record.data.processing_start_time;

        let elapsedSec = 0;
        if (startTimeStr) {
            try {
                const cleanTimeStr = startTimeStr.replace(" ", "T") + (startTimeStr.includes("Z") ? "" : "Z");
                const startTime = new Date(cleanTimeStr);
                const now = new Date();
                elapsedSec = Math.max(0, Math.floor((now.getTime() - startTime.getTime()) / 1000));
            } catch (e) {
                elapsedSec = 0;
            }
        }

        const remaining = Math.max(0, totalEstSeconds - elapsedSec);
        this.state.remainingSeconds = remaining;

        if (remaining > 0) {
            const rawPercent = Math.min(95, Math.floor((elapsedSec / totalEstSeconds) * 100));
            this.state.percent = Math.max(5, rawPercent);
            
            let timeStr = "";
            if (remaining >= 3600) {
                const hours = Math.floor(remaining / 3600);
                const mins = Math.floor((remaining % 3600) / 60);
                timeStr = `${hours} giờ ${mins} phút`;
            } else if (remaining >= 60) {
                const mins = Math.floor(remaining / 60);
                const secs = remaining % 60;
                const secPad = secs < 10 ? "0" + secs : secs;
                timeStr = `${mins} phút ${secPad} giây`;
            } else {
                timeStr = `${remaining} giây`;
            }
            this.state.statusText = "Đang trích xuất văn bản & vector hóa tri thức... Còn khoảng " + timeStr + " (ước tính)";
        } else {
            this.state.percent = 96;
            this.state.statusText = "Đang hoàn tất lưu trữ vector embeddings cuối cùng, sắp xong...";
        }
    }
}

export const processingCountdownField = {
    component: ProcessingCountdownField,
    displayName: "Processing Countdown",
    supportedTypes: ["char"],
};

registry.category("fields").add("processing_countdown", processingCountdownField);

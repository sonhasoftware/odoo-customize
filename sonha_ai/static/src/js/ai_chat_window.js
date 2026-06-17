/** @odoo-module **/

import { Component, useState, useRef, onPatched, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class AiChatWindow extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.menuService = useService("menu");
        
        this.chatBodyRef = useRef("chatBody");
        this.chatWindowRef = useRef("chatWindow");
        
        this.dragState = {
            isDragging: false,
            startX: 0, startY: 0,
            initialX: 0, initialY: 0,
            hasMoved: false
        };
        
        this.state = useState({
            messages: [{
                id: 1,
                role: 'ai',
                content: 'Xin chào! Tôi có thể giúp gì cho bạn hôm nay?',
                formattedContent: markup('Xin chào! Tôi có thể giúp gì cho bạn hôm nay?')
            }],
            inputValue: "",
            isTyping: false,
            isFullScreen: false,
            isMinimized: false,
        });

        onPatched(() => {
            if (!this.state.isMinimized) {
                this._scrollToBottom();
                this._renderCharts();
            }
        });
    }

    _onDragStart(ev) {
        if (!this.state.isMinimized) return;
        ev.preventDefault();
        
        this.dragState.isDragging = true;
        this.dragState.hasMoved = false;
        this.dragState.startX = ev.clientX;
        this.dragState.startY = ev.clientY;
        
        const rect = this.chatWindowRef.el.getBoundingClientRect();
        this.dragState.initialX = rect.left;
        this.dragState.initialY = rect.top;

        this._onDragMoveBound = this._onDragMove.bind(this);
        this._onDragEndBound = this._onDragEnd.bind(this);
        window.addEventListener("pointermove", this._onDragMoveBound);
        window.addEventListener("pointerup", this._onDragEndBound);
        
        // Tắt CSS transition khi đang kéo để tránh bị delay
        this.chatWindowRef.el.style.transition = 'none';
    }

    _onDragMove(ev) {
        if (!this.dragState.isDragging) return;
        
        const dx = ev.clientX - this.dragState.startX;
        const dy = ev.clientY - this.dragState.startY;
        
        // If moved more than 3 pixels, consider it a drag
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
            this.dragState.hasMoved = true;
        }
        
        if (this.dragState.hasMoved && this.chatWindowRef.el) {
            let newX = this.dragState.initialX + dx;
            let newY = this.dragState.initialY + dy;
            
            // Boundary checks to keep it inside screen
            const maxX = window.innerWidth - 60; // 60 is logo width
            const maxY = window.innerHeight - 60;
            newX = Math.max(0, Math.min(newX, maxX));
            newY = Math.max(0, Math.min(newY, maxY));
            
            this.chatWindowRef.el.style.bottom = 'auto';
            this.chatWindowRef.el.style.right = 'auto';
            this.chatWindowRef.el.style.left = `${newX}px`;
            this.chatWindowRef.el.style.top = `${newY}px`;
        }
    }

    _onDragEnd(ev) {
        this.dragState.isDragging = false;
        window.removeEventListener("pointermove", this._onDragMoveBound);
        window.removeEventListener("pointerup", this._onDragEndBound);
        
        // Phục hồi lại CSS transition sau khi kéo xong
        if (this.chatWindowRef.el) {
            this.chatWindowRef.el.style.transition = '';
        }
    }

    _onRootClick(ev) {
        if (!this.state.isMinimized) return;
        this._onLogoClick(ev);
    }

    _onLogoClick() {
        if (this.dragState.hasMoved) return;
        this._toggleMinimize();
    }

    _toggleFullScreen() {
        this.state.isFullScreen = !this.state.isFullScreen;
        if (this.state.isFullScreen) this.state.isMinimized = false;
    }

    _toggleMinimize() {
        this.state.isMinimized = !this.state.isMinimized;
        if (this.state.isMinimized) {
            this.state.isFullScreen = false;
        } else {
            if (this.chatWindowRef.el) {
                this.chatWindowRef.el.style.left = '';
                this.chatWindowRef.el.style.top = '';
                this.chatWindowRef.el.style.right = '';
                this.chatWindowRef.el.style.bottom = '';
            }
        }
    }

    async _renderCharts() {
        const messagesWithCharts = this.state.messages.filter(m => (m.chartData || m.multiChartData) && !m.chartRendered);
        if (messagesWithCharts.length === 0) return;

        try {
            if (!window.Chart) {
                await loadJS("https://cdn.jsdelivr.net/npm/chart.js");
            }
            
            for (const msg of messagesWithCharts) {
                if (msg.chartData) {
                    const canvasId = `chart_${msg.id}`;
                    const canvas = document.getElementById(canvasId);
                    if (canvas) {
                        if (window.IntersectionObserver) {
                            let observer = new IntersectionObserver((entries, obs) => {
                                entries.forEach(entry => {
                                    if (entry.isIntersecting) {
                                        this._initChartJs(canvas, msg.chartData);
                                        obs.unobserve(canvas);
                                    }
                                });
                            }, { root: null, rootMargin: '200px' });
                            observer.observe(canvas);
                        } else {
                            this._initChartJs(canvas, msg.chartData);
                        }
                    }
                }
                
                if (msg.multiChartData) {
                    msg.multiChartData.forEach((chartData, index) => {
                        const canvasId = `chart_${msg.id}_${index}`;
                        const canvas = document.getElementById(canvasId);
                        if (canvas) {
                            if (window.IntersectionObserver) {
                                let observer = new IntersectionObserver((entries, obs) => {
                                    entries.forEach(entry => {
                                        if (entry.isIntersecting) {
                                            this._initChartJs(canvas, chartData);
                                            obs.unobserve(canvas);
                                        }
                                    });
                                }, { root: null, rootMargin: '200px' });
                                observer.observe(canvas);
                            } else {
                                this._initChartJs(canvas, chartData);
                            }
                        }
                    });
                }
                
                msg.chartRendered = true;
            }
        } catch (e) {
            console.error("Lỗi khi load Chart.js", e);
        }
    }

    _initChartJs(canvas, chartData) {
        let chartType = chartData.chart_type || 'bar';
        let chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: chartData.labels.length <= 10,
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        font: { size: 11 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) { label += ': '; }
                            if (context.parsed.y !== null && context.parsed.y !== undefined && context.parsed.x === undefined) {
                                label += context.parsed.y;
                            } else if (context.parsed.x !== null && context.parsed.x !== undefined) {
                                label += context.parsed.x;
                            } else {
                                label += context.parsed;
                            }
                            return label;
                        }
                    }
                }
            }
        };
        
        if (chartType === 'horizontalBar') {
            chartType = 'bar';
            chartOptions.indexAxis = 'y';
            
            // Ensure each bar has enough vertical space
            const requiredHeight = Math.max(300, chartData.labels.length * 35);
            canvas.parentElement.style.height = `${requiredHeight}px`;
        } else {
            canvas.parentElement.style.height = '400px';
        }

        new Chart(canvas, {
            type: chartType,
            data: chartData,
            options: chartOptions
        });
    }

    _formatMarkdown(text) {
        if (!text) return "";
        let html = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        html = html.replace(/^### (.*$)/gim, '<strong>$1</strong>');
        html = html.replace(/^## (.*$)/gim, '<strong>$1</strong>');
        html = html.replace(/^# (.*$)/gim, '<strong>$1</strong>');
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*([^\*]+)\*/g, '<em>$1</em>');
        html = html.replace(/`(.*?)`/g, '<code>$1</code>');
        html = html.replace(/^\* (.*$)/gim, '• $1');
        html = html.replace(/^- (.*$)/gim, '• $1');
        return html;
    }

    _scrollToBottom() {
        if (this.chatBodyRef.el) {
            this.chatBodyRef.el.scrollTop = this.chatBodyRef.el.scrollHeight;
        }
    }

    _useSuggestion(text) {
        this.state.inputValue = text;
        this._sendMessage();
    }

    _onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this._sendMessage();
        }
    }

    async _sendMessage() {
        const text = this.state.inputValue.trim();
        if (!text || this.state.isTyping) return;

        this.state.messages.push({
            id: Date.now(),
            role: 'user',
            content: text,
            formattedContent: markup(this._formatMarkdown(text))
        });
        
        this.state.inputValue = "";
        this.state.isTyping = true;

        const hash = window.location.hash;
        const modelMatch = hash.match(/model=([^&]+)/);
        const idMatch = hash.match(/id=([^&]+)/);
        const modelName = modelMatch ? modelMatch[1] : null;
        const recordId = idMatch ? parseInt(idMatch[1]) : null;

        try {
            const response = await this.rpc("/sonha_ai/chat", {
                prompt: text,
                model_name: modelName,
                record_id: recordId,
                chatter_messages: [] 
            });
            
            if (response.error) {
                this.state.messages.push({
                    id: Date.now(),
                    role: 'ai',
                    content: `Lỗi: ${response.error}`
                });
            } else {
                this.state.messages.push({
                    id: Date.now(),
                    role: 'ai',
                    content: response.result || "Không có phản hồi.",
                    formattedContent: markup(this._formatMarkdown(response.result || "Không có phản hồi.")),
                    chartData: response.chartData,
                    multiChartData: response.multiChartData,
                    fileData: response.fileData,
                    filename: response.filename
                });
                
                if (response.menu_id) {
                    this.menuService.selectMenu(response.menu_id);
                } else if (response.action_id) {
                    this.actionService.doAction(response.action_id);
                } else if (response.action === 'orm_create_draft') {
                    this.actionService.doAction({
                        type: 'ir.actions.act_window',
                        res_model: response.model,
                        views: [[false, 'form']],
                        target: 'new',
                        context: response.context || {}
                    });
                }
            }
        } catch (error) {
            this.state.messages.push({
                id: Date.now(),
                role: 'ai',
                content: `Lỗi kết nối tới server Odoo. Chi tiết JS Error: ${error.message || error.name || JSON.stringify(error)}`
            });
            console.error("Sonha AI JS Error:", error);
        } finally {
            this.state.isTyping = false;
            // Tự động dọn rác DOM: Chỉ giữ lại 20 tin nhắn gần nhất để chống lag trình duyệt
            if (this.state.messages.length > 20) {
                this.state.messages.splice(0, this.state.messages.length - 20);
            }
        }
    }

    _copyMessage(content) {
        navigator.clipboard.writeText(content).then(() => {
            this.notification.add("Đã copy vào clipboard", { type: "success" });
        });
    }

    async _logAsNote(content) {
        const hash = window.location.hash;
        const modelMatch = hash.match(/model=([^&]+)/);
        const idMatch = hash.match(/id=([^&]+)/);
        
        if (modelMatch && idMatch) {
            try {
                await this.rpc("/mail/message/post", {
                    thread_model: modelMatch[1],
                    thread_id: parseInt(idMatch[1]),
                    post_data: {
                        body: content,
                        message_type: 'comment',
                        subtype_xmlid: 'mail.mt_note',
                    }
                });
                this.notification.add("Đã lưu thành ghi chú trong chatter", { type: "success" });
            } catch (e) {
                this.notification.add("Không thể lưu ghi chú. Có thể model này không hỗ trợ chatter.", { type: "danger" });
            }
        } else {
            this.notification.add("Bạn cần mở một bản ghi cụ thể để lưu ghi chú.", { type: "warning" });
        }
    }

    async _sendAsMessage(content) {
        const hash = window.location.hash;
        const modelMatch = hash.match(/model=([^&]+)/);
        const idMatch = hash.match(/id=([^&]+)/);
        
        if (modelMatch && idMatch) {
            try {
                await this.rpc("/mail/message/post", {
                    thread_model: modelMatch[1],
                    thread_id: parseInt(idMatch[1]),
                    post_data: {
                        body: content,
                        message_type: 'comment',
                        subtype_xmlid: 'mail.mt_comment',
                    }
                });
                this.notification.add("Đã gửi tin nhắn vào chatter", { type: "success" });
            } catch (e) {
                this.notification.add("Không thể gửi tin nhắn.", { type: "danger" });
            }
        } else {
            this.notification.add("Bạn cần mở một bản ghi cụ thể để gửi tin nhắn.", { type: "warning" });
        }
    }
}
AiChatWindow.template = "sonha_ai.ChatWindow";

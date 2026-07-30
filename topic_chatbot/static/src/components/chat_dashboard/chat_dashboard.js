/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, useRef, useEffect, markup } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const _ = _t;

class ChatbotDashboard extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.chatContainer = useRef("chatContainer");
        this.inputRef = useRef("inputMessageRef");

        this.state = useState({
            topics: [],
            selectedTopicId: null,
            conversations: [],
            activeConversationId: null,
            messages: [],
            inputMessage: "",
            isLoading: false,
            isSending: false,
            showDeleteConfirm: false,
            conversationToDeleteId: null,
        });


        onWillStart(async () => {
            await this.loadTopics();
        });

        // Automatically scroll to bottom on new messages
        useEffect(() => {
            this.scrollToBottom();
        }, () => [this.state.messages.length, this.state.isSending]);
    }

    async loadTopics() {
        try {
            const result = await this.rpc("/topic_chatbot/get_topics", {});
            this.state.topics = result || [];
        } catch (error) {
            this.notification.add(_("Lỗi khi tải danh sách chủ đề: ") + error.message, { type: "danger" });
        }
    }

    async selectTopic(topicId) {
        this.state.selectedTopicId = topicId;
        this.state.activeConversationId = null;
        this.state.messages = [];
        await this.loadConversations(topicId);
    }

    async loadConversations(topicId) {
        try {
            this.state.isLoading = true;
            const result = await this.rpc("/topic_chatbot/get_conversations", { topic_id: topicId });
            this.state.conversations = result || [];
            this.state.isLoading = false;
        } catch (error) {
            this.state.isLoading = false;
            this.notification.add(_("Lỗi khi tải lịch sử hội thoại: ") + error.message, { type: "danger" });
        }
    }

    async selectConversation(conversationId) {
        this.state.activeConversationId = conversationId;
        await this.loadMessages(conversationId);
    }

    async loadMessages(conversationId) {
        try {
            this.state.isLoading = true;
            const result = await this.rpc("/topic_chatbot/get_messages", { conversation_id: conversationId });
            this.state.messages = result || [];
            this.state.isLoading = false;
        } catch (error) {
            this.state.isLoading = false;
            this.notification.add(_("Lỗi khi tải tin nhắn: ") + error.message, { type: "danger" });
        }
    }

    async startNewConversation() {
        if (!this.state.selectedTopicId) return;
        try {
            const result = await this.rpc("/topic_chatbot/create_conversation", { topic_id: this.state.selectedTopicId });
            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
                return;
            }
            this.state.conversations.unshift(result);
            this.state.activeConversationId = result.id;
            this.state.messages = [];
            
            // Focus on input box
            setTimeout(() => {
                if (this.inputRef.el) this.inputRef.el.focus();
            }, 100);
        } catch (error) {
            this.notification.add(_("Lỗi khi tạo hội thoại mới: ") + error.message, { type: "danger" });
        }
    }

    async deleteConversation(conversationId, ev) {
        if (ev) ev.stopPropagation();
        this.state.conversationToDeleteId = conversationId;
        this.state.showDeleteConfirm = true;
    }

    cancelDelete() {
        this.state.showDeleteConfirm = false;
        this.state.conversationToDeleteId = null;
    }

    async confirmDelete() {
        const conversationId = this.state.conversationToDeleteId;
        if (!conversationId) return;

        try {
            const result = await this.rpc("/topic_chatbot/delete_conversation", { conversation_id: conversationId });
            if (result.success) {
                this.state.conversations = this.state.conversations.filter(c => c.id !== conversationId);
                if (this.state.activeConversationId === conversationId) {
                    this.state.activeConversationId = null;
                    this.state.messages = [];
                }
            } else {
                this.notification.add(result.error || "Không thể xóa hội thoại", { type: "danger" });
            }
        } catch (error) {
            this.notification.add(_("Lỗi khi xóa hội thoại: ") + error.message, { type: "danger" });
        } finally {
            this.cancelDelete();
        }
    }


    async sendMessage() {
        const text = this.state.inputMessage.trim();
        if (!text || this.state.isSending || !this.state.activeConversationId) return;

        this.state.inputMessage = "";

        const userMsgId = Date.now();
        this.state.messages.push({
            id: userMsgId,
            role: "user",
            content: text,
            create_date: new Date()
        });

        const botMsgId = Date.now() + 1;
        this.state.messages.push({
            id: botMsgId,
            role: "model",
            content: "",
            create_date: new Date(),
            isStreaming: true
        });

        this.state.isSending = true;

        try {
            const response = await fetch("/topic_chatbot/ask_stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    conversation_id: this.state.activeConversationId,
                    message: text
                })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const event = JSON.parse(line.slice(6));
                            this._handleStreamEvent(event, botMsgId);
                        } catch (_e) {
                            // skip malformed event
                        }
                    }
                }
            }
        } catch (error) {
            const botMsg = this.state.messages.find(m => m.id === botMsgId);
            if (botMsg) {
                botMsg.content = "Đã xảy ra lỗi kết nối: " + error.message;
                botMsg.isStreaming = false;
            }
        } finally {
            const botMsg = this.state.messages.find(m => m.id === botMsgId);
            if (botMsg) {
                botMsg.isStreaming = false;
            }
            this.state.isSending = false;
        }
    }

    _handleStreamEvent(event, botMsgId) {
        const botMsg = this.state.messages.find(m => m.id === botMsgId);
        if (!botMsg) return;

        switch (event.type) {
            case "token":
                botMsg.content += event.content;
                break;
            case "error":
                botMsg.content = event.content;
                botMsg.isStreaming = false;
                break;
            case "done":
                botMsg.isStreaming = false;
                if (event.conversation_name) {
                    const conv = this.state.conversations.find(
                        c => c.id === this.state.activeConversationId
                    );
                    if (conv) conv.name = event.conversation_name;
                }
                break;
            // "status" events are ignored (shown via typing indicator already)
        }
    }

    handleKeyPress(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    scrollToBottom() {
        if (this.chatContainer.el) {
            this.chatContainer.el.scrollTop = this.chatContainer.el.scrollHeight;
        }
    }

    formatMarkdown(text) {
        if (!text) return "";
        let cleaned = text.replace(/<br\s*\/?>/gi, "\n");
        const codeBlocks = [];
        cleaned = cleaned.replace(/```([\s\S]*?)```/g, (match, code) => {
            const index = codeBlocks.length;
            const escapedCode = code.trim()
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;");
            codeBlocks.push(`<div class="md-code-block-wrap"><button class="md-copy-btn" onclick="copyCode(this)" data-code="${escapedCode}" title="Copy code"><i class="fa fa-copy"></i></button><pre class="md-code-block"><code>${escapedCode}</code></pre></div>`);
            return `\n@@CODEBLOCK_${index}@@\n`;
        });

        let escaped = cleaned
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        const applyInlineMarkdown = (value) => value
            .replace(/`([^`\n]+)`/g, "<code class='md-inline-code'>$1</code>")
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/\*([^*]+)\*/g, "<em>$1</em>");

        const splitTableRow = (line) => line
            .trim()
            .replace(/^\|/, "")
            .replace(/\|$/, "")
            .split("|")
            .map((cell) => applyInlineMarkdown(cell.trim()));

        const lines = escaped.split("\n");
        const blocks = [];
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            const codeMatch = line.match(/^@@CODEBLOCK_(\d+)@@$/);
            if (codeMatch) {
                blocks.push(codeBlocks[Number(codeMatch[1])] || "");
                continue;
            }
            if (!line) {
                blocks.push("");
                continue;
            }

            const nextLine = (lines[i + 1] || "").trim();
            if (line.startsWith("|") && /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(nextLine)) {
                const headerCells = splitTableRow(line);
                i += 2;
                const bodyRows = [];
                while (i < lines.length && lines[i].trim().startsWith("|")) {
                    bodyRows.push(splitTableRow(lines[i]));
                    i++;
                }
                i--;
                const header = headerCells.map((cell) => `<th>${cell}</th>`).join("");
                const body = bodyRows
                    .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
                    .join("");
                blocks.push(`<div class="md-table-wrap"><table class="md-table"><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></div>`);
                continue;
            }

            const heading = line.match(/^(#{1,4})\s+(.+)$/);
            if (heading) {
                const level = Math.min(heading[1].length, 4);
                blocks.push(`<h${level + 2} class="md-heading md-heading-${level}">${applyInlineMarkdown(heading[2])}</h${level + 2}>`);
                continue;
            }

            const bullet = line.match(/^[-*]\s+(.+)$/);
            if (bullet) {
                blocks.push(`<div class="md-list-item"><span class="md-list-marker">•</span><span>${applyInlineMarkdown(bullet[1])}</span></div>`);
                continue;
            }

            const numbered = line.match(/^(\d+)\.\s+(.+)$/);
            if (numbered) {
                blocks.push(`<div class="md-list-item"><span class="md-list-marker">${numbered[1]}.</span><span>${applyInlineMarkdown(numbered[2])}</span></div>`);
                continue;
            }

            blocks.push(`<div class="md-paragraph">${applyInlineMarkdown(line)}</div>`);
        }

        const formatted = blocks.join("");

        return markup(formatted);

    }
}

ChatbotDashboard.template = "topic_chatbot.ChatbotDashboard";
registry.category("actions").add("topic_chatbot.dashboard", ChatbotDashboard);

window.copyCode = function (btn) {
    const code = btn.getAttribute("data-code");
    navigator.clipboard.writeText(code).then(() => {
        const icon = btn.querySelector("i");
        icon.className = "fa fa-check";
        setTimeout(() => { icon.className = "fa fa-copy"; }, 2000);
    }).catch(() => {
        // clipboard not available
    });
};

export { ChatbotDashboard };

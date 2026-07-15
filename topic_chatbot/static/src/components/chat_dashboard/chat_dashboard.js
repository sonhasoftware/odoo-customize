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

        // Clean input
        this.state.inputMessage = "";

        // Instantly push user message to UI
        this.state.messages.push({
            id: Date.now(), // temporary client-side ID
            role: "user",
            content: text,
            create_date: new Date()
        });

        this.state.isSending = true;

        try {
            const result = await this.rpc("/topic_chatbot/ask", {
                conversation_id: this.state.activeConversationId,
                message: text
            });

            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
                // Remove the failed user message
                this.state.messages.pop();
            } else {
                // Update conversation list name if it was updated from 'New Chat'
                const currentConv = this.state.conversations.find(c => c.id === this.state.activeConversationId);
                if (currentConv && result.conversation_name) {
                    currentConv.name = result.conversation_name;
                }

                // Add assistant response
                this.state.messages.push({
                    id: Date.now() + 1,
                    role: "model",
                    content: result.response,
                    create_date: new Date()
                });
            }
        } catch (error) {
            this.notification.add(_("Lỗi kết nối API: ") + error.message, { type: "danger" });
            this.state.messages.push({
                id: Date.now() + 1,
                role: "model",
                content: "Đã xảy ra lỗi kết nối: " + error.message,
                create_date: new Date()
            });
        } finally {
            this.state.isSending = false;
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
        let formatted = cleaned
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");


        // Code blocks
        formatted = formatted.replace(/```([\s\S]*?)```/g, (match, code) => {
            return `<pre class="bg-gray-800 text-white p-3 rounded my-2 overflow-x-auto font-mono text-sm"><code>${code.trim()}</code></pre>`;
        });

        // Inline code
        formatted = formatted.replace(/`([^`\n]+)`/g, "<code class='bg-gray-200 text-red-600 px-1 py-0.5 rounded font-mono text-xs'>$1</code>");

        // Bold
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

        // Italic
        formatted = formatted.replace(/\*([^*]+)\*/g, "<em>$1</em>");

        // Bullet lists
        formatted = formatted.replace(/^\s*[-*]\s+(.+)$/gm, "<li class='ml-4 list-disc mt-1'>$1</li>");

        // Line breaks
        formatted = formatted.replace(/\n/g, "<br/>");

        return markup(formatted);

    }
}

ChatbotDashboard.template = "topic_chatbot.ChatbotDashboard";
registry.category("actions").add("topic_chatbot.dashboard", ChatbotDashboard);
export { ChatbotDashboard };

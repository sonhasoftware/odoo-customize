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

        this.userHasScrolledUp = false;

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

        // Automatically scroll to bottom on new messages if user hasn't scrolled up
        useEffect(() => {
            this.scrollToBottom();
        }, () => [this.state.messages.length, this.state.isSending, (this.state.messages[this.state.messages.length - 1] || {}).content]);
    }

    onChatScroll(ev) {
        if (!this.chatContainer.el) return;
        const el = this.chatContainer.el;
        const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        // If user scrolled up more than 80px from bottom, pause auto-scroll
        this.userHasScrolledUp = distFromBottom > 80;
    }

    scrollToBottom(force = false) {
        if (!this.chatContainer.el) return;
        if (force || !this.userHasScrolledUp) {
            this.chatContainer.el.scrollTop = this.chatContainer.el.scrollHeight;
        }
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
        this.userHasScrolledUp = false;
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
        this.userHasScrolledUp = false;
        await this.loadMessages(conversationId);
        setTimeout(() => this.scrollToBottom(true), 50);
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
            this.userHasScrolledUp = false;
            
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
        this.userHasScrolledUp = false;

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
        setTimeout(() => this.scrollToBottom(true), 30);

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
            this.scrollToBottom();
        }
    }

    _handleStreamEvent(event, botMsgId) {
        const botMsg = this.state.messages.find(m => m.id === botMsgId);
        if (!botMsg) return;

        switch (event.type) {
            case "token":
                botMsg.content += event.content;
                botMsg.statusText = "";
                this.scrollToBottom();
                break;
            case "status":
                botMsg.statusText = event.content;
                this.scrollToBottom();
                break;
            case "error":
                botMsg.content = event.content;
                botMsg.statusText = "";
                botMsg.isStreaming = false;
                break;
            case "done":
                botMsg.isStreaming = false;
                botMsg.statusText = "";
                if (event.conversation_name) {
                    const conv = this.state.conversations.find(
                        c => c.id === this.state.activeConversationId
                    );
                    if (conv) conv.name = event.conversation_name;
                }
                this.scrollToBottom();
                break;
        }
    }

    handleKeyPress(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    _escapeHtml(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    _sanitizeHtml(rawHtml) {
        if (!rawHtml) return "";
        try {
            const parser = new DOMParser();
            const doc = parser.parseFromString(rawHtml, "text/html");
            const allowedTags = new Set([
                "H1", "H2", "H3", "H4", "H5", "H6", "P", "UL", "OL", "LI",
                "STRONG", "B", "EM", "I", "U", "DEL", "S", "BLOCKQUOTE", "HR",
                "TABLE", "THEAD", "TBODY", "TR", "TH", "TD",
                "PRE", "CODE", "A", "BR", "SPAN", "DIV", "BUTTON"
            ]);
            const allowedAttrs = new Set([
                "class", "id", "data-code", "href", "target", "rel", "title", "style"
            ]);

            const cleanNode = (node) => {
                const toRemove = [];
                for (const child of Array.from(node.childNodes)) {
                    if (child.nodeType === Node.ELEMENT_NODE) {
                        const tagName = child.tagName.toUpperCase();
                        if (!allowedTags.has(tagName)) {
                            toRemove.push(child);
                            continue;
                        }

                        // Remove dangerous attributes
                        const attrsToRemove = [];
                        for (let i = 0; i < child.attributes.length; i++) {
                            const attr = child.attributes[i];
                            const name = attr.name.toLowerCase();
                            const val = attr.value.toLowerCase().trim();

                            if (!allowedAttrs.has(name) || name.startsWith("on")) {
                                attrsToRemove.push(attr.name);
                            } else if ((name === "href" || name === "src") && (val.startsWith("javascript:") || val.startsWith("data:text/html"))) {
                                attrsToRemove.push(attr.name);
                            }
                        }
                        for (const attrName of attrsToRemove) {
                            child.removeAttribute(attrName);
                        }

                        if (tagName === "A") {
                            child.setAttribute("target", "_blank");
                            child.setAttribute("rel", "noopener noreferrer");
                        }

                        cleanNode(child);
                    }
                }
                for (const dead of toRemove) {
                    node.removeChild(dead);
                }
            };

            cleanNode(doc.body);
            return doc.body.innerHTML;
        } catch (e) {
            return rawHtml
                .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
                .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, "")
                .replace(/on\w+\s*=\s*["'][^"']*["']/gi, "")
                .replace(/javascript:/gi, "");
        }
    }

    _highlightCode(code, lang) {
        const escaped = this._escapeHtml(code);
        if (!lang) return escaped;

        const l = lang.toLowerCase().trim();
        if (l === "sql" || l === "tsql" || l === "pgsql") {
            const keywords = /\b(SELECT|FROM|WHERE|INSERT|INTO|UPDATE|DELETE|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|ON|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|AS|AND|OR|NOT|IN|EXISTS|BETWEEN|LIKE|ILIKE|IS|NULL|COUNT|SUM|AVG|MIN|MAX|DISTINCT|UNION|ALL|CREATE|TABLE|INDEX|VIEW|ALTER|DROP|SET|CASE|WHEN|THEN|ELSE|END|WITH|OVER|PARTITION\s+BY)\b/gi;
            return escaped
                .replace(keywords, '<span class="hl-keyword">$1</span>')
                .replace(/(--[^\n]*)/g, '<span class="hl-comment">$1</span>')
                .replace(/('(?:[^'\\]|\\.)*')/g, '<span class="hl-string">$1</span>')
                .replace(/\b(\d+)\b/g, '<span class="hl-number">$1</span>');
        } else if (l === "python" || l === "py") {
            const keywords = /\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|in|not|and|or|is|lambda|yield|raise|pass|break|continue|None|True|False|async|await)\b/g;
            return escaped
                .replace(keywords, '<span class="hl-keyword">$1</span>')
                .replace(/(#[^\n]*)/g, '<span class="hl-comment">$1</span>')
                .replace(/('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")/g, '<span class="hl-string">$1</span>')
                .replace(/\b(\d+)\b/g, '<span class="hl-number">$1</span>');
        } else if (l === "json" || l === "javascript" || l === "js") {
            const keywords = /\b(function|const|let|var|return|if|else|for|while|try|catch|finally|async|await|import|export|from|true|false|null|undefined)\b/g;
            return escaped
                .replace(keywords, '<span class="hl-keyword">$1</span>')
                .replace(/(\/\/[^\n]*)/g, '<span class="hl-comment">$1</span>')
                .replace(/('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")/g, '<span class="hl-string">$1</span>')
                .replace(/\b(\d+)\b/g, '<span class="hl-number">$1</span>');
        }
        return escaped;
    }

    formatMarkdown(rawText) {
        if (!rawText) return "";

        let text = rawText;

        // Auto-close unclosed code block during streaming
        const backtickMatches = text.match(/```/g);
        if (backtickMatches && backtickMatches.length % 2 !== 0) {
            text += "\n```";
        }

        // Clean LaTeX math arrows/symbols emitted by LLMs into clean unicode
        text = text
            .replace(/\$\s*\\rightarrow\s*\$/g, "→")
            .replace(/\\rightarrow/g, "→")
            .replace(/\$\s*\\Rightarrow\s*\$/g, "⇒")
            .replace(/\\Rightarrow/g, "⇒")
            .replace(/\$\s*\\leftarrow\s*\$/g, "←")
            .replace(/\\leftarrow/g, "←")
            .replace(/\$\s*\\leftrightarrow\s*\$/g, "↔")
            .replace(/\\leftrightarrow/g, "↔")
            .replace(/\$\s*\\le(?:q)?\s*\$/g, "≤")
            .replace(/\$\s*\\ge(?:q)?\s*\$/g, "≥")
            .replace(/\$\s*\\approx\s*\$/g, "≈")
            .replace(/\$\s*\\times\s*\$/g, "×")
            .replace(/\$\s*\\pm\s*\$/g, "±");

        // 1. Extract Code Blocks into placeholders
        const codeBlocks = [];
        text = text.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
            const index = codeBlocks.length;
            const cleanCode = code.trim();
            const highlighted = this._highlightCode(cleanCode, lang);
            const escapedCode = this._escapeHtml(cleanCode);
            const displayLang = (lang || "code").toUpperCase();

            codeBlocks.push(
                `<div class="md-code-block-wrap">` +
                    `<div class="md-code-header">` +
                        `<span class="md-code-lang">${displayLang}</span>` +
                        `<button class="md-copy-btn" onclick="copyCode(this)" data-code="${escapedCode}" title="Sao chép code">` +
                            `<i class="fa fa-copy"></i> <span>Sao chép</span>` +
                        `</button>` +
                    `</div>` +
                    `<pre class="md-code-block"><code class="language-${lang || 'text'}">${highlighted}</code></pre>` +
                `</div>`
            );
            return `\n@@CODEBLOCK_${index}@@\n`;
        });

        // 2. Process Inline markdown helper
        const applyInlineMarkdown = (val) => {
            if (!val) return "";
            return val
                .replace(/\$\s*\\rightarrow\s*\$/g, "→")
                .replace(/\\rightarrow/g, "→")
                .replace(/\$\s*\\Rightarrow\s*\$/g, "⇒")
                .replace(/\\Rightarrow/g, "⇒")
                .replace(/\$\s*\\leftarrow\s*\$/g, "←")
                .replace(/\\leftarrow/g, "←")
                .replace(/`([^`\n]+)`/g, "<code class='md-inline-code'>$1</code>")
                .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
                .replace(/__([^_]+)__/g, "<strong>$1</strong>")
                .replace(/\*([^*]+)\*/g, "<em>$1</em>")
                .replace(/_([^_]+)_/g, "<em>$1</em>")
                .replace(/~~([^~]+)~~/g, "<del>$1</del>")
                .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        };

        // Split table row helper
        const parseTableRow = (line) => {
            const clean = line.trim().replace(/^\|/, "").replace(/\|$/, "");
            return clean.split("|").map(c => applyInlineMarkdown(c.trim()));
        };

        // 3. Process Blocks line by line
        const lines = text.split("\n");
        const outBlocks = [];
        let i = 0;

        while (i < lines.length) {
            const line = lines[i];
            const trimmed = line.trim();

            if (!trimmed) {
                i++;
                continue;
            }

            // Check Code block placeholder
            const codeMatch = trimmed.match(/^@@CODEBLOCK_(\d+)@@$/);
            if (codeMatch) {
                outBlocks.push(codeBlocks[Number(codeMatch[1])] || "");
                i++;
                continue;
            }

            // Check Horizontal rule
            if (/^(---|\*\*\*|___)$/.test(trimmed)) {
                outBlocks.push("<hr/>");
                i++;
                continue;
            }

            // Check Heading
            const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
            if (headingMatch) {
                const level = headingMatch[1].length;
                outBlocks.push(`<h${level}>${applyInlineMarkdown(headingMatch[2])}</h${level}>`);
                i++;
                continue;
            }

            // Check Blockquote
            if (trimmed.startsWith(">")) {
                const quoteLines = [];
                while (i < lines.length && lines[i].trim().startsWith(">")) {
                    quoteLines.push(lines[i].trim().replace(/^>\s?/, ""));
                    i++;
                }
                const quoteContent = quoteLines.map(l => applyInlineMarkdown(l)).join("<br/>");
                outBlocks.push(`<blockquote>${quoteContent}</blockquote>`);
                continue;
            }

            // Check Table
            const nextLine = (lines[i + 1] || "").trim();
            if (trimmed.startsWith("|") && nextLine.startsWith("|") && /^[|\s:-]+$/.test(nextLine) && nextLine.includes("-")) {
                const headerCells = parseTableRow(trimmed);
                const alignDefs = parseTableRow(nextLine);
                const alignments = alignDefs.map(def => {
                    const d = def.trim();
                    if (d.startsWith(":") && d.endsWith(":")) return "center";
                    if (d.endsWith(":")) return "right";
                    return "left";
                });

                i += 2;
                const bodyRows = [];
                while (i < lines.length && lines[i].trim().startsWith("|")) {
                    const rowCells = parseTableRow(lines[i]);
                    bodyRows.push(rowCells);
                    i++;
                }

                const thHtml = headerCells.map((cell, idx) => {
                    const align = alignments[idx] || "left";
                    return `<th style="text-align: ${align}">${cell}</th>`;
                }).join("");

                const trHtml = bodyRows.map(row => {
                    const tdHtml = row.map((cell, idx) => {
                        const align = alignments[idx] || "left";
                        return `<td style="text-align: ${align}">${cell}</td>`;
                    }).join("");
                    return `<tr>${tdHtml}</tr>`;
                }).join("");

                outBlocks.push(
                    `<div class="md-table-wrap">` +
                        `<table class="md-table">` +
                            `<thead><tr>${thHtml}</tr></thead>` +
                            `<tbody>${trHtml}</tbody>` +
                        `</table>` +
                    `</div>`
                );
                continue;
            }

            // Check Unordered List
            if (/^[-*+]\s+/.test(trimmed)) {
                const listItems = [];
                while (i < lines.length && /^[-*+]\s+/.test(lines[i].trim())) {
                    const itemContent = lines[i].trim().replace(/^[-*+]\s+/, "");
                    listItems.push(`<li>${applyInlineMarkdown(itemContent)}</li>`);
                    i++;
                }
                outBlocks.push(`<ul>${listItems.join("")}</ul>`);
                continue;
            }

            // Check Ordered List
            if (/^\d+\.\s+/.test(trimmed)) {
                const listItems = [];
                while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
                    const itemContent = lines[i].trim().replace(/^\d+\.\s+/, "");
                    listItems.push(`<li>${applyInlineMarkdown(itemContent)}</li>`);
                    i++;
                }
                outBlocks.push(`<ol>${listItems.join("")}</ol>`);
                continue;
            }

            // Regular Paragraph / fallback line - MUST ALWAYS ADVANCE i
            const startI = i;
            const paraLines = [];
            while (i < lines.length) {
                const curTrimmed = lines[i].trim();
                if (!curTrimmed) break;
                if (curTrimmed.startsWith("#") || curTrimmed.startsWith(">") || /^[-*+]\s+/.test(curTrimmed) || /^\d+\.\s+/.test(curTrimmed) || curTrimmed.match(/^@@CODEBLOCK_\d+@@$/) || /^(---|\*\*\*|___)$/.test(curTrimmed)) {
                    break;
                }
                // If it looks like start of a complete table, break so table parser handles it
                const nextL = (lines[i + 1] || "").trim();
                if (curTrimmed.startsWith("|") && nextL.startsWith("|") && /^[|\s:-]+$/.test(nextL) && nextL.includes("-")) {
                    break;
                }
                paraLines.push(applyInlineMarkdown(curTrimmed));
                i++;
            }
            if (paraLines.length > 0) {
                outBlocks.push(`<p>${paraLines.join("<br/>")}</p>`);
            } else if (i === startI) {
                outBlocks.push(`<p>${applyInlineMarkdown(trimmed)}</p>`);
                i++;
            }
        }

        const rawHtml = outBlocks.join("");
        const sanitized = this._sanitizeHtml(rawHtml);
        return markup(sanitized);
    }
}

ChatbotDashboard.template = "topic_chatbot.ChatbotDashboard";
registry.category("actions").add("topic_chatbot.dashboard", ChatbotDashboard);

window.copyCode = function (btn) {
    if (!btn) return;
    const code = btn.getAttribute("data-code") || "";
    if (!code) return;

    // Decode HTML entities
    const textarea = document.createElement("textarea");
    textarea.innerHTML = code;
    const decodedCode = textarea.value;

    navigator.clipboard.writeText(decodedCode).then(() => {
        const icon = btn.querySelector("i");
        const span = btn.querySelector("span");
        btn.classList.add("copied");
        if (icon) icon.className = "fa fa-check text-success";
        if (span) span.textContent = "Đã sao chép!";
        setTimeout(() => {
            btn.classList.remove("copied");
            if (icon) icon.className = "fa fa-copy";
            if (span) span.textContent = "Sao chép";
        }, 2000);
    }).catch(() => {
        // Fallback for older browsers
        textarea.value = decodedCode;
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand("copy");
            const icon = btn.querySelector("i");
            const span = btn.querySelector("span");
            btn.classList.add("copied");
            if (icon) icon.className = "fa fa-check text-success";
            if (span) span.textContent = "Đã sao chép!";
            setTimeout(() => {
                btn.classList.remove("copied");
                if (icon) icon.className = "fa fa-copy";
                if (span) span.textContent = "Sao chép";
            }, 2000);
        } catch (_err) {
            // copy failed
        }
        document.body.removeChild(textarea);
    });
};

export { ChatbotDashboard };

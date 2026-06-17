/** @odoo-module */
import { patch } from "@web/core/utils/patch";

import { _t } from "@web/core/l10n/translation";
import { registerMessageAction, MessageAction } from "@mail/core/common/message_actions";
import { unwrapContents } from "@html_editor/utils/dom";
import { setElementContent } from "@web/core/utils/html";

registerMessageAction("insertToComposer", {
    condition: ({ message, store, thread }) =>
        !!thread?.aiSpecialActions?.insert &&
        store.aiInsertButtonTarget && // after a reload both parts of the below conditions are undefined and but we don't want to button to appear
        (store.aiInsertButtonTarget === thread.aiChatSource || store.env.isSmall) &&
        !message.isSelfAuthored,
    name: _t("Use this"),
    onSelected: ({ message, store, thread }) => {
        const fragment = document.createDocumentFragment();
        const content_root = document.createElement("span");
        content_root.setAttribute("InsertorId", "AIInsertion");
        setElementContent(content_root, message.body);
        // check if the content is enclosed in a <p> element, if so, unwrap it
        const paragraphElements = content_root.querySelectorAll("p");
        if (paragraphElements.length === 1) {
            unwrapContents(paragraphElements[0]);
        }
        fragment.appendChild(content_root);
        thread.aiSpecialActions.insert(fragment);
        if (store.env.isSmall) {
            thread.closeChatWindow();
        }
    },
    sequence: 10,
});
registerMessageAction("send-message-direct", {
    condition: ({ message, thread }) =>
        !!thread?.aiSpecialActions?.sendMessage && !message.isSelfAuthored, // don't show the buttons for the user's messages,
    name: _t("Send as Message"),
    onSelected: ({ message, thread }) => thread.aiSpecialActions.sendMessage(message.body),
    sequence: 20,
});
registerMessageAction("log-note-direct", {
    condition: ({ message, thread }) =>
        !!thread?.aiSpecialActions?.logNote && !message.isSelfAuthored, // don't show the buttons for the user's messages
    name: _t("Log as Note"),
    onSelected: ({ message, thread }) => thread.aiSpecialActions.logNote(message.body),
    sequence: 25,
});

patch(MessageAction.prototype, {
    _condition({ thread }) {
        const requiredActions = [
            "insertToComposer",
            "copy-message",
            "send-message-direct",
            "log-note-direct",
        ];
        if (thread?.type === "ai_chat" && !requiredActions.includes(this.id)) {
            return false;
        }
        if (this.id === "copy-message") {
            return super._condition(...arguments) || thread?.type === "ai_chat";
        }
        return super._condition(...arguments);
    },
    _sequence({ thread }) {
        if (this.id === "copy-message" && thread?.type === "ai_chat") {
            return 50;
        }
        return super._sequence(...arguments);
    },
});

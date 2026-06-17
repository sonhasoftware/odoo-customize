/** @odoo-module */
import { registry } from "@web/core/registry";

async function initChat(env, action) {
    const store = env.services["mail.store"];

    const thread = store.Thread.insert({
        model: "discuss.channel",
        id: Number(action.params.channelId),
    });
    if (!thread.is_pinned) {
        await env.services["mail.thread"].fetchChannel(thread.id);
    }
    if (!thread) {
        throw new Error("Thread not found");
    }
    env.services["mail.thread"].open(thread);
    if (action.params.user_prompt && thread.status !== "loading") {
        await env.services["mail.thread"].post(thread, action.params.user_prompt);
    }
}

registry.category("actions").add("agent_chat_action", initChat);

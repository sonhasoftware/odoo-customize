import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService, useBus } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, useState, useEffect, useRef } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { convertBrToLineBreak } from "@mail/utils/common/format";


export class AILivechatComponent extends Component {
    static template = "ai_website_livechat.AILivechatComponent";
    static props = {
        agentId: { type: Number },
        livechatChannelId: { type: Number, optional: true },
        chatStyle: { type: String, optional: true },
        promptPlaceholder: {type: String, optional: true },
        hasFallbackButton: { type: Boolean },
        fallbackButtonText: { type: String },
        fallbackButtonURL: { type: String },
    };

    setup() {
        this.notificationService = useService("notification");
        this.store = useService("mail.store");
        this.livechatService = useService("im_livechat.livechat");

        this.state = useState({
            prompt: "",
            messages: [],
            assistantThinking: false,
            otherElementsHidden: false,
        });
        this.promptInputRef = useRef("promptInput");
        this.messagesDiv = useRef("messagesDiv");
        this.channel = undefined;

        onWillStart(this.isLivechatAvailable.bind(this));
        onMounted(() => {
            const aiLivechatSnippet = document.querySelector(this.SNIPPET_SELECTOR);
            this.snippetParent = aiLivechatSnippet.parentNode;
            this.snippetNextSibling = aiLivechatSnippet.nextElementSibling;
        });
        useBus(this.env.bus, "discuss.channel/new_message", this.onMessagePosted.bind(this));
        useBus(this.env.bus, "CHATWINDOW_CLOSED", async (payload) => { await this.onChatWindowClosed(payload) });

        useEffect(
            () => {
                // Resize  textarea to fit its content.
                this.promptInputRef.el.style.height = 0;
                this.promptInputRef.el.style.height = this.promptInputRef.el.scrollHeight + "px";
            },
            () => [this.state.prompt]
        );
        useEffect(
            () => {
                if (this.props.chatStyle === 'fullscreen'){
                    this.promptInputRef.el.focus();
                }
            },
            () => [this.state.assistantThinking]
        );
        useEffect(
            () => {
                // Scroll to the latest message whenever new message
                // is inserted.
                const messagesDivEl = this.messagesDiv.el;
                const selectorToHide = ['footer', '.o-livechat-root'];
                if(messagesDivEl){
                    const lastMessageEl = messagesDivEl.lastElementChild;
                    lastMessageEl.scrollIntoView({ block: "start", inline: "nearest", behavior: "smooth" });
                    if(!this.state.otherElementsHidden){
                        for (const s of selectorToHide) {
                            document.querySelector(s)?.classList.add('d-none');
                        }
                        this.hideOtherSnippets();
                        this.centerAndApplyWidthHeight();
                        this.state.otherElementsHidden = true;
                    }
                }
                else if(this.state.otherElementsHidden) {
                    for (const s of selectorToHide) {
                        document.querySelector(s)?.classList.remove('d-none')
                    }
                    this.showOtherSnippets();
                    this.restorePositionAndWidthHeight();
                    this.state.otherElementsHidden = false;
                }
            },
            () => [this.state.messages.length]
        );
    }

    async isLivechatAvailable(){
        this.livechatAvailable = await rpc(
            "/ai_website_livechat/is_livechat_operator_available",
            {'livechat_channel_id': this.props.livechatChannelId}
        );
    }

    onMessagePosted({ detail: { message } }){
        if(!message.thread?.eq(this.channel) || message.isSelfAuthored){
            return;
        }
        this.processResponse(message);
    }

    processResponse(message){
        if(this.props.chatStyle !== "fullscreen" || !this.channel.ai_agent_id){
            return;
        }
        this.state.messages.push({
            author: "assistant",
            text: message.body,
            id: message.id,
        });
        this.state.assistantThinking = false;
    }

    async onChatWindowClosed({ detail }){
        if(detail.channel.eq(this.channel)){
            // leaveLivechatSession = false => User has already left the livechat session.
            await this.closeConversation(false);
        }
    }

    async closeConversation(leaveLivechatSession=true) {
        if(leaveLivechatSession && this.channel?.channel_type === 'livechat'){
            await this.livechatService.leave(this.channel);
        }
        this.resetState();
        this.channel = undefined;
    }

    resetState(){
        this.state.messages = [];
        this.state.prompt = "";
        this.state.assistantThinking = false;
    }

    showOtherSnippets() {
        const aiLivechatSnippet = document.querySelector(this.SNIPPET_SELECTOR);
        if (aiLivechatSnippet) {
            this.snippetParent.insertBefore(aiLivechatSnippet, this.snippetNextSibling);
        }
        const snippetsToShow = document.querySelectorAll(this.ALL_SNIPPETS_SELECTOR);
        for (const snippet of snippetsToShow) {
            snippet.classList.remove("d-none");
        }
    }

    restorePositionAndWidthHeight() {
        const aiLivechatContainer = document.querySelector(this.SNIPPET_SELECTOR).querySelector('[data-name="ai_livechat_container"]');
        if(aiLivechatContainer){
            aiLivechatContainer.classList.remove('o_ai_livechat_container');
        }
    }

    hideOtherSnippets() {
        // Hiding all snippets other than the aiLivechatSnippet may result in hiding the aiLivechatSnippet if it is embedded into another snippet.
        // Instead, all the snippets will be hidden and the aiLivechatSnippet will be added to the '#wrap' div which wraps all the snippets.
        const snippetsToHide = document.querySelectorAll(this.ALL_SNIPPETS_SELECTOR);
        for (const snippet of snippetsToHide) {
            snippet.classList.add("d-none");
        }
        const aiLivechatSnippet = document.querySelector(this.SNIPPET_SELECTOR);
        if(aiLivechatSnippet){
            aiLivechatSnippet.classList.remove('d-none');
            document.querySelector(this.SNIPPETS_WRAPPER_DIV_SELECTOR).appendChild(aiLivechatSnippet);
        }
    }

    centerAndApplyWidthHeight() {
        const aiLivechatContainer = document.querySelector(this.SNIPPET_SELECTOR).querySelector('[data-name="ai_livechat_container"]');
        if(aiLivechatContainer){
            aiLivechatContainer.classList.add('o_ai_livechat_container');
        }
    }

    onTextareaKeydown(ev) {
        if(ev.key === "Enter" && !ev.shiftKey){
            ev.stopImmediatePropagation();
            if(this.state.prompt.trim().length){
                this.submitPrompt(ev);
            }
        }
    }

    async submitPrompt(ev) {
        ev?.preventDefault();
        if(!this.props.agentId){
            this.notificationService.add(_t("Oops, there is no Agent linked to this block!"));
            return;
        }
        if(this.channel && !this.channel.ai_agent_id){
            return;
        }

        await this.createChannel(this.props.chatStyle === "popup");
        if(!this.isChannelActive){
            return;
        }

        this.channel?.post(this.state.prompt);
        if (this.props.chatStyle === 'fullscreen'){
            this.state.messages.push({ author: "user", text: DOMPurify.sanitize(this.state.prompt) });
            this.state.assistantThinking = true;
        }
        this.state.prompt = "";
    }

    async createChannel(openChatWindow){
        if(this.isChannelActive){
            return;
        }
        let archivedAgent = false;
        if(this.livechatAvailable){
            let livechatChannelOptions = { persist: true, channel_id: this.props.livechatChannelId, ai_agent_id: this.props.agentId };
            this.channel = await this.livechatService._createThread({ options: livechatChannelOptions })
            // If an ai_agent is set on the website snippet and then that ai_agent became archived and wasn't removed
            // from the snippet, the created channel won't have ai_agent_id.
            if (!this.channel.ai_agent_id) {
                this.channel = undefined;
                archivedAgent = true;
            }
        }
        else{
            let channel_params = { ai_agent_id: this.props.agentId }
            const result = await rpc("/ai_website_livechat/create_chat_channel", channel_params);
            if (result){
                this.store.insert(result["store_data"]);
                this.channel = this.store.Thread.get({ id: result["channel_id"], model: "discuss.channel" });
            }
            else {
                archivedAgent = true;
            }
        }
        if (archivedAgent){
            this.notificationService.add(_t("Oops, the Agent linked to this block is archived!"));
            return;
        }
        if (openChatWindow){
            await this.channel.openChatWindow({ focus:true });
        }
    }

    async askHuman(ev) {
        await this.createChannel(false);
        if (!this.isChannelActive || !this.channel.ai_agent_id){
            return;
        }
        const result = await rpc("/ai_livechat/forward_operator", {
            channel_id: this.channel.id,
        });
        if(result['store_data']){
            this.store.insert(result['store_data']);
        }
        if(result['notification']){
            this.store.env.services.notification.add(result['notification'], { type: result['notification_type']});
        }
        if(result['success'] === true){
            this.channel.readyToSwapDeferred.resolve();
            await this.channel.openChatWindow({ focus:true });
            // Reset the state to show other snippets. The livechat with a human will always open in a chat window popup not fullscreen.
            this.resetState();
        }
    }

    async copyAnswer(message_index) {
        const message_content_markdown = convertBrToLineBreak(this.state.messages[message_index].text);
        const message_content_html = this.state.messages[message_index].text;
        await browser.navigator.clipboard?.write([
            new ClipboardItem({
                'text/html': new Blob([message_content_html], {type: 'text/html'}),
                'text/plain': new Blob([message_content_markdown], {type: 'text/plain'}),
            }),
        ]);
    }

    get fallbackButtonActive() {
        return !this.livechatAvailable && this.props.hasFallbackButton && Boolean(this.props.fallbackButtonURL);
    }

    get isChannelActive(){
        return Boolean(
            this.channel && (
                this.channel.channel_type === 'ai_chat' ||
                this.channel.channel_type == 'livechat' && !this.channel.livechat_end_dt
            )
        )
    }

    get SNIPPET_SELECTOR(){
        return '.s_ai_livechat';
    }

    get ALL_SNIPPETS_SELECTOR(){
        return `${this.SNIPPETS_WRAPPER_DIV_SELECTOR} > *`;
    }

    get SNIPPETS_WRAPPER_DIV_SELECTOR(){
        return '#wrap';
    }
}
registry.category("public_components").add("ai_website_livechat.ai_livechat_component", AILivechatComponent);

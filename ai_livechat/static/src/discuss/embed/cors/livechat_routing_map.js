import { livechatRoutingMap } from "@im_livechat/embed/cors/livechat_routing_map";

livechatRoutingMap
    .add("/ai/generate_response", "/ai/cors/generate_response")
    .add("/ai/post_error_message", "/ai/cors/post_error_message")
    .add("/ai/close_ai_chat", "/ai/cors/close_ai_chat")
    .add("/ai_livechat/forward_operator", "/ai_livechat/cors/forward_operator")

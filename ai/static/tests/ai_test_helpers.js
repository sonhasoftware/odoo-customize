import { mailModels } from "@mail/../tests/mail_test_helpers";
import { AIAgent } from "./mock_server/mock_models/ai_agent";
import { DiscussChannel } from "./mock_server/mock_models/discuss_channel";
import { defineModels } from "@web/../tests/web_test_helpers";
import { AIComposer } from "./mock_server/mock_models/ai_composer";

export function defineAIModels() {
    return defineModels({ ...mailModels, AIAgent, AIComposer, DiscussChannel });
}

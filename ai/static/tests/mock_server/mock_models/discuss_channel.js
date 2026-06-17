import { mailModels } from "@mail/../tests/mail_test_helpers";
import { Command } from "@web/../tests/web_test_helpers";

export class DiscussChannel extends mailModels.DiscussChannel {
    /**
     * @param {import("@mail/../tests/mock_server/mock_models/res_partner").ResPartner} partner
     */
    _get_or_create_ai_chat(partner) {
        const channels = this.env["discuss.channel"].search([
            ["is_member", "=", true],
            ["channel_type", "=", "ai_chat"],
            ["channel_member_ids", "any", ["partner_id", "=", partner.id]],
        ]);

        if (!channels[0]) {
            return this.env["discuss.channel"].create({
                name: partner.name,
                channel_type: "ai_chat",
                channel_member_ids: [
                    Command.create({
                        partner_id: this.env.user.partner_id.id,
                    }),
                    Command.create({
                        partner_id: partner.id,
                    }),
                ],
            });
        }

        return channels[0];
    }
}

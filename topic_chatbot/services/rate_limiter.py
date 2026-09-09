# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

RATE_LIMIT_MAX_MESSAGES = 5
RATE_LIMIT_WINDOW_SECONDS = 60


def check_rate_limit(env, user_id, max_messages=RATE_LIMIT_MAX_MESSAGES, window_seconds=RATE_LIMIT_WINDOW_SECONDS):
    """Check if user has exceeded the rate limit.
    Returns True if rate limit exceeded, False otherwise.
    Args:
        env: Odoo environment (request.env or self.env in tests)
        user_id: ID of the user to check
        max_messages: Maximum messages allowed within window
        window_seconds: Sliding window duration in seconds
    """
    cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
    recent_count = env['topic_chatbot.message'].sudo().search_count([
        ('conversation_id.user_id', '=', user_id),
        ('role', '=', 'user'),
        ('create_date', '>=', cutoff),
    ])
    return recent_count >= max_messages

# Part of Odoo. See LICENSE file for full copyright and licensing details.
from typing import NamedTuple

from odoo.exceptions import UserError


class Provider(NamedTuple):
    name: str
    display_name: str
    embedding_model: str
    llms: list[tuple[str, str]]


PROVIDERS = [
    Provider(
        "openai",
        "OpenAI",
        "text-embedding-3-small",
        [
            ("gpt-3.5-turbo", "GPT-3.5 Turbo"),
            ("gpt-4", "GPT-4"),
            ("gpt-4o", "GPT-4o"),
            ("gpt-4.1", "GPT-4.1"),
            ("gpt-4.1-mini", "GPT-4.1 Mini"),
            ("gpt-5", "GPT-5"),
            ("gpt-5-mini", "GPT-5 Mini")
        ],
    ),
    Provider(
        "google",
        "Google",
        "gemini-embedding-001",
        [
            ("gemini-3.5-flash", "Gemini 3.5 Flash"),
            ("gemini-2.5-pro", "Gemini 2.5 Pro"),
            ("gemini-2.5-flash", "Gemini 2.5 Flash"),
            ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite"),
            ("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite"),
            ("gemini-2.0-flash", "Gemini 2.0 Flash"),
            ("gemini-1.5-pro", "Gemini 1.5 Pro"),
            ("gemini-1.5-flash", "Gemini 1.5 Flash"),
        ],
    ),
]


EMBEDDING_MODELS_SELECTION = [
    (provider.embedding_model, provider.display_name) for provider in PROVIDERS
]


def get_provider_for_embedding_model(env, embedding_model):
    for p in PROVIDERS:
        if p.embedding_model == embedding_model:
            return p.name
    raise UserError(env._("No provider found for the embedding model"))


def get_provider(env, llm_model):
    for p in PROVIDERS:
        if llm_model in [m[0] for m in p.llms]:
            return p.name
    raise UserError(env._("No provider found for the selected model"))

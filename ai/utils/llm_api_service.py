# Part of Odoo. See LICENSE file for full copyright and licensing details.
import copy
import json
import os
import requests
import typing
from logging import getLogger
import time
from typing import Callable, Any

from odoo import _
from odoo.api import Environment
from odoo.exceptions import UserError

from .ai_logging import ai_response_logging, api_call_logging, get_ai_logging_session

_logger = getLogger(__name__)


class Embedding(typing.TypedDict):
    index: int
    embedding: list[float]
    object: str


class EmbeddingResponse(typing.TypedDict):
    object: str
    data: list[Embedding]
    model: str
    usage: dict


class RealtimeSessionAudioInputFormatParameter(typing.TypedDict, total=False):
    type: str | None
    rate: int | None


class RealtimeSessionAudioInputTranscriptionParameter(typing.TypedDict, total=False):
    language: str | None
    model: str | None
    prompt: str | None


class RealtimeSessionAudioInputTurnDetectionParameter(typing.TypedDict, total=False):
    create_response: bool | None
    eagerness: str | None
    idle_timeout_ms: int | None
    interrupt_response: bool | None
    prefix_padding_ms: int | None
    silence_duration_ms: int | None
    threshold: float | None
    type: str | None


class RealtimeSessionAudioInputNoiseReductionParameter(typing.TypedDict, total=False):
    type: str | None


class RealtimeSessionAudioInputParameter(typing.TypedDict, total=False):
    format: RealtimeSessionAudioInputFormatParameter | None
    noise_reduction: RealtimeSessionAudioInputNoiseReductionParameter | None
    transcription: RealtimeSessionAudioInputTranscriptionParameter | None
    turn_detection: RealtimeSessionAudioInputTurnDetectionParameter | None


class RealtimeSessionAudioParameter(typing.TypedDict, total=False):
    input: RealtimeSessionAudioInputParameter | None


class RealtimeSessionParameter(typing.TypedDict, total=False):
    type: str
    audio: RealtimeSessionAudioParameter | None
    include: list[str] | None


class RealtimeExpiresAfterParameter(typing.TypedDict, total=False):
    anchor: str | None
    seconds: int | None


class RealtimeParameters(typing.TypedDict, total=False):
    expires_after: RealtimeExpiresAfterParameter | None
    session: RealtimeSessionParameter | None


class LLMApiService:
    def __init__(self, env: Environment, provider: str = 'openai') -> None:
        self.provider = provider
        base_url = None
        if self.provider == 'openai':
            base_url = "https://api.openai.com/v1"
        elif self.provider == 'google':
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        else:
            raise NotImplementedError(f"Unsupported provider: {self.provider}")

        self.base_url = base_url
        self.env = env

    def get_embedding(
        self,
        input: str | list[str] | list[int] | list[list[int]],
        dimensions: int,
        model: str = 'text-embedding-3-small',
        encoding_format: str | None = None,
        user: str | None = None,
    ) -> EmbeddingResponse:
        body = {
            'input': input,
            'model': model
        }
        self._add_if_set(body, 'encoding_format', encoding_format)
        self._add_if_set(body, 'dimensions', dimensions)
        self._add_if_set(body, 'user', user)

        return self._request(
            'post',
            '/embeddings',
            self._get_base_headers(),
            body,
        )

    def get_transcription(
            self,
            data: bytes,
            mimetype: str = "audio/ogg",
            model: str = "whisper-1",
            language: str | None = None,
            prompt: str | None = None,
            response_format: str = "verbose_json",
            temperature: float | None = None
    ):
        """ Submit audio data for transcription and return the transcribed text
            Logs real-time factor:  `o_rtf = (transmission + inference_time) / audio_duration`
            :param data: The audio file as raw bytes (not a filename or path!).
            :param mimetype: MIME type of the audio data, defaults to "audio/ogg".
            :param model: model to use for the transcription, defaults to 'whisper-1'
            :param language: language of the audio
            :param prompt: Optional text used to guide the model's style or continue a previous audio segment. Only supports english.
            :param response_format: format of the output of the model. Types: 'json', 'text', 'srt', 'verbose_json', or 'vtt'
            :param temperature: randomness level of the model. Ranges from 0 to 1.
            :return: str | None: The transcribed text if successful, or None if the transcription failed.

            Example:
            ```python
            from odoo.addons.ai.utils.llm_api_service import LLMApiService
            service = LLMApiService(self.env)
            with open("audio.ogg", "rb") as f:
                audio_bytes = f.read()
            text = service.get_transcription(audio_bytes, mimetype="audio/ogg")
            ```
        """
        if response_format not in ['json', 'verbose_json']:  # limitation of using response.json() in _request function
            raise NotImplementedError(f"Response format '{response_format}' is not supported. Request must return json!")

        headers = {
            'Authorization': f'Bearer {self._get_api_token()}',
        }
        body = {
            "model": model,
            "response_format": response_format
        }
        self._add_if_set(body, "prompt", prompt)
        self._add_if_set(body, "language", language)
        self._add_if_set(body, "temperature", temperature)

        start = time.perf_counter()
        response = self._request(
            method="post",
            endpoint="/audio/transcriptions",
            headers=headers,
            body={},
            data=body,
            files={"file": ("audio", data, mimetype)},
            timeout=550
        )
        elapsed = time.perf_counter() - start

        if not response or 'text' not in response:
            _logger.warning("No transcription received.")
            return None

        # Observed RTF (request time + transcription time)
        o_rft_text = ""
        audio_duration = response.get('duration', False)
        if audio_duration and audio_duration > 0:
            o_rtf = elapsed / audio_duration
            o_rft_text = f"(Observed RTF: {o_rtf:.2f} for {audio_duration:.1f}s audio)"
        _logger.info("Transcription job done in %.1fs %s", elapsed, o_rft_text)
        return response.get('text')

    def get_transcription_session(self, config: RealtimeParameters | None):
        headers = self._get_base_headers()

        body = dict(**config) if config is not None else {}
        return self._request("post", "/realtime/client_secrets", headers, body)

    def _add_if_set(self, d: dict, key: str, value):
        if value is not None:
            d[key] = value

    def _get_base_headers(self) -> dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._get_api_token()}',
        }

    def _get_api_token(self):
        provider_config = {
            "openai": {
                "config_key": "ai.openai_key",
                "env_var": "ODOO_AI_CHATGPT_TOKEN",
            },
            "google": {
                "config_key": "ai.google_key",
                "env_var": "ODOO_AI_GEMINI_TOKEN",
            },
        }
        config = provider_config.get(self.provider)
        if config is None:
            raise UserError(_("Unsupported provider '%s'", self.provider))

        if api_key := self.env["ir.config_parameter"].sudo().get_param(config["config_key"]) or os.getenv(config["env_var"]):
            return api_key

        raise UserError(_("No API key set for provider '%s'", self.provider))

    def _request(
        self, method: str, endpoint: str, headers: dict[str, str], body: dict,
        data: dict | None = None, files: dict | None = None, params: dict | None = None,
        base_url: str | None = None, timeout: int = 30
    ) -> dict:
        route = f"{base_url or self.base_url}/{endpoint.strip('/')}"
        try:
            response = requests.request(
                method,
                route,
                params=params,
                headers=headers,
                json=body,
                data=data,
                timeout=timeout,
                files=files
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error = repr(e)
            if e.response is not None:
                try:
                    response = e.response.json()
                    if isinstance(response, list) and response:
                        # Gemini return error in a list
                        response = response[0]
                    if isinstance(response, dict) and (json_error := response.get('error', {}).get('message')):
                        error = json_error
                    else:
                        error = json.dumps(response, indent=2)
                except ValueError:  # catch JSON decode errors
                    error = e.response.text
                if not error:
                    error = repr(e)

            _logger.warning("LLM API request failed: %s", error)
            raise UserError(error)

    def _request_llm_openai(
        self, llm_model, system_prompts, user_prompts, tools=None,
        files=None, schema=None, temperature=0.2, inputs=(), web_grounding=False
    ):
        """Make a single request to the LLM.

        > https://platform.openai.com/docs/guides/responses-vs-chat-completions#why-the-responses-api
        > https://platform.openai.com/docs/guides/pdf-files?api-mode=responses
        > https://platform.openai.com/docs/guides/function-calling?api-mode=responses

        Return:
        - a list of responses
        - a list of tuple of the tools to call
            [(tool_name, call_id, {argument_1: True, argument_2: 3})]
        - a list of inputs to include in the next call in addition to the tool response
        """
        user_content = [{"type": "input_text", "text": prompt} for prompt in user_prompts]

        if files:
            def _build_file(idx, file):
                if file["mimetype"] == "text/plain":
                    return {"type": "input_text", "text": file["value"]}

                file_uri = f"data:{file['mimetype']};base64,{file['value']}"
                if file['mimetype'] == 'application/pdf':
                    return {
                        "type": "input_file",
                        "filename": f"file_{idx}.pdf",
                        "file_data": file_uri,
                    }

                assert file["mimetype"].startswith("image/")
                return {"type": "input_image", "image_url": file_uri, "detail": "low"}

            user_content.extend(
                _build_file(idx, file)
                for idx, file in enumerate(files, start=1)
            )

        body = {
            "model": llm_model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {"type": "input_text", "text": prompt}
                        for prompt in system_prompts
                    ],
                },
                {"role": "user", "content": user_content},
                *inputs,
            ],
            "store": False,
        }
        if llm_model not in ('gpt-5', 'gpt-5-mini'):
            # temperature in not supported with openai reasoning models
            body["temperature"] = temperature

        if schema:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "json_schema",
                    "schema": schema,
                    "strict": True,
                },
            }

        if tools:
            body["tools"] = self._to_open_ai_tool_schema([{
                "description": tool_description,
                "parameters": tool_parameter_schema,
                "type": "function",
                "name": tool_name,
                "strict": True,
            } for tool_name, (tool_description, __, __, tool_parameter_schema) in tools.items()])
            body["parallel_tool_calls"] = True

        if web_grounding:
            search_tool = {
                'type': 'web_search_preview',
            }
            if country_code := self.env.company.country_id.code:
                search_tool['user_location'] = {
                    'type': 'approximate',
                    'country': country_code,
                }
                if city := self.env.company.city:
                    search_tool['user_location']['city'] = city
            body.setdefault("tools", []).append(search_tool)

        with api_call_logging(body["input"], tools) as record_response:
            response, to_call, next_inputs = self._request_llm_openai_helper(body, tools, inputs)
            if record_response:
                record_response(to_call, response)
            return response, to_call, next_inputs

    def _request_llm_openai_helper(self, body, tools=None, inputs=()):
        llm_response = self._request(
            "post",
            "/responses",
            self._get_base_headers(),
            body,
        )

        to_call = []
        response = []
        next_inputs = list(inputs or ())

        for line in llm_response.get("output") or ():
            if line.get('type') == 'function_call':
                tool_name = line.get("name", "")
                if tool_name not in tools:
                    _logger.error("AI: Try to call a forbidden action %s", line)
                    continue

                try:
                    arguments = json.loads(line.get("arguments") or "")
                except json.decoder.JSONDecodeError:
                    _logger.error("AI: Malformed arguments: %s", line)
                    continue

                to_call.append((tool_name, line.get('call_id'), arguments))
                next_inputs.append(line)

            elif text := line.get('text'):
                response.append(text)
            elif line.get('type') == 'message':
                response.extend(t for c in line.get('content', ()) if (t := c.get('text')))
        return response, to_call, next_inputs

    def _request_llm_google(
        self, llm_model, system_prompts, user_prompts, tools=None,
        files=None, schema=None, temperature=0.2, inputs=(), web_grounding=False,
    ):
        """Make a single request to the LLM.

        Gemini's OpenAI conversion layer does not support `type: file`, so we use the real API
        > https://discuss.ai.google.dev/t/combining-openai-compatible-gemini-completions-with-file-uploads/75281/2

        > https://ai.google.dev/gemini-api/docs/text-generation
        > https://ai.google.dev/gemini-api/docs/function-calling
        > https://ai.google.dev/gemini-api/docs/document-processing
        """
        if (tools or web_grounding) and schema:
            # https://discuss.ai.google.dev/t/why-is-using-a-response-schema-not-supported-when-using-grounded-search/92327
            raise NotImplementedError("Gemini does not support structured output with tools")
        if web_grounding and tools:
            # https://ai.google.dev/gemini-api/docs/function-calling?example=meeting#native-tools
            # see note, live api feature only for the moment
            raise NotImplementedError("Gemini does not support tools with web grounding")
        body = {
            "contents": [],
            "generationConfig": {
                "temperature": temperature,
            },
        }
        if system_prompts:
            body["systemInstruction"] = {
                "parts": [
                    {"text": prompt}
                    for prompt in system_prompts
                ],
            }
        if user_prompts:
            body["contents"].append({
                "role": "user",
                "parts": [
                    {"text": prompt}
                    for prompt in user_prompts
                ],
            })

        body["contents"].extend(inputs)

        if files:
            def _build_file(idx, file):
                if file["mimetype"] == "text/plain":
                    return {"text": file["value"]}

                return {"inline_data": {"mime_type": file['mimetype'], "data": file["value"]}}

            body["contents"].append({"role": "user", "parts":
                [_build_file(idx, file) for idx, file in enumerate(files, start=1)]})

        if schema:
            body["generationConfig"]["responseMimeType"] = "application/json"
            body["generationConfig"]["responseJsonSchema"] = schema

        if tools:
            body["tools"] = {
                "functionDeclarations": [{
                    "description": tool_description,
                    "parameters": tool_parameter_schema,
                    "name": tool_name,
                } for tool_name, (tool_description, __, __, tool_parameter_schema) in tools.items()]
            }
        if web_grounding:
            body["tools"] = {'google_search': {}}

        with api_call_logging(body["contents"], tools) as record_response:
            response, to_call, next_inputs = self._request_llm_google_helper(body, llm_model, inputs)
            if record_response:
                record_response(to_call, response)
            return response, to_call, next_inputs

    def _request_llm_google_helper(self, body, llm_model, inputs=()):
        llm_response = self._request(
            "post",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            headers={},
            endpoint=f"/models/{llm_model}:generateContent",
            params={"key": self._get_api_token()},
            body=body,
            timeout=120,
        )

        to_call = []
        response = []
        next_inputs = list(inputs or ())

        for candidate in llm_response.get("candidates") or ():
            for line in candidate.get('content', {}).get('parts') or ():
                if f_info := line.get('functionCall'):
                    to_call.append((f_info['name'], f_info['name'], f_info['args']))
                    next_inputs.append({"role": "model", "parts": [line]})
                elif r := line.get('text'):
                    response.append(r)
                else:
                    _logger.warning("Gemini: could not parse %s", line)

        return response, to_call, next_inputs

    def _request_llm(self, *args, **kwargs):
        if self.provider == 'openai':
            return self._request_llm_openai(*args, **kwargs)

        if self.provider == 'google':
            return self._request_llm_google(*args, **kwargs)

        raise NotImplementedError()

    def request_llm(
        self, llm_model: str, system_prompts: list[str], user_prompts: list[str],
        tools: dict[str, tuple[str, bool, Callable[[dict[str, Any]], Any], dict]] | None = None,
        files: list[dict] | None = None, schema: dict | None = None, temperature: float = 0.2,
        inputs: list[dict] | None = None, web_grounding: bool = False,
    ) -> list[str]:
        """Same as `_request_llm`, but will call the tools until we are done.

        >>> files = [
        >>>     {'mimetype': 'text/plain', 'value': 'text content', 'file_ref': '<file_#1>'},
        >>>     {'mimetype': 'image/png', 'value': 'aW1hZ2UgY29udGVudA==', 'file_ref': '<file_#2>'},
        >>>     {'mimetype': 'application/pdf', 'value': 'cGRmIGNvbnRlbnQ=', 'file_ref': '<file_#3>'},
        >>> ]

        >>> tools = {
        >>>     "function_1": (
        >>>         "This function compute a sum",
        >>>         lambda arguments: arguments['a'] + arguments['b'],
        >>>         json_schema,
        >>>     ),
        >>>     "function_2": ...
        >>> }
        > https://json-schema.org/
        """
        with ai_response_logging(llm_model):
            return self._request_llm_silent(
                llm_model=llm_model,
                system_prompts=system_prompts,
                user_prompts=user_prompts,
                tools=tools,
                files=files,
                schema=schema,
                temperature=temperature,
                inputs=inputs,
                web_grounding=web_grounding,
            )

    def _request_llm_silent(
        self, llm_model: str, system_prompts: list[str], user_prompts: list[str],
        tools: dict[str, tuple[str, bool, Callable[[dict[str, Any]], Any], dict]] | None = None,
        files: list[dict] | None = None, schema: dict | None = None, temperature: float = 0.2,
        inputs: list[dict] | None = None, web_grounding: bool = False,
    ):
        """Wraps the `_request_llm` method to handle multiple calls and tool execution."""
        AI_MAX_SUCCESSIVE_CALLS = int(self.env["ir.config_parameter"].sudo()
            .get_param("ai.max_successive_calls", "20"))

        AI_MAX_TOOL_CALLS_PER_CALL = int(self.env["ir.config_parameter"].sudo()
            .get_param("ai.max_tool_calls_per_call", "20"))

        if tools:
            # Avoid copy.deepcopy on the entire tools dict because it contains
            # partial() callables referencing Odoo Environment objects which
            # cannot be deep-copied. Only deep-copy the JSON schema dicts.
            tools = {
                name: (desc, allow_end, callback, copy.deepcopy(schema))
                for name, (desc, allow_end, callback, schema) in tools.items()
            }
            for __, allow_end_message, __, tool_parameter_schema in tools.values():
                if allow_end_message and "__end_message" not in tool_parameter_schema["properties"]:
                    tool_parameter_schema["properties"]["__end_message"] = {
                        "type": "string",
                        "description": "If you are not waiting a result and you are done, write here your last message (it must follow the instructions). If you will do an action after this one, leave it empty.",
                    }
                if "__end_message" in tool_parameter_schema["properties"] and "__end_message" not in tool_parameter_schema["required"]:
                    tool_parameter_schema["required"].append("__end_message")

        inputs = inputs or []

        if self.provider == 'google':
            # OpenAI / Odoo inputs -> Gemini
            inputs = [
                {"role": "user" if i["role"] == "user" else "model", "parts": [{"text": i["content"]}]}
                for i in inputs
            ]

        all_responses = []
        for api_call in range(AI_MAX_SUCCESSIVE_CALLS):
            responses, next_actions, inputs = self._request_llm(
                llm_model,
                system_prompts,
                user_prompts,
                files=files,
                inputs=inputs,
                schema=schema,
                tools=tools,
                temperature=temperature,
                web_grounding=web_grounding,
            )
            all_responses.extend(responses)

            if not next_actions:
                break

            done = False
            limited_next_actions = next_actions[:AI_MAX_TOOL_CALLS_PER_CALL]
            session = get_ai_logging_session()

            if session:
                session["tool_calls"] += len(limited_next_actions)

            for tool_name, call_id, arguments in limited_next_actions:
                if tool_name not in tools:
                    _logger.error("AI: Try to call a forbidden action %s", tool_name)
                    continue

                has_end_message = "__end_message" in arguments
                end_message = arguments.pop("__end_message", None)
                result, error = tools[tool_name][2](arguments=arguments)

                inputs.append(self._build_tool_call_response(call_id, result))

                if has_end_message and error is None:
                    done = True
                    if end_response := end_message and end_message.strip():
                        all_responses.append(end_response)
                        _logger.info("AI: action terminate early: %s", end_response)
                    else:
                        _logger.info("AI: action terminate early with empty message")

            if session and len(limited_next_actions) > 1:  # Batch of tool calls
                _logger.debug("[AI Tool Summary] Batch #%d completed, %d tool calls", session["current_batch_id"], len(limited_next_actions))

            if done:
                break

        _logger.info("AI: API calls %s", api_call + 1)

        return all_responses

    def _to_open_ai_tool_schema(self, schema):
        """Convert the tool schema if needed.

        Open AI `responses` endpoints needs all parameters to be in the
        "required" list, but it accepts `"type": ["string", "null"]`.

        So we convert the base JSON schema to the array version if needed.
        """
        if self.provider != "openai":
            return schema

        for tool in schema:
            required = tool["parameters"]["required"]
            non_required = set(tool["parameters"]["properties"]) - set(required)
            for name in non_required:
                tool["parameters"]["properties"][name]["type"] = [tool["parameters"]["properties"][name]["type"], "null"]
            tool["parameters"]["required"].extend(non_required)
            tool["parameters"]["additionalProperties"] = False
        return schema

    def _build_tool_call_response(self, tool_call_id, return_value):
        """Build the response for the given tool call.

        :param tool_call_id: The identifier of the tool call
        :param return_value: The value the tool returned
        """
        if self.provider == "openai":
            return {
                "type": "function_call_output",
                "call_id": tool_call_id,
                "output": str(return_value),
            }

        if self.provider == "google":
            return {
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": tool_call_id,
                        "response": {"result": str(return_value)},
                    },
                }],
            }

        raise NotImplementedError(f"Unsupported provider: {self.provider}")

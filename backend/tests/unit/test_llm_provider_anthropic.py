"""AnthropicLLMProvider tests (ticket section 18).

No live Anthropic API key or network access is used or required
anywhere in this file -- every test injects a fake client object
mimicking only the shape of the real SDK's response
(`.content` list of blocks with `.type`/`.name`/`.input`). This proves
the adapter's own mapping/parsing logic without depending on the
`anthropic` package being installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import SecretStr

from app.agent.actions import AgentAction, ActionType, SearchArgs, SearchRoute
from app.config import Settings
from app.integrations.llm_provider import (
    AnthropicLLMProvider,
    LLMDecisionRequest,
    LLMProviderConfigurationError,
    LLMProviderMalformedResponseError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
)


def _settings(**overrides) -> Settings:
    defaults = dict(_env_file=None, anthropic_api_key=SecretStr("sk-ant-super-secret-value"), pantrypilot_llm_model="claude-sonnet-5")
    defaults.update(overrides)
    return Settings(**defaults)


@dataclass
class FakeToolUseBlock:
    input: dict
    name: str = "pantrypilot_agent_decision"
    type: str = "tool_use"


@dataclass
class FakeResponse:
    content: list = field(default_factory=list)


class FakeMessagesAPI:
    def __init__(self, response=None, exception: Exception | None = None):
        self._response = response
        self._exception = exception
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exception is not None:
            raise self._exception
        return self._response


class FakeAnthropicClient:
    def __init__(self, response=None, exception: Exception | None = None):
        self.messages = FakeMessagesAPI(response=response, exception=exception)


def _request() -> LLMDecisionRequest:
    return LLMDecisionRequest(
        system_policy="policy",
        action_schema=AgentAction.model_json_schema(),
        observation={"state_summary": {}, "latest_search_observation": None},
    )


# --- successful structured action mapping / tool arguments --------------------


async def test_successful_response_maps_to_raw_action_and_model_name():
    action = AgentAction(action_type=ActionType.SEARCH, search=SearchArgs(route=SearchRoute.RECIPEAPI_IO, anchor_ingredients=["tomato"]))
    raw = action.model_dump(mode="json")
    client = FakeAnthropicClient(response=FakeResponse(content=[FakeToolUseBlock(input=raw)]))
    provider = AnthropicLLMProvider(_settings(), client=client)

    result = await provider.decide(_request())

    assert result.raw_action == raw
    assert result.model_name == "claude-sonnet-5"


async def test_tool_schema_and_model_are_passed_through_to_the_client():
    client = FakeAnthropicClient(response=FakeResponse(content=[FakeToolUseBlock(input={"action_type": "stop", "stop": {"reason": "attempt_limit_reached"}})]))
    provider = AnthropicLLMProvider(_settings(pantrypilot_llm_model="claude-fable-5-1"), client=client)

    await provider.decide(_request())

    [call] = client.messages.calls
    assert call["model"] == "claude-fable-5-1"
    assert call["tools"][0]["name"] == "pantrypilot_agent_decision"
    assert call["tool_choice"] == {"type": "tool", "name": "pantrypilot_agent_decision"}
    assert call["system"] == "policy"


# --- malformed / empty response ------------------------------------------------


async def test_empty_content_raises_malformed_response_error():
    client = FakeAnthropicClient(response=FakeResponse(content=[]))
    provider = AnthropicLLMProvider(_settings(), client=client)

    with pytest.raises(LLMProviderMalformedResponseError):
        await provider.decide(_request())


async def test_missing_tool_use_block_raises_malformed_response_error():
    @dataclass
    class TextBlock:
        text: str = "just some prose"
        type: str = "text"

    client = FakeAnthropicClient(response=FakeResponse(content=[TextBlock()]))
    provider = AnthropicLLMProvider(_settings(), client=client)

    with pytest.raises(LLMProviderMalformedResponseError):
        await provider.decide(_request())


async def test_non_dict_tool_input_raises_malformed_response_error():
    client = FakeAnthropicClient(response=FakeResponse(content=[FakeToolUseBlock(input="not-a-dict")]))
    provider = AnthropicLLMProvider(_settings(), client=client)

    with pytest.raises(LLMProviderMalformedResponseError):
        await provider.decide(_request())


# --- authentication/config absence ---------------------------------------------


def test_missing_api_key_raises_controlled_configuration_error_not_a_crash():
    with pytest.raises(LLMProviderConfigurationError):
        AnthropicLLMProvider(_settings(anthropic_api_key=None))


def test_missing_model_raises_controlled_configuration_error():
    with pytest.raises(LLMProviderConfigurationError):
        AnthropicLLMProvider(_settings(pantrypilot_llm_model=None))


# --- timeout / error mapping ----------------------------------------------------


async def test_client_timeout_exception_is_mapped_to_typed_timeout_error():
    class APITimeoutError(Exception):
        pass

    client = FakeAnthropicClient(exception=APITimeoutError("timed out"))
    provider = AnthropicLLMProvider(_settings(), client=client)

    with pytest.raises(LLMProviderTimeoutError):
        await provider.decide(_request())


async def test_client_auth_exception_is_mapped_to_typed_configuration_error():
    class AuthenticationError(Exception):
        pass

    client = FakeAnthropicClient(exception=AuthenticationError("bad key: sk-ant-super-secret-value"))
    provider = AnthropicLLMProvider(_settings(), client=client)

    with pytest.raises(LLMProviderConfigurationError):
        await provider.decide(_request())


async def test_client_unexpected_exception_is_mapped_to_unavailable_error():
    client = FakeAnthropicClient(exception=RuntimeError("boom"))
    provider = AnthropicLLMProvider(_settings(), client=client)

    with pytest.raises(LLMProviderUnavailableError):
        await provider.decide(_request())


# --- API key never appears in exception text -----------------------------------


async def test_api_key_never_appears_in_any_raised_exception_text():
    secret = "sk-ant-super-secret-value"  # fake value, not a real key  # secret-scan: allow

    class AuthenticationError(Exception):
        pass

    client = FakeAnthropicClient(exception=AuthenticationError(f"rejected key {secret}"))
    provider = AnthropicLLMProvider(_settings(anthropic_api_key=SecretStr(secret)), client=client)

    try:
        await provider.decide(_request())
        pytest.fail("expected LLMProviderConfigurationError")
    except LLMProviderConfigurationError as exc:
        assert secret not in str(exc)
        assert secret not in repr(exc)


def test_api_key_never_appears_in_settings_repr():
    settings = _settings(anthropic_api_key=SecretStr("sk-ant-super-secret-value"))
    assert "sk-ant-super-secret-value" not in repr(settings)
    assert "sk-ant-super-secret-value" not in str(settings)


# --- fake provider substitutes for the Anthropic provider ----------------------


async def test_fake_provider_satisfies_the_llm_provider_protocol():
    from app.integrations.llm_provider import LLMDecisionResponse, LLMProvider

    class FakeLLM:
        provider_name = "fake"

        async def decide(self, request: LLMDecisionRequest) -> LLMDecisionResponse:
            return LLMDecisionResponse(raw_action={"action_type": "stop", "stop": {"reason": "attempt_limit_reached"}}, model_name="fake")

    fake = FakeLLM()
    assert isinstance(fake, LLMProvider)
    result = await fake.decide(_request())
    assert result.model_name == "fake"

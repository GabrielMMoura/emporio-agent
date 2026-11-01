"""Agent loop tests. The LLM is replaced by a scripted fake; tools run for real."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from emporio_agent import clock
from emporio_agent.agent import FALLBACK_REPLY, Agent, create_agent, format_arguments
from emporio_agent.config import Settings
from emporio_agent.tools import tool_schemas


def reply(content):
    return SimpleNamespace(content=content, tool_calls=None)


def tool_request(*calls):
    return SimpleNamespace(
        content=None,
        tool_calls=[
            SimpleNamespace(
                id=f"call_{i}",
                function=SimpleNamespace(name=name, arguments=json.dumps(args)),
            )
            for i, (name, args) in enumerate(calls)
        ],
    )


class FakeClient:
    """Returns scripted messages in order and records every request."""

    def __init__(self, *messages):
        self.script = list(messages)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=item)])


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    frozen = datetime(2026, 11, 4, 10, 30, tzinfo=clock.STORE_TZ)
    monkeypatch.setattr(clock, "now", lambda: frozen)


def test_plain_answer_without_tools():
    client = FakeClient(reply("Olá! Como posso ajudar?"))
    agent = Agent(client, "fake-model")

    turn = agent.ask("oi")

    assert turn.reply == "Olá! Como posso ajudar?"
    assert turn.tool_calls == []
    assert agent.messages == [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "Olá! Como posso ajudar?"},
    ]
    request = client.requests[0]
    assert request["model"] == "fake-model"
    assert request["tools"] == tool_schemas()
    system = request["messages"][0]
    assert system["role"] == "system"
    assert "quarta-feira, 04/11/2026 10:30" in system["content"]


def test_tool_call_is_executed_and_result_sent_back():
    client = FakeClient(
        tool_request(("get_product_details", {"product_id": 95})),
        reply("O Takamine GD20 custa R$ 2.199,00."),
    )
    agent = Agent(client, "fake-model")

    turn = agent.ask("quanto custa o takamine gd20?")

    assert turn.reply == "O Takamine GD20 custa R$ 2.199,00."
    assert [c.name for c in turn.tool_calls] == ["get_product_details"]
    assert json.loads(turn.tool_calls[0].result)["price"] == "R$ 2.199,00"

    second_request = client.requests[1]["messages"]
    assistant_call, tool_result = second_request[-2], second_request[-1]
    assert assistant_call["tool_calls"][0]["function"]["name"] == "get_product_details"
    assert tool_result["role"] == "tool"
    assert tool_result["tool_call_id"] == "call_0"
    assert "R$ 2.199,00" in tool_result["content"]


def test_parallel_tool_calls_in_one_round():
    client = FakeClient(
        tool_request(("get_store_status", {}), ("get_policy", {"topic": "hours"})),
        reply("Estamos abertos."),
    )
    turn = Agent(client, "fake-model").ask("vocês estão abertos?")
    assert [c.name for c in turn.tool_calls] == ["get_store_status", "get_policy"]
    assert json.loads(turn.tool_calls[0].result)["is_open"] is True


def test_tool_errors_are_returned_to_the_model_not_raised():
    client = FakeClient(
        tool_request(("get_product_details", {"wrong_arg": 1})),
        reply("Não encontrei esse produto."),
    )
    turn = Agent(client, "fake-model").ask("produto x")
    assert "error" in json.loads(turn.tool_calls[0].result)
    assert turn.reply == "Não encontrei esse produto."


def test_stops_after_max_rounds_with_fallback():
    looping = [tool_request(("list_categories", {})) for _ in range(3)]
    agent = Agent(FakeClient(*looping), "fake-model", max_tool_rounds=3)

    turn = agent.ask("?")

    assert turn.reply == FALLBACK_REPLY
    assert len(turn.tool_calls) == 3
    assert agent.messages[-1] == {"role": "assistant", "content": FALLBACK_REPLY}


def test_history_is_kept_across_turns():
    client = FakeClient(reply("R$ 2.199,00"), reply("No PIX fica R$ 2.089,05"))
    agent = Agent(client, "fake-model")
    agent.ask("quanto custa o takamine gd20?")
    agent.ask("e no pix?")
    sent = client.requests[1]["messages"]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]


def test_api_error_rolls_back_the_turn():
    client = FakeClient(reply("primeira"), RuntimeError("API down"))
    agent = Agent(client, "fake-model")
    agent.ask("oi")
    before = list(agent.messages)

    with pytest.raises(RuntimeError):
        agent.ask("tudo bem?")

    assert agent.messages == before


def test_reset_clears_history():
    agent = Agent(FakeClient(reply("oi")), "fake-model")
    agent.ask("oi")
    agent.reset()
    assert agent.messages == []


def test_create_agent_requires_api_key():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        create_agent(Settings(api_key=None, base_url="http://x", model="m"))


def test_format_arguments():
    assert (
        format_arguments('{"product_id": 95, "query": "violão"}') == 'product_id=95, query="violão"'
    )
    assert format_arguments("") == ""

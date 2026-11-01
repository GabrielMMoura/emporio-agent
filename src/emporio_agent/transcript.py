"""Renders a conversation as Markdown, showing which tools ran in each turn."""

import json

from emporio_agent.agent import Turn, format_arguments


def _pretty_result(result: str) -> str:
    try:
        return json.dumps(json.loads(result), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return result


def _blockquote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def to_markdown(turns: list[Turn], title: str, description: str = "", model: str = "") -> str:
    lines = [f"# {title}", ""]
    if description:
        lines += [description, ""]
    if model:
        lines += [f"Model: `{model}`", ""]

    for turn in turns:
        lines += ["**Cliente:**", "", _blockquote(turn.user), ""]
        if turn.tool_calls:
            calls = ", ".join(
                f"`{c.name}({format_arguments(c.arguments)})`" for c in turn.tool_calls
            )
            lines += [f"Tools called: {calls}", ""]
            lines += ["<details><summary>Tool results</summary>", ""]
            for call in turn.tool_calls:
                lines += [
                    f"`{call.name}({format_arguments(call.arguments)})`",
                    "",
                    "```json",
                    _pretty_result(call.result),
                    "```",
                    "",
                ]
            lines += ["</details>", ""]
        else:
            lines += ["Tools called: none", ""]
        lines += ["**Agente:**", "", _blockquote(turn.reply), "", "---", ""]
    return "\n".join(lines).rstrip("-\n") + "\n"

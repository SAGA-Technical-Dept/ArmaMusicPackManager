"""AI 翻译服务：调用 OpenAI 兼容 Chat Completions API 翻译曲目名。"""

from __future__ import annotations

import json
import re

import httpx

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
TRANSLATE_TIMEOUT = 60.0

_SYSTEM_PROMPT = (
    "你是 Arma 3 游戏音乐模组的曲目名翻译助手。"
    "将英文音乐曲目名翻译为简洁、自然的中文。"
    "规则：专有名词（专辑名、游戏名、人名、地名）可保留原文或音译；"
    "游戏原声带曲名保留简洁风格；不要加引号；只输出翻译结果，不要解释。"
)


def translate_names(
    names: list[str],
    base_url: str = DEFAULT_BASE_URL,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
) -> dict[str, str]:
    """批量翻译曲目名，返回 {原文: 翻译} 映射。

    一次性发送全部名称（单次请求，节省调用）。解析失败时对失败名称抛
    TranslationError。
    """
    if not api_key:
        raise TranslationError("未配置 API Key")
    if not names:
        return {}

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": (
                "请将以下曲目名翻译成中文，以 JSON 对象返回："
                '{"原曲名": "中文翻译", ...}\n' + json.dumps(names, ensure_ascii=False))},
        ],
        "temperature": 0.3,
    }
    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=TRANSLATE_TIMEOUT,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        raise TranslationError(f"API 返回 {exc.response.status_code}: {exc.response.text[:200]}") from exc
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise TranslationError(f"请求失败: {exc}") from exc

    data = _parse_json_response(content)
    if not isinstance(data, dict):
        raise TranslationError("API 返回格式无法解析（期望 JSON 对象）")
    return {str(k): str(v) for k, v in data.items() if str(k).strip()}


def _parse_json_response(content: str) -> object:
    """解析模型输出：剥离 ```json 围栏等常见干扰。"""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 容错：提取最外层 { ... } 再解析
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise TranslationError("API 输出不是有效 JSON")


class TranslationError(RuntimeError):
    pass

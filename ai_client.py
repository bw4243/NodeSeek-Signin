# -*- coding: utf-8 -*-

import os
from dataclasses import dataclass
from typing import Dict, Optional

try:
    import google.generativeai as genai
    _has_gemini = True
except Exception:
    _has_gemini = False


@dataclass
class GenConfig:
    model: str = "gemini-1.5-flash"
    min_len: int = 120
    max_len: int = 220
    language: str = "zh"


class AIClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        if api_key is None:
            api_key = os.getenv("GOOGLE_API_KEY", "")
        self.enabled = bool(api_key and _has_gemini)
        self.model_name = model or os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
        if self.enabled:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            self.model = None

    def generate_comment(self, context: Dict, cfg: GenConfig) -> str:
        """
        根据帖子上下文生成评论（中文、限定长度、避免 AI 自述）。
        """
        if not self.enabled:
            return ""

        title = context.get("title") or ""
        op_summary = context.get("op_summary") or ""
        comments = context.get("comments") or []

        examples = "\n\n".join([f"示例评论 {i+1}: {c[:300]}" for i, c in enumerate(comments[:6])])

        prompt = f"""
你是一位参与论坛讨论的普通用户。请根据帖子标题、楼主内容摘要与若干示例评论，模仿整体语气与表达习惯，生成一条自然、友好、简洁但有信息增量的中文评论。

严格要求：
- 语言：中文
- 长度：在 {cfg.min_len}-{cfg.max_len} 字之间
- 不要包含网址、广告、联系方式、@他人、敏感词
- 不要暴露“AI”“模型”等字眼，不要自称 AI
- 不要复述原文大段内容，给出简短观点或补充建议
- 不要透露隐私信息，不要要求对方私聊

帖子标题：{title}
楼主摘要：{op_summary[:500]}
{examples}

请直接输出评论正文，不要添加前缀或解释。
""".strip()

        resp = self.model.generate_content(prompt)
        text = (resp.text or "").strip()

        # 基础裁剪与清理
        if not text:
            return ""
        if len(text) > cfg.max_len:
            text = text[: cfg.max_len].rstrip()
        return text

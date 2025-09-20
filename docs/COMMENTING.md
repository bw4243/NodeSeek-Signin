# 自动评论功能（预览）

本模块提供“自动抓取帖子上下文 → 使用 Google AI Studio (Gemini) 生成评论 →（暂不发布，干跑）”的能力，默认目标分类为 `https://www.nodeseek.com/categories/review`。

当前仅启用“干跑”流程，用于生成评论草稿。后续将与您一同对接回复接口与页面字段解析，完成正式发布。

## 环境变量

- `NS_COMMENT_ENABLED`：是否启用自动评论（默认 `false`）
- `NS_COMMENT_CATEGORY_SLUG`：评论目标分类（当前固定为 `review`）
- `NS_COMMENT_DAILY_LIMIT`：每账号每日评论上限（默认 2）
- `COMMENT_RUN_AT`：评论调度时间（例如 `10:30` 或 `14:00-21:00`），不设默认为 `14:00-21:00`
- `NS_COMMENT_DRY_RUN`：干跑（只生成不发布），默认 `true`
- `NS_COMMENT_SAMPLE_COUNT`：示例评论抓取数量，默认 6
- `NS_COMMENT_MIN_SAMPLE`：至少需要的“他人评论”数量，默认 2（不足则跳过）
- `NS_COMMENT_MIN_LEN`/`NS_COMMENT_MAX_LEN`：生成评论长度范围，默认 120/220
- `NS_COMMENT_BLACKLIST`：黑名单关键词，默认 `广告,推广,微信,钉钉,http://,https://,@`
- `NS_COMMENT_BACKOFF`：评论之间随机等待秒数范围，默认 `60-180`
- `GOOGLE_API_KEY`：Google AI Studio API key（必需）
- `GOOGLE_MODEL`：生成模型，默认 `gemini-1.5-flash`
- `NS_COMMENT_REPLY_ENDPOINT`：手动指定回复接口（可选），支持 `{id}` 占位符，例如 `/api/topic/reply` 或 `/api/t/{id}/reply`
- `NS_THREAD_URLS`：可直接指定要处理的帖子 URL 列表（逗号或换行分隔），可用于绕过分类页抓取被拦截的情况
- 覆盖请求头以模拟浏览器（可选）：`NS_UA`、`NS_ACCEPT`、`NS_ACCEPT_LANGUAGE`、`NS_ACCEPT_ENCODING`、`NS_SEC_CH_UA`、`NS_SEC_CH_UA_MOBILE`、`NS_SEC_CH_UA_PLATFORM`、`NS_SEC_FETCH_DEST`、`NS_SEC_FETCH_MODE`、`NS_SEC_FETCH_SITE`、`NS_CACHE_CONTROL`、`NS_PRAGMA`、`NS_REFERER`、`NS_REFRACT_KEY`、`NS_REFRACT_SIGN`、`NS_REFRACT_VERSION`

## 运行方式

- 一次性执行（遵循干跑/正式由环境变量控制）：
  ```bash
  python commenter.py
  ```
- 独立调度（与签到解耦）：
  ```bash
  python comment_scheduler.py
  ```

## 工作流程

1. 从 `NS_COOKIE`（或 Docker 文件 `./cookie/NS_COOKIE.txt`）读取账号 Cookie 列表。
2. 在目标分类页抓取帖子列表，随机选取未近期处理的帖（后续会补全更细策略）。
3. 抓取帖子页标题、楼主摘要、最近 N 条“他人评论”文本作为上下文；若该帖“他人评论”少于 2 条（可配 `NS_COMMENT_MIN_SAMPLE`），则跳过该帖。
4. 使用 Gemini 根据上下文生成评论草稿（中文、长度与风控约束）。
5. 干跑模式下仅打印并可选通知；正式模式将完成真实发布（待对接）。

## 通知

沿用仓库内 `notify.py`，可用企业微信机器人（`QYWX_KEY`）或企业微信应用（`QYWX_AM`）等方式接收“成功/失败/草稿”通知。

---

如需更改分类、上限或时间窗，直接在 `.env` 中修改对应变量即可。

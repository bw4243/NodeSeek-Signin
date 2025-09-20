# -*- coding: utf-8 -*-

import json
import os
import random
import time
from datetime import datetime, timezone, timedelta
from typing import List

from ai_client import AIClient, GenConfig
from nodeseek_client import NodeSeekClient


# ---------------- 通知模块（可选） ----------------
hadsend = False
try:
    from notify import send

    hadsend = True
except Exception:
    def send(*args, **kwargs):
        pass


GMT8 = timezone(timedelta(hours=8))
HISTORY_FILE = "./cookie/comment_history.json"


def _load_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_history(data: dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get_daily_key() -> str:
    return datetime.now(GMT8).strftime("%Y-%m-%d")


def _safe_filter(txt: str, blacklist: List[str]) -> bool:
    if not txt:
        return False
    if any(b in txt for b in blacklist):
        return False
    if "http://" in txt or "https://" in txt:
        return False
    if "@" in txt:
        return False
    return True


def _pick_targets(client: NodeSeekClient, category_slug: str, max_threads: int) -> List[dict]:
    # 目前抓取第 1 页，后续可扩展多页与过滤规则
    threads = client.get_category_threads(category_slug=category_slug, page=1)
    random.shuffle(threads)
    return threads[:max_threads]


def run_comment_for_account(ns_cookie: str, account_label: str, dry_run: bool = True):
    if not ns_cookie:
        print(f"[{account_label}] 无有效Cookie，跳过评论")
        return

    # 读取配置
    category_slug = os.getenv("NS_COMMENT_CATEGORY_SLUG", "review")
    daily_limit = int(os.getenv("NS_COMMENT_DAILY_LIMIT", "2") or 2)
    sample_count = int(os.getenv("NS_COMMENT_SAMPLE_COUNT", "6") or 6)
    min_len = int(os.getenv("NS_COMMENT_MIN_LEN", "120") or 120)
    max_len = int(os.getenv("NS_COMMENT_MAX_LEN", "220") or 220)
    min_sample = int(os.getenv("NS_COMMENT_MIN_SAMPLE", "2") or 2)
    blacklist = [s for s in os.getenv("NS_COMMENT_BLACKLIST", "广告,推广,微信,钉钉").split(",") if s]
    backoff_range = os.getenv("NS_COMMENT_BACKOFF", "60-180")
    try:
        backoff_min, backoff_max = [int(x) for x in backoff_range.split("-")]
    except Exception:
        backoff_min, backoff_max = 60, 180
    read_delay_range = os.getenv("NS_COMMENT_READ_DELAY", "8-18")
    try:
        read_delay_min, read_delay_max = [int(x) for x in read_delay_range.split("-")]
    except Exception:
        read_delay_min, read_delay_max = 8, 18
    if read_delay_min > read_delay_max:
        read_delay_min, read_delay_max = read_delay_max, read_delay_min
    read_delay_min = max(0, read_delay_min)
    read_delay_max = max(read_delay_min, read_delay_max)

    # 限流与历史
    history = _load_history()
    day_key = _get_daily_key()
    acc_hist = history.get(day_key, {}).get(account_label, {"count": 0, "threads": []})
    sent_count = acc_hist.get("count", 0)

    if sent_count >= daily_limit and not dry_run:
        print(f"[{account_label}] 今日评论已达上限({daily_limit})，跳过")
        return

    ai = AIClient()
    if not ai.enabled:
        print("未检测到 GOOGLE_API_KEY 或未安装 google-generativeai，跳过 AI 生成。")
        return

    client = NodeSeekClient(ns_cookie)

    # 优先使用显式帖子URL（避免分类页被防护拦截）
    explicit_urls = [u.strip() for u in (os.getenv("NS_THREAD_URLS", "").replace("\n", ",")).split(",") if u.strip()]
    targets = []
    if explicit_urls:
        import re as _re
        for u in explicit_urls:
            m_p = _re.search(r"/post-(\d+)", u)
            m_t = _re.search(r"/t/(\d+)", u)
            tid = int(m_p.group(1)) if m_p else (int(m_t.group(1)) if m_t else None)
            targets.append({"title": u, "url": u, "thread_id": tid})
    else:
        targets = _pick_targets(client, category_slug, max_threads=daily_limit)
    if not targets:
        print(f"[{account_label}] 未找到可评论的帖子")
        return

    cfg = GenConfig(min_len=min_len, max_len=max_len)

    for i, t in enumerate(targets, 1):
        if not dry_run and sent_count >= daily_limit:
            break

        url = t.get("url")
        title = t.get("title")
        print(f"[{account_label}] 目标{i}: {title} -> {url}")

        try:
            ctx = client.get_thread_context(url, sample_count=sample_count)
        except PermissionError as e:
            print(f"[{account_label}] 获取上下文失败(403): {e}，终止该账号")
            break
        except Exception as e:
            print(f"[{account_label}] 获取上下文失败: {e}")
            fail_wait = random.randint(backoff_min, backoff_max) if backoff_max >= backoff_min and backoff_max > 0 else 0
            if fail_wait > 0:
                print(f"[{account_label}] Cooldown {fail_wait}s before trying another thread")
                time.sleep(fail_wait)
            continue

        # 跳过已评论的帖子
        if ctx.get("has_commented"):
            print(f"[{account_label}] 检测到已在该帖评论，跳过")
            continue

        # 跳过无人回复的帖子（无可模仿样本）
        other_comments = ctx.get("comments") or []
        if len(other_comments) < min_sample:
            print(f"[{account_label}] 他人回复不足 {min_sample} 条，跳过")
            continue

        browse_delay = random.randint(read_delay_min, read_delay_max) if read_delay_max > 0 else 0
        if browse_delay > 0:
            print(f"[{account_label}] Pause {browse_delay}s to mimic reading")
            time.sleep(browse_delay)

        comment = ai.generate_comment(ctx, cfg).strip()
        if not _safe_filter(comment, blacklist):
            print(f"[{account_label}] 生成评论不合规或为空，跳过")
            continue

        if dry_run:
            print("------ DRY RUN 生成评论（未发布） ------")
            print(comment)
            print("------------------------------------")
            if hadsend:
                try:
                    send("NodeSeek 评论干跑", f"{account_label} 在 {title} 的草稿评论:\n{comment}")
                except Exception:
                    pass
        else:
            ok, msg = client.post_reply(url, comment, csrf=ctx.get("csrf"))
            print(f"[{account_label}] 发布结果: ok={ok}, msg={msg}")
            if ok:
                sent_count += 1
                # 持久化历史
                history.setdefault(day_key, {}).setdefault(account_label, {"count": 0, "threads": []})
                history[day_key][account_label]["count"] = sent_count
                history[day_key][account_label]["threads"].append(url)
                _save_history(history)
                if hadsend:
                    try:
                        send("NodeSeek 评论成功", f"{account_label} 在 {title} 评论成功:\n{comment}")
                    except Exception:
                        pass
            else:
                if hadsend:
                    try:
                        send("NodeSeek 评论失败", f"{account_label} 在 {title} 评论失败: {msg}")
                    except Exception:
                        pass
                if isinstance(msg, str) and any(code in msg for code in ("403", "429")):
                    print(f"[{account_label}] API returned high-risk status ({msg}); aborting remaining comments")
                    break

        # 随机等待，模拟人类行为
        delay = random.randint(backoff_min, backoff_max)
        print(f"[{account_label}] 随机等待 {delay}s 后继续...")
        time.sleep(delay)


def main():
    # 优先尝试加载 .env（便于本地直接运行）
    # 优先加载 .env（若未安装 python-dotenv，则使用简单回退加载器）
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for raw in f:
                        line = raw.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        os.environ.setdefault(k, v)
            except Exception:
                pass

    # 是否启用干跑
    dry_run = os.getenv("NS_COMMENT_DRY_RUN", "true").lower() == "true"

    # 读取 cookie（与 nodeseek_sign.py 一致的来源优先级）
    COOKIE_FILE_PATH = "./cookie/NS_COOKIE.txt"
    all_cookies = ""
    if os.getenv("IN_DOCKER") == "true":
        if os.path.exists(COOKIE_FILE_PATH):
            try:
                with open(COOKIE_FILE_PATH, "r", encoding="utf-8") as f:
                    all_cookies = f.read().strip()
            except Exception:
                pass
    if not all_cookies:
        all_cookies = os.getenv("NS_COOKIE", "")

    cookie_list = [c.strip() for c in all_cookies.replace("\n", "&").split("&") if c.strip()]

    if not cookie_list:
        print("未检测到 NS_COOKIE，无法进行评论")
        return

    # 每个 cookie 作为一个账号处理
    for idx, ck in enumerate(cookie_list, 1):
        label = f"账号{idx}"
        run_comment_for_account(ck, label, dry_run=dry_run)


if __name__ == "__main__":
    main()

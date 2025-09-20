# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

# ensure project root on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodeseek_client import NodeSeekClient


def main():
    # load .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        import os
        from pathlib import Path
        env_path = Path.cwd() / ".env"
        if env_path.exists():
            try:
                for raw in env_path.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    k = k.strip(); v = v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)
            except Exception:
                pass
    cookie = os.getenv("NS_COOKIE", "")
    client = NodeSeekClient(cookie)
    print("[SMOKE] 抓取 review 分类首页帖子...")
    threads = client.get_category_threads("review", page=1)
    print(f"[SMOKE] 共解析到 {len(threads)} 条候选")
    for t in threads[:3]:
        print(f"- {t['thread_id']}: {t['title']} -> {t['url']}")

    if not threads:
        return

    print("[SMOKE] 抽取第一个帖子的上下文...")
    ctx = client.get_thread_context(threads[0]["url"], sample_count=6)
    print(f"标题: {ctx.get('title')}")
    print(f"已评论: {ctx.get('has_commented')}")
    print(f"楼主摘要(截断): {(ctx.get('op_summary') or '')[:120]}")
    print(f"他人评论数: {len(ctx.get('comments') or [])}")
    for i, c in enumerate((ctx.get('comments') or [])[:3], 1):
        print(f"  样例{i}: {c[:80]}")


if __name__ == "__main__":
    main()

import os
import sys
import time
import datetime
import random
import subprocess
import re
from datetime import timezone, timedelta

GMT8 = timezone(timedelta(hours=8))

# 提示: scheduler.py 已支持在签到完成后自动执行评论任务。
# 本脚本仅用于需要独立调度评论的高级场景。


def get_run_config(var_name: str, default_range: str) -> tuple[str, str]:
    """
    从环境变量读取并解析运行时间配置
    - 'HH:MM': 固定时间
    - 'HH:MM-HH:MM': 随机时间范围
    - 未设置或格式错误: 使用 default_range
    返回 (mode, value)
    """
    run_at_env = os.environ.get(var_name, default_range)

    if re.fullmatch(r"\d{2}:\d{2}", run_at_env):
        print(f"[{var_name}] 检测到固定时间模式: {run_at_env}", flush=True)
        return "fixed", run_at_env

    if re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", run_at_env):
        print(f"[{var_name}] 检测到随机时间范围模式: {run_at_env}", flush=True)
        return "range", run_at_env

    if os.environ.get(var_name):
        print(f"警告: 环境变量 {var_name} 的格式 '{run_at_env}' 无效", flush=True)

    print(f"[{var_name}] 将使用默认随机时间范围 '{default_range}'", flush=True)
    return "range", default_range


def calculate_next_run_time(mode: str, value: str) -> datetime.datetime:
    now = datetime.datetime.now(GMT8)
    if mode == "fixed":
        h, m = map(int, value.split(":"))
        next_run_attempt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if next_run_attempt > now:
            return next_run_attempt
        return next_run_attempt + datetime.timedelta(days=1)

    start_str, end_str = value.split("-")
    start_h, start_m = map(int, start_str.split(":"))
    end_h, end_m = map(int, end_str.split(":"))

    start_time = datetime.time(start_h, start_m)
    end_time = datetime.time(end_h, end_m)

    start_today = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    target_date = now.date() if now < start_today else (now.date() + datetime.timedelta(days=1))

    start_target = datetime.datetime.combine(target_date, start_time, tzinfo=GMT8)
    end_target = datetime.datetime.combine(target_date, end_time, tzinfo=GMT8)
    if start_target > end_target:
        end_target += datetime.timedelta(days=1)

    start_timestamp = int(start_target.timestamp())
    end_timestamp = int(end_target.timestamp())
    random_timestamp = random.randint(start_timestamp, end_timestamp)
    return datetime.datetime.fromtimestamp(random_timestamp, tz=GMT8)


def run_comment_task():
    """
    执行 commenter.py 脚本
    """
    if os.environ.get("NS_COMMENT_ENABLED", "false").lower() != "true":
        print("评论任务未启用(NS_COMMENT_ENABLED!=true)，退出", flush=True)
        return
    print(f"[{datetime.datetime.now(GMT8).strftime('%Y-%m-%d %H:%M:%S')}] 开始执行评论任务..", flush=True)
    try:
        subprocess.run([sys.executable, "commenter.py"], check=True)
        print(f"[{datetime.datetime.now(GMT8).strftime('%Y-%m-%d %H:%M:%S')}] 评论任务执行完毕", flush=True)
    except FileNotFoundError:
        print("错误: 'commenter.py' 未找到。请确保它与 comment_scheduler.py 位于同一目录", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"评论任务执行失败，返回码: {e.returncode}", flush=True)
    except Exception as e:
        print(f"执行评论任务时发生未知错误: {e}", flush=True)


def main():
    print("评论调度器启动..", flush=True)
    mode, value = get_run_config("COMMENT_RUN_AT", "14:00-21:00")
    print(f"评论调度模式: '{mode}', 配置为 '{value}'", flush=True)

    while True:
        next_run_time = calculate_next_run_time(mode, value)
        now = datetime.datetime.now(GMT8)
        sleep_duration = (next_run_time - now).total_seconds()

        if sleep_duration > 0:
            print(f"下一次评论任务计划在: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
            hours, remainder = divmod(sleep_duration, 3600)
            minutes, _ = divmod(remainder, 60)
            print(f"程序将休眠 {int(hours)} 小时 {int(minutes)} 分钟", flush=True)
            time.sleep(sleep_duration)
        else:
            print("计算出的下一个运行时间已过，等待 60 秒后重试...", flush=True)
            time.sleep(60)

        run_comment_task()


if __name__ == "__main__":
    main()


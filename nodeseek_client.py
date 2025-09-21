# -*- coding: utf-8 -*-

import re
import os
import base64
import json
import random
import time
from typing import List, Dict, Optional, Tuple

from bs4 import BeautifulSoup
from curl_cffi import requests


class NodeSeekClient:
    """
    NodeSeek 简单客户端（HTML 抓取版）

    说明：
    - 仅用于抓取帖子列表与帖子页面上下文，提交回复的接口与字段待对接。
    - 统一使用 curl_cffi.requests 并设置 impersonate 以降低风控概率。
    """

    BASE = "https://www.nodeseek.com"

    @staticmethod
    def _parse_int(value: Optional[str], default: int, minimum: int = 0) -> int:
        try:
            num = int(value) if value is not None else default
        except Exception:
            return default
        return max(minimum, num)

    @staticmethod
    def _parse_float(value: Optional[str], default: float, minimum: float = 0.0) -> float:
        try:
            num = float(value) if value is not None else default
        except Exception:
            return default
        return max(minimum, num)


    def __init__(self, cookie: str):
        self.cookie = cookie or ""
        self.ua = os.getenv(
            "NS_UA",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        )
        self.logged_in_user_id: Optional[str] = None
        self.impersonate = os.getenv("NS_IMPERSONATE", "chrome110")
        self.timeout = self._parse_float(os.getenv("NS_HTTP_TIMEOUT"), default=30.0, minimum=5.0)
        self.max_retries = self._parse_int(os.getenv("NS_HTTP_RETRY"), default=2, minimum=0)
        self.backoff_base = self._parse_float(os.getenv("NS_HTTP_BACKOFF_BASE"), default=1.6, minimum=1.1)
        self.max_backoff = self._parse_float(os.getenv("NS_HTTP_MAX_BACKOFF"), default=20.0, minimum=1.0)
        self._session = requests.Session(impersonate=self.impersonate)

    def _headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": self.ua,
            "Accept": os.getenv("NS_ACCEPT", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"),
            "Accept-Language": os.getenv("NS_ACCEPT_LANGUAGE", "zh-CN,zh;q=0.9,en;q=0.8"),
            "Connection": "keep-alive",
            "Accept-Encoding": os.getenv("NS_ACCEPT_ENCODING", "gzip, deflate, br, zstd"),
            "Upgrade-Insecure-Requests": "1",
            # Hint headers similar to a real browser
            "sec-ch-ua": os.getenv("NS_SEC_CH_UA", '"Not A(Brand";v="99", "Microsoft Edge";v="121", "Chromium";v="121"'),
            "sec-ch-ua-mobile": os.getenv("NS_SEC_CH_UA_MOBILE", "?0"),
            "sec-ch-ua-platform": os.getenv("NS_SEC_CH_UA_PLATFORM", '"Windows"'),
            # sec-fetch family can be overridden if needed
            "sec-fetch-dest": os.getenv("NS_SEC_FETCH_DEST", "document"),
            "sec-fetch-mode": os.getenv("NS_SEC_FETCH_MODE", "navigate"),
            "sec-fetch-site": os.getenv("NS_SEC_FETCH_SITE", "same-origin"),
            # cache hints
            "Cache-Control": os.getenv("NS_CACHE_CONTROL", "no-cache"),
            "Pragma": os.getenv("NS_PRAGMA", "no-cache"),
        }
        if referer:
            headers["Referer"] = referer
        if self.cookie:
            headers["Cookie"] = self.cookie
        # Optional Refract headers copied from browser
        if os.getenv("NS_REFRACT_KEY"):
            headers["refract-key"] = os.getenv("NS_REFRACT_KEY")
        if os.getenv("NS_REFRACT_SIGN"):
            headers["refract-sign"] = os.getenv("NS_REFRACT_SIGN")
        return headers

    def _retry_delay(self, attempt: int) -> float:
        jitter = random.uniform(0.5, 1.5)
        return min(self.max_backoff, (self.backoff_base ** (attempt + 1)) + jitter)

    def _request(self, method: str, url: str, **kwargs):
        timeout = kwargs.pop("timeout", None) or self.timeout
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.request(method=method, url=url, timeout=timeout, **kwargs)
                if resp.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(self._retry_delay(attempt))
                    continue
                return resp
            except Exception as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    raise
                time.sleep(self._retry_delay(attempt))
        if last_exc:
            raise last_exc
        raise RuntimeError("request failed")

    def _extract_csrf_from_cookie(self) -> Optional[str]:
        env_token = os.getenv("NS_COMMENT_STATIC_CSRF")
        if env_token:
            token = env_token.strip()
            if token:
                return token
        if not self.cookie:
            return None
        for part in self.cookie.split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip().lower()
            if not key:
                continue
            if "csrf" in key or key.endswith("token"):
                value = value.strip()
                if value:
                    return value
        return None

    def _headers_for_api(self, referer: Optional[str], csrf_token: Optional[str]) -> Dict[str, str]:
        headers = self._headers(referer=referer or self.BASE)
        headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": self.BASE,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        headers.pop("Upgrade-Insecure-Requests", None)
        if csrf_token:
            headers["csrf-token"] = csrf_token
        else:
            headers.pop("csrf-token", None)
        headers["X-Requested-With"] = "XMLHttpRequest"
        return headers

    def get_category_threads(self, category_slug: str = "review", page: int = 1) -> List[Dict]:
        """
        抓取分类页的帖子列表（仅解析链接和标题）。
        返回: [{"title": str, "url": str, "thread_id": Optional[int]}]
        """
        # 常见两种分页：?page=N 或 page-N
        url_candidates = [
            f"{self.BASE}/categories/{category_slug}?page={page}",
            f"{self.BASE}/categories/{category_slug}/page-{page}",
            f"{self.BASE}/categories/{category_slug}",
        ]
        last_exc_msg: Optional[str] = None
        html = None
        final_url = None
        for u in url_candidates:
            try:
                ref = os.getenv("NS_REFERER", None)
                resp = self._request("GET", u, headers=self._headers(referer=ref or self.BASE))
                if resp.status_code == 200 and (resp.text or ""):
                    html = resp.text
                    final_url = u
                    break
                if resp.status_code == 403:
                    raise PermissionError(f"HTTP 403 at {u}")
                last_exc_msg = f"HTTP {resp.status_code} at {u}: {resp.text[:120]}"
            except PermissionError:
                raise
            except Exception as e:
                last_exc_msg = f"{type(e).__name__}: {e} at {u}"

        if html is None:
            raise RuntimeError(f"无法抓取分类页: {last_exc_msg}")

        # 使用内置解析器，避免容器内安装 lxml 的负担
        soup = BeautifulSoup(html, "html.parser")
        threads = []

        # 粗略选择器：寻找形如 /t/12345 或 /post-12345-1 的帖子链接
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href:
                continue
            # 规范化为绝对 URL
            full = href if href.startswith("http") else f"{self.BASE}{href if href.startswith('/') else '/' + href}"
            # 过滤出帖子链接
            m_t = re.search(r"/t/(\d+)", href)
            m_p = re.search(r"/post-(\d+)(?:-[0-9]+)?", href)
            thread_id = None
            if m_t:
                thread_id = int(m_t.group(1))
            elif m_p:
                thread_id = int(m_p.group(1))
            if thread_id:
                title = a.get_text(strip=True)
                if title:
                    threads.append({"title": title, "url": full, "thread_id": thread_id})

        # 去重，保持顺序
        seen = set()
        uniq = []
        for t in threads:
            if t["thread_id"] in seen:
                continue
            seen.add(t["thread_id"])
            uniq.append(t)
        return uniq

    def get_thread_context(self, thread_url: str, sample_count: int = 6) -> Dict:
        """
        抓取帖子页上下文：标题、楼主摘要、其他用户近期评论；并检测自己是否已评论。
        返回: {title, op_summary, comments: [str], csrf, turnstile, has_commented, thread_id}
        """
        import os as _os
        ref = _os.getenv("NS_REFERER", self.BASE)
        resp = self._request("GET", thread_url, headers=self._headers(referer=ref))
        if resp.status_code == 403:
            raise PermissionError(f"HTTP 403 at {thread_url}")
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.get_text(strip=True) if soup.title else ""

        # 解析帖子ID
        thread_id = None
        m_p = re.search(r"/post-(\d+)", thread_url)
        m_t = re.search(r"/t/(\d+)", thread_url)
        if m_p:
            thread_id = int(m_p.group(1))
        elif m_t:
            thread_id = int(m_t.group(1))

        # 提取楼主内容（优先 NodeSeek 常见结构）
        op_summary = ""
        main_post_container = soup.find('div', class_='nsk-post')
        if main_post_container:
            content_article = main_post_container.find('article', class_='post-content')
            if content_article:
                op_summary = content_article.get_text(separator=' ', strip=True)
        if not op_summary:
            candidates = [
                ("div", {"class": re.compile(r"post|content|markdown", re.I)}),
                ("article", {}),
            ]
            for tag, kw in candidates:
                el = soup.find(tag, kw)
                if el:
                    op_summary = el.get_text(" ", strip=True)
                    if op_summary:
                        break

        # 获取已登录用户ID（从首页配置脚本中解析）
        if self.logged_in_user_id is None:
            try:
                r = self._request("GET", f"{self.BASE}/", headers=self._headers())
                if r.status_code == 200 and r.text:
                    s = BeautifulSoup(r.text, "html.parser")
                    config_script = s.find('script', id='temp-script')
                    if config_script and config_script.string:
                        try:
                            json_text = base64.b64decode(config_script.string).decode('utf-8')
                            config_data = json.loads(json_text)
                            uid = config_data.get('user', {}).get('member_id')
                            if uid:
                                self.logged_in_user_id = str(uid)
                        except Exception:
                            pass
            except Exception:
                pass

        # 收集其他用户的评论，检测是否已评论
        comments: List[str] = []
        has_commented = False
        try:
            items = soup.select('.comment-container .content-item')
            for item in items:
                author_link = item.find('a', class_='author-name')
                if not author_link:
                    continue
                href = author_link.get('href', '')
                is_self = False
                if self.logged_in_user_id and self.logged_in_user_id in href:
                    is_self = True
                if is_self:
                    has_commented = True
                    continue
                comment_article = item.find('article', class_='post-content')
                if comment_article:
                    txt = comment_article.get_text(strip=True)
                    if txt and len(txt) >= 5:
                        comments.append(txt)
                if len(comments) >= sample_count:
                    break
        except Exception:
            # 回退：宽松选择器
            for el in soup.find_all(["div", "li", "article"], {"class": re.compile(r"comment|reply|post", re.I)}):
                txt = el.get_text(" ", strip=True)
                if txt and len(txt) >= 10:
                    comments.append(txt)
                if len(comments) >= sample_count:
                    break

        # 尝试解析 CSRF/表单隐藏字段（占位）
        csrf = None
        meta_csrf = soup.find("meta", {"name": re.compile(r"csrf", re.I)})
        if meta_csrf and meta_csrf.get("content"):
            csrf = meta_csrf.get("content")
        else:
            hidden = soup.find("input", {"name": re.compile(r"csrf|token", re.I)})
            if hidden and hidden.get("value"):
                csrf = hidden.get("value")

        # Turnstile 信息占位（若回复也需要验证码，这里需要从页面脚本中解析）
        turnstile = None

        return {
            "title": title,
            "op_summary": op_summary,
            "comments": comments,
            "csrf": csrf,
            "turnstile": turnstile,
            "has_commented": has_commented,
            "thread_id": thread_id,
        }

    def post_reply(self, thread_url: str, content: str, csrf: Optional[str] = None, turnstile_token: Optional[str] = None) -> Tuple[bool, str]:
        """
        发布回复（试探多种常用 API 端点；可通过环境变量 NS_COMMENT_REPLY_ENDPOINT 覆盖）。
        返回: (ok, message)
        注意：实际线上字段以抓包为准，如失败请提供抓包信息以便调整。
        """
        import os

        m_p = re.search(r"/post-(\d+)", thread_url)
        m_t = re.search(r"/t/(\d+)", thread_url)
        if m_p:
            thread_id = int(m_p.group(1))
        elif m_t:
            thread_id = int(m_t.group(1))
        else:
            return False, "无法从URL解析帖子ID"

        override = os.getenv("NS_COMMENT_REPLY_ENDPOINT", "").strip()

        def generate_csrf_token(length: int = 16) -> str:
            import random as _random
            import string as _string
            character_pool = _string.ascii_letters + _string.digits
            return "".join(_random.choice(character_pool) for _ in range(length))

        override_csrf = os.getenv("NS_COMMENT_STATIC_CSRF", "").strip()
        csrf_token = ""
        if override_csrf:
            csrf_token = override_csrf
        elif isinstance(csrf, str) and csrf.strip():
            csrf_token = csrf.strip()
        else:
            # NodeSeek ??? scsrf-token ?????????????????????
            csrf_token = generate_csrf_token(16)

        payload_base = {
            "content": content,
            "mode": "new-comment",
            "postId": thread_id,
        }
        if turnstile_token:
            payload_base.update({"token": turnstile_token, "source": "turnstile"})

        attempts: List[Tuple[str, Dict[str, object]]] = []
        if override:
            url = override
            if not url.startswith("http"):
                if not url.startswith("/"):
                    url = "/" + url
                url = f"{self.BASE}{url}"
            url = url.replace("{id}", str(thread_id))
            payload = dict(payload_base)
            payload.setdefault("threadId", thread_id)
            payload.setdefault("topicId", thread_id)
            attempts.append((url, payload))
        else:
            attempts.append((f"{self.BASE}/api/content/new-comment", dict(payload_base)))
            fallback_endpoints = [
                (f"{self.BASE}/api/topic/reply", ("topicId",)),
                (f"{self.BASE}/api/thread/reply", ("threadId",)),
                (f"{self.BASE}/api/post/create", ("threadId",)),
                (f"{self.BASE}/api/post", ("threadId",)),
                (f"{self.BASE}/api/comment", ("threadId",)),
            ]
            for url, extra_keys in fallback_endpoints:
                payload = dict(payload_base)
                for key in extra_keys:
                    payload[key] = thread_id
                attempts.append((url, payload))

        referer = thread_url if thread_url.startswith("http") else f"{self.BASE}/post-{thread_id}-1"
        headers = self._headers_for_api(referer=referer, csrf_token=csrf_token)

        last_err = None
        for url, payload in attempts:
            try:
                resp = self._request("POST", url, headers=headers, json=payload)
                try:
                    data = resp.json()
                except Exception:
                    data = {"status_code": resp.status_code, "text": resp.text[:300]}

                if resp.status_code in (200, 201):
                    if isinstance(data, dict) and (data.get("success") or data.get("ok") or data.get("status") in ("ok", 0, 200, "success")):
                        return True, str(data.get("message") or "发布成功")
                    if isinstance(data, dict) and not data.get("error"):
                        return True, str(data.get("message") or "发布成功(未显式success)")

                if resp.status_code in (401, 403, 429):
                    last_err = f"HTTP {resp.status_code}: {data}"
                    return False, last_err

                last_err = f"HTTP {resp.status_code}: {data}"
            except Exception as e:
                last_err = str(e)

        return False, (last_err or "未知错误")

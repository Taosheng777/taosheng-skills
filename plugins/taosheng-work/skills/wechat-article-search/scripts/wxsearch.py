#!/usr/bin/env python3
"""wxsearch — 搜索微信公众号文章并抓取全文为 Markdown。

本地链路仅用 Python 标准库；本地 IP 被限流时可自动调用已登录的 Firecrawl CLI。

主链路：搜狗微信首页(建会话) → 搜索列表页 → 跳转链解析出真实微信 URL → 抓正文
备用链路：普通搜狗网页索引 → Firecrawl 远端抓搜索页/微信正文
直读链接：本地直连 → 被拦时 Firecrawl（解析其原始 HTML，与直连同一套）
关键：必须维持完整 cookie 会话（ABTEST/SUID/SUV）并逐级设置 Referer，
     否则搜狗会以 antispider 页面拦截跳转链。详见 README。
"""
from __future__ import annotations

import argparse
import gzip
import html as _html
import http.cookiejar
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timedelta

__version__ = "1.3.0"

HOME = "https://weixin.sogou.com/"
SEARCH = "https://weixin.sogou.com/weixin"
WEB_HOME = "https://www.sogou.com/"
WEB_SEARCH = "https://www.sogou.com/web"

UAS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


class Blocked(Exception):
    """搜狗反爬拦截。"""


# 拦截页特征。正常列表页不含这些（实测对比 36533 字节正常页 vs 5402 字节拦截页）。
_BLOCK_MARKERS = ("antispider", "请输入验证码", "newstatic/css/verify.css")
_RESULT_ITEM = re.compile(r"sogou_vr_\d+_box_\d+")


def looks_blocked(text: str) -> bool:
    """判断是否为反爬拦截页。

    组合判据而非单纯字符串匹配：命中特征 **且** 页面里没有任何结果条目。
    多这一层是为了防止搜狗日后在正常页面也引入 antispider 资源时全面误判。
    """
    if not any(m in text for m in _BLOCK_MARKERS):
        return False
    return not _RESULT_ITEM.search(text)


class Session:
    """带 cookie 的会话。先落地首页建立 cookie，是整条链路能通的前提。"""

    def __init__(self, delay=(1.0, 2.2), timeout=30, verbose=False):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.ua = random.choice(UAS)
        self.delay = delay
        self.timeout = timeout
        self.verbose = verbose
        self._last = 0.0
        self._warm = False

    def _wait(self):
        gap = time.time() - self._last
        need = random.uniform(*self.delay)
        if gap < need:
            time.sleep(need - gap)
        self._last = time.time()

    def get(self, url, referer=None):
        self._wait()
        headers = [
            ("User-Agent", self.ua),
            ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
            ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
            ("Accept-Encoding", "gzip, deflate"),
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
        ]
        if referer:
            headers.append(("Referer", referer))
        self.op.addheaders = headers
        with self.op.open(url, timeout=self.timeout) as r:
            raw = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
        if enc == "gzip":
            raw = gzip.decompress(raw)
        elif enc == "deflate":
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        text = raw.decode("utf-8", "ignore")
        if looks_blocked(text):
            raise Blocked(
                "本地搜狗反爬拦截（这是限流，不是工具故障）。\n"
                "  跑 `wxsearch --doctor` 可确认工具本身是否正常。\n"
                "  `auto` 会继续尝试普通搜狗与 Firecrawl；`direct` 模式需等待或换网络。")
        return text

    def warmup(self):
        """访问首页拿 ABTEST/SUID，并确保存在 SUV。缺这步跳转链必被拦。"""
        if self._warm:
            return
        try:
            self.get(HOME)
        except Blocked:
            raise
        except Exception:
            pass  # 首页取不到不致命，只要 SUV 在
        if not any(c.name == "SUV" for c in self.cj):
            self.cj.set_cookie(http.cookiejar.Cookie(
                0, "SUV", os.urandom(16).hex().upper(), None, False,
                ".sogou.com", True, False, "/", True, False, None, False, None, None, {}))
        self._warm = True
        if self.verbose:
            print(f"  [session] cookies: {[c.name for c in self.cj]}", file=sys.stderr)


# ---------- 解析 ----------

def _txt(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return _html.unescape(re.sub(r"\s+", " ", s)).strip()


def search(sess: Session, query: str, page=1, days=None, kind="article"):
    """搜索，返回结果列表（含 sogou_link，尚未解析出真实微信 URL）。"""
    sess.warmup()
    params = {"type": "2" if kind == "article" else "1", "query": query, "page": str(page)}
    if days:
        et = int(time.time())
        params.update({"ft": str(et - days * 86400), "et": str(et), "tsn": "5", "interation": ""})
    url = SEARCH + "?" + urllib.parse.urlencode(params)
    page_html = sess.get(url, referer=HOME)
    out = []

    if kind == "gzh":
        for blk in re.findall(r'<div[^>]*class="gzh-box[^"]*"[^>]*>(.*?)<div class="s-p"', page_html, re.S):
            name = re.search(r'<p[^>]*class="tit"[^>]*>.*?<a[^>]*>(.*?)</a>', blk, re.S)
            wxid = re.search(r"<label[^>]*>微信号[:：]\s*([^<]+)</label>", blk)
            if name:
                out.append({"nickname": _txt(name.group(1)),
                            "wechat_id": wxid.group(1).strip() if wxid else ""})
        return out, url

    for li in re.findall(r'<li[^>]*id="sogou_vr_\d+_box_\d+"[^>]*>(.*?)</li>', page_html, re.S):
        a = re.search(r'href="(/link\?url=[^"]+)"', li)
        t = re.search(r"<h3>\s*<a[^>]*>(.*?)</a>\s*</h3>", li, re.S)
        if not (a and t):
            continue
        d = re.search(r'<p[^>]*class="txt-info"[^>]*>(.*?)</p>', li, re.S)
        acc = re.search(r'<span[^>]*class="all-time-y2"[^>]*>([^<]+)</span>', li)
        ts = re.search(r"timeConvert\('(\d+)'\)", li)
        link = _html.unescape(a.group(1)).replace(" ", "%20")
        out.append({
            "title": _txt(t.group(1)),
            "account": acc.group(1).strip() if acc else "",
            "digest": _txt(d.group(1))[:200] if d else "",
            "time": datetime.fromtimestamp(int(ts.group(1))).strftime("%Y-%m-%d %H:%M") if ts else "",
            "sogou_link": urllib.parse.urljoin(HOME, link),
            "provider": "sogou-weixin",
        })
    return out, url


def _sogou_web_url(query: str, page=1) -> str:
    params = {"query": f"site:mp.weixin.qq.com/s {query}"}
    if page > 1:
        params["page"] = str(page)
    return WEB_SEARCH + "?" + urllib.parse.urlencode(params)


def _clean_url(url: str) -> str:
    # html.unescape 会把合法参数名 `&timestamp` 误判成实体 `&times`，变成 `×tamp`。
    return url.replace("&amp;", "&").strip()


def parse_sogou_web(page_html: str) -> list[dict]:
    """从普通搜狗网页结果中保留直达 mp.weixin.qq.com 的条目。"""
    headings = list(re.finditer(
        r'<h3\b[^>]*>\s*<a\b[^>]*href=["\'](https?://mp\.weixin\.qq\.com/s\?[^"\']+)["\'][^>]*>'
        r'(.*?)</a>\s*</h3>', page_html, re.S | re.I))
    out = []
    seen = set()
    for i, match in enumerate(headings):
        wx_url = _clean_url(match.group(1))
        if wx_url in seen:
            continue
        seen.add(wx_url)
        end = headings[i + 1].start() if i + 1 < len(headings) else min(len(page_html), match.end() + 3000)
        tail = page_html[match.end():end]
        digest_match = re.search(r"<p\b[^>]*>(.*?)</p>", tail, re.S | re.I)
        time_match = re.search(r"(20\d{2}[-年]\d{1,2}[-月]\d{1,2}(?:日)?(?:\s+\d{1,2}:\d{2})?)", tail)
        out.append({
            "title": _txt(match.group(2)),
            "account": "",
            "digest": _txt(digest_match.group(1))[:200] if digest_match else "",
            "time": time_match.group(1) if time_match else "",
            "wx_url": wx_url,
            "sogou_link": wx_url,
            "provider": "sogou-web",
        })
    return out


def search_web(sess: Session, query: str, page=1):
    """用普通搜狗网页索引找直达微信公众号链接。"""
    url = _sogou_web_url(query, page)
    page_html = sess.get(url, referer=WEB_HOME)
    return parse_sogou_web(page_html), url


def _markdown_plain(text: str) -> str:
    text = re.sub(r"!\[[^]]*]\([^)]*\)", "", text)
    text = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", text)
    text = text.replace("\\", "")
    return re.sub(r"[*_`]+", "", text).strip()


def parse_firecrawl_search(markdown: str) -> list[dict]:
    """解析 Firecrawl 抓取的普通搜狗 Markdown，只保留直达微信结果。"""
    pattern = re.compile(
        r"^[ \t]*#{2,4}\s+\[([^\]]+)]\((https?://mp\.weixin\.qq\.com/s\?[^)\s]+)\)[ \t]*$",
        re.M | re.I)
    matches = list(pattern.finditer(markdown))
    out = []
    seen = set()
    for i, match in enumerate(matches):
        wx_url = _clean_url(match.group(2))
        if wx_url in seen:
            continue
        seen.add(wx_url)
        end = matches[i + 1].start() if i + 1 < len(matches) else min(len(markdown), match.end() + 2500)
        tail = markdown[match.end():end]
        paragraphs = [
            _markdown_plain(p) for p in re.split(r"\n\s*\n", tail)
            if _markdown_plain(p)
            and "mp.weixin.qq.com" not in p
            and not p.lstrip().startswith(("推荐您搜索", "大家还在搜"))
        ]
        digest = paragraphs[0][:200] if paragraphs else ""
        time_match = re.search(r"(20\d{2}-\d{1,2}-\d{1,2}|\d+天前|\d+小时前)", tail)
        out.append({
            "title": _markdown_plain(match.group(1)),
            "account": "",
            "digest": digest,
            "time": time_match.group(1) if time_match else "",
            "wx_url": wx_url,
            "sogou_link": wx_url,
            "provider": "firecrawl-sogou-web",
        })
    return out


def _firecrawl_scrape(url: str, only_main=False, document=False, raw_html=False):
    exe = shutil.which("firecrawl")
    if not exe:
        raise RuntimeError("未找到 Firecrawl CLI；可安装并登录后重试，或使用 --backend direct")
    with tempfile.TemporaryDirectory(prefix="wxsearch-") as tmpdir:
        out = os.path.join(tmpdir, "result.json")
        cmd = [exe, "scrape", url]
        if only_main:
            cmd.append("--only-main-content")
        if raw_html:
            cmd.extend(["--format", "markdown,rawHtml"])
        else:
            cmd.append("--json")
        cmd.extend(["-o", out])
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("Firecrawl 抓取超时") from e
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            raise RuntimeError("Firecrawl 抓取失败" + (f"：{detail[-1]}" if detail else ""))
        if not os.path.exists(out):
            raise RuntimeError("Firecrawl 未生成抓取结果")
        with open(out, encoding="utf-8") as f:
            raw = f.read()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"markdown": raw, "metadata": {}}
        if isinstance(payload.get("data"), dict) and "markdown" not in payload:
            payload = payload["data"]
        if document:
            return payload
        return payload.get("markdown", "")


def search_firecrawl(query: str, page=1):
    """用 Firecrawl 的远端出口抓普通搜狗索引。"""
    url = _sogou_web_url(query, page)
    markdown = _firecrawl_scrape(url)
    if any(marker in markdown for marker in _BLOCK_MARKERS) and not parse_firecrawl_search(markdown):
        raise Blocked("Firecrawl 远端出口也被搜狗限流")
    return parse_firecrawl_search(markdown), url


def search_auto(sess: Session, query: str, page=1, days=None, kind="article", backend="auto"):
    """按专用搜狗 → 普通搜狗 → Firecrawl 的顺序检索。"""
    if kind == "gzh":
        if backend == "firecrawl":
            raise ValueError("Firecrawl 备用通道暂不支持 --type gzh")
        return search(sess, query, page, days, kind)
    if backend == "direct":
        return search(sess, query, page, days, kind)
    if backend == "firecrawl":
        return search_firecrawl(query, page)

    failures = []
    empty_ref = None
    try:
        results, ref = search(sess, query, page, days, kind)
        if results:
            return results, ref
        empty_ref = ref
        failures.append("专用搜狗无结果")
    except Exception as e:
        failures.append(f"专用搜狗：{e}")

    try:
        results, ref = search_web(sess, query, page)
        if results:
            return results, ref
        empty_ref = ref
        failures.append("普通搜狗无直达微信结果")
    except Exception as e:
        failures.append(f"普通搜狗：{e}")

    try:
        results, ref = search_firecrawl(query, page)
        if results:
            return results, ref
        empty_ref = ref
        failures.append("Firecrawl 无直达微信结果")
    except Exception as e:
        failures.append(f"Firecrawl：{e}")
    if empty_ref:
        return [], empty_ref
    raise Blocked("三条微信公众号检索链路均未成功：\n  " + "\n  ".join(failures))


def resolve(sess: Session, sogou_link: str, referer: str) -> str | None:
    """跳转链 → 真实 mp.weixin.qq.com URL。

    搜狗把 URL 拆成多段 JS 字符串拼接，并插入 '@' 作混淆，需剔除。
    """
    page = sess.get(sogou_link, referer=referer)
    parts = re.findall(r"url \+= '([^']+)'", page)
    if parts:
        return "".join(parts).replace("@", "")
    m = re.search(r"""var\s+url\s*=\s*["']([^"']+)["']""", page)
    return m.group(1).replace("@", "") if m else None


def resolve_auto(sess: Session, result: dict, referer: str, backend="auto") -> str | None:
    if result.get("wx_url"):
        return result["wx_url"]
    try:
        wx_url = resolve(sess, result["sogou_link"], referer)
        if wx_url or backend != "auto":
            return wx_url
    except Exception:
        if backend != "auto":
            raise
    candidates, _ = search_firecrawl(f'"{result["title"]}"', 1)
    return candidates[0]["wx_url"] if candidates else None


# ---------- 正文 → Markdown ----------

_BLOCK = re.compile(r"</(p|section|div|h[1-6]|li|tr|blockquote)>", re.I)
_VIDEO_PLAYER = re.compile(r'<(\w+)\b[^>]*\bclass="[^"]*\bvideo_iframe\b[^"]*"[^>]*>', re.I)


def _drop_video_players(s: str) -> str:
    """整块去掉文中视频。

    浏览器渲染后（Firecrawl 抓到的就是渲染结果）播放器控件会展开在正文容器里，
    按同名标签配对找到结束位置；配不上时只去开标签，宁可留控件文字也不截掉后文。
    """
    out, pos = [], 0
    while m := _VIDEO_PLAYER.search(s, pos):
        out.append(s[pos:m.start()])
        pos, depth = m.end(), 1
        for t in re.compile(rf"<(/?){m.group(1)}\b[^>]*>", re.I).finditer(s, m.end()):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                pos = t.end()
                break
    out.append(s[pos:])
    return "".join(out)


def to_markdown(fragment: str) -> str:
    s = _drop_video_players(fragment)
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", s, flags=re.S | re.I)
    # 微信图片走 data-src 懒加载
    s = re.sub(r'<img[^>]*?data-src="([^"]+)"[^>]*>', r"\n![](\1)\n", s, flags=re.I)
    s = re.sub(r'<img[^>]*?src="([^"]+)"[^>]*>', r"\n![](\1)\n", s, flags=re.I)
    for lvl in range(1, 7):
        s = re.sub(rf"<h{lvl}[^>]*>(.*?)</h{lvl}>", lambda m, l=lvl: f"\n{'#' * l} {_txt(m.group(1))}\n",
                   s, flags=re.S | re.I)
    s = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", lambda m: f"**{_txt(m.group(2))}**", s, flags=re.S | re.I)
    s = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", lambda m: f"*{_txt(m.group(2))}*", s, flags=re.S | re.I)
    s = re.sub(r'<a[^>]*?href="([^"]+)"[^>]*>(.*?)</a>',
               lambda m: f"[{_txt(m.group(2))}]({m.group(1)})", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = _BLOCK.sub("\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t ]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return "\n".join(l.rstrip() for l in s.splitlines()).strip()


def fetch_article(sess: Session, wx_url: str, referer=HOME) -> dict:
    return parse_article_html(sess.get(wx_url, referer=referer), wx_url)


def parse_article_html(page: str, wx_url: str) -> dict:
    """解析微信文章 HTML；本地直连的原始页与 Firecrawl 的渲染页共用。"""
    if "该内容已被发布者删除" in page:
        return {"error": "deleted", "wx_url": wx_url}
    if "环境异常" in page or "wappoc_appmsgcaptcha" in page:
        return {"error": "captcha", "wx_url": wx_url}

    def pick(*pats):
        for p in pats:
            m = re.search(p, page, re.S)
            if m:
                return _txt(m.group(1))
        return ""

    body = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*(?:<script|<div\s+id="js_)', page, re.S)
    if not body:
        body = re.search(r'<div[^>]*id="js_content"[^>]*>(.*)', page, re.S)
    # 时间戳优先：渲染页的 publish_time 是英文界面文本，且按渲染端时区显示
    ct = re.search(r'var\s+ct\s*=\s*"(\d+)"', page)
    if ct:
        publish_time = datetime.fromtimestamp(int(ct.group(1))).strftime("%Y-%m-%d %H:%M")
    else:
        publish_time = pick(r'<em[^>]*id="publish_time"[^>]*>(.*?)</em>')
    article = {
        "wx_url": wx_url,
        "title": pick(r'<h1[^>]*class="rich_media_title"[^>]*>(.*?)</h1>',
                      r'<h1[^>]*id="activity-name"[^>]*>(.*?)</h1>', r"<title>([^<]+)</title>"),
        "account": pick(r'<a[^>]*id="js_name"[^>]*>(.*?)</a>',
                        r'<strong[^>]*class="profile_nickname"[^>]*>(.*?)</strong>'),
        "publish_time": publish_time,
        "content": to_markdown(body.group(1)) if body else "",
    }
    if not article["content"]:
        article["error"] = "parse-failed"
    return article


_CN_DATE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日(?:\s+(\d{1,2}):(\d{2}))?")
# Firecrawl 远端拿到的是英文界面，如 `_Sep 17, 2026, 8:08 PM_`
_EN_DATE = re.compile(
    r"(?<![A-Za-z])(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),\s*(20\d{2})"
    r"(?:,?\s+(\d{1,2}):(\d{2})\s*([AP]M))?", re.I)
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def _header_date(line: str) -> str:
    """页头日期 → YYYY-MM-DD[ HH:MM]。英文界面按渲染端时区显示，有时间戳时会被覆盖。"""
    m = _CN_DATE.search(line)
    if m:
        year, month, day, hour, minute = m.groups()
    else:
        m = _EN_DATE.search(line)
        if not m:
            return ""
        mon, day, year, hour, minute, noon = m.groups()
        month = _MONTHS.index(mon[:3].lower()) + 1
        if hour is not None:
            hour = int(hour) % 12 + (12 if noon.upper() == "PM" else 0)
    out = f"{year}-{int(month):02d}-{int(day):02d}"
    if hour is not None:
        out += f" {int(hour):02d}:{minute}"
    return out


def parse_firecrawl_article(markdown: str, wx_url: str) -> dict:
    """从 Firecrawl 的微信文章 Markdown 中提取出处和正文。"""
    if "环境异常" in markdown or "wappoc_appmsgcaptcha" in markdown:
        return {"error": "captcha", "wx_url": wx_url, "provider": "firecrawl"}
    if "该内容已被发布者删除" in markdown:
        return {"error": "deleted", "wx_url": wx_url, "provider": "firecrawl"}

    lines = [line.rstrip() for line in markdown.splitlines()]
    title = ""
    title_index = -1
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("# "):
            title = _markdown_plain(stripped[2:])
            title_index = i
            break

    # 日期只在标题下方的页头里找：页尾的「修改于2026年9月18日」不能当正文起点
    date_index = -1
    publish_time = ""
    for i in range(title_index + 1, min(len(lines), title_index + 13)):
        publish_time = _header_date(lines[i])
        if publish_time:
            date_index = i
            break
    if not publish_time:
        relative = re.search(r"\b(Yesterday|Today)\s+(\d{1,2}):(\d{2})", markdown, re.I)
        if relative:
            when = datetime.now() - timedelta(days=1 if relative.group(1).lower() == "yesterday" else 0)
            publish_time = when.replace(
                hour=int(relative.group(2)), minute=int(relative.group(3))).strftime("%Y-%m-%d %H:%M")

    account = ""
    if date_index >= 0:
        for line in reversed(lines[max(title_index + 1, 0):date_index]):
            candidate = _markdown_plain(line)
            if not candidate or candidate.startswith(("Original", "原创")):
                continue
            if candidate.startswith("![") or candidate == title:
                continue
            account = candidate
            break

    start = date_index + 1 if date_index >= 0 else title_index + 1
    body_lines = lines[max(start, 0):]
    while body_lines:
        plain = _markdown_plain(body_lines[0])
        if (not plain or plain.startswith(("在小说阅读器", "去阅读", "在小说阅读器中"))
                or body_lines[0].lstrip().startswith("![")):
            body_lines.pop(0)
            continue
        break
    end_markers = ("**点击分享此文章**", "预览时标签不可点", "Like the Author")
    end = next((i for i, line in enumerate(body_lines) if any(m in line for m in end_markers)), None)
    if end is None:
        # 「Close」也是文中视频播放器的按钮，只在没有可靠结束标记时兜底
        end = next((i for i, line in enumerate(body_lines) if line.strip() == "Close"), None)
    body_lines = body_lines[:end]
    content = "\n".join(body_lines).strip()
    content = re.sub(r"\n{3,}", "\n\n", content)
    if not title or not content:
        return {"error": "parse-failed", "wx_url": wx_url, "provider": "firecrawl"}
    return {
        "wx_url": wx_url,
        "title": title,
        "account": account,
        "publish_time": publish_time,
        "content": content,
        "provider": "firecrawl",
    }


def parse_firecrawl_raw_metadata(raw_html: str) -> dict:
    """从微信原始 HTML 的 appmsg 数据中提取公众号和发布时间。"""
    account = ""
    for field in ("nick_name", "nickname"):
        account_match = re.search(
            rf"(?<![\w-]){field}\s*[:=]\s*(['\"])(.*?)\1",
            raw_html, re.S)
        if account_match:
            account = _html.unescape(account_match.group(2)).strip()
            break
    if not account:
        account_match = re.search(
            r'<(?:a|strong)[^>]*(?:id=["\']js_name["\']|class=["\'][^"\']*profile_nickname[^"\']*["\'])'
            r'[^>]*>(.*?)</(?:a|strong)>', raw_html, re.S | re.I)
        if account_match:
            account = _txt(account_match.group(1))

    publish_time = ""
    time_match = re.search(
        r"(?<![\w-])(?:create_time|publish_time|oriCreateTime)\s*[:=]\s*(['\"])(20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2})(?::\d{2})?\1",
        raw_html)
    if time_match:
        publish_time = time_match.group(2)
    if not publish_time:
        epoch_match = re.search(
            r"(?<![\w-])(?:ori_create_time|create_time|ct)\s*[:=]\s*['\"]?(\d{10})",
            raw_html)
        if epoch_match:
            publish_time = datetime.fromtimestamp(
                int(epoch_match.group(1))).strftime("%Y-%m-%d %H:%M")
    return {"account": account, "publish_time": publish_time}


def fetch_article_firecrawl(wx_url: str) -> dict:
    document = _firecrawl_scrape(
        wx_url, only_main=True, document=True, raw_html=True)
    # 原始 HTML 带正文容器时与本地直连同一套解析；英文界面渲染出的 Markdown 只作后备
    raw_html = document.get("rawHtml", "")
    article = parse_article_html(raw_html, wx_url) if 'id="js_content"' in raw_html else {}
    if article.get("content"):
        article["provider"] = "firecrawl"
    else:
        article = parse_firecrawl_article(document.get("markdown", ""), wx_url)
    metadata = document.get("metadata") or {}
    raw_metadata = parse_firecrawl_raw_metadata(raw_html)
    metadata_account = next((
        str(metadata[key]).strip()
        for key in ("author", "og:article:author", "twitter:creator")
        if metadata.get(key)), "")
    article["account"] = raw_metadata["account"] or article.get("account") or metadata_account
    article["publish_time"] = raw_metadata["publish_time"] or article.get("publish_time", "")
    return article


def _fetch_firecrawl_with_refresh(wx_url: str, title: str | None = None) -> dict:
    article = fetch_article_firecrawl(wx_url)
    if article.get("error") != "parse-failed" or not title:
        return article
    candidates, _ = search_firecrawl(f'"{title}"', 1)
    for candidate in candidates:
        fresh_url = candidate["wx_url"]
        if fresh_url == wx_url:
            continue
        refreshed = fetch_article_firecrawl(fresh_url)
        if not refreshed.get("error"):
            return refreshed
    return article


def fetch_article_auto(
        sess: Session, wx_url: str, referer=HOME, backend="auto", title: str | None = None) -> dict:
    """本地抓正文；仅在被拦或网络失败时切到 Firecrawl。"""
    if backend == "firecrawl":
        return _fetch_firecrawl_with_refresh(wx_url, title)
    if backend == "direct":
        return fetch_article(sess, wx_url, referer=referer)

    direct_error = None
    try:
        article = fetch_article(sess, wx_url, referer=referer)
        if article.get("error") == "deleted" or article.get("content"):
            return article
        direct_error = article
    except Exception as e:
        direct_error = e
    try:
        return _fetch_firecrawl_with_refresh(wx_url, title)
    except Exception as e:
        if isinstance(direct_error, dict):
            direct_error["fallback_error"] = str(e)
            return direct_error
        raise RuntimeError(f"本地与 Firecrawl 正文通道均失败：{direct_error}；{e}") from e


# ---------- 自检 ----------

# 最小样本：结构取自真实列表页，用于离线验证解析逻辑未被搜狗改版打坏。
_FIXTURE_OK = '''<li id="sogou_vr_11002601_box_0"><div class="txt-box">
<h3><a href="/link?url=ABC123&amp;type=2">测试<em>标题</em></a></h3>
<p class="txt-info">这是摘要内容</p>
<div class="s-p" t="1698291020"><span class="all-time-y2">测试公众号</span>
<script>document.write(timeConvert('1698291020'))</script></div></div></li>'''

_FIXTURE_BLOCKED = ('<html><head><link rel="stylesheet" href="static/css/anti.min.css"/>'
                    '<script src="static/js/antispider.min.js?v=3"></script></head>'
                    '<body>请输入验证码</body></html>')


def doctor(verbose=False) -> int:
    """自检：区分「工具故障」与「IP 被限流」。"""
    print(f"wxsearch {__version__} 自检\n")
    ok_offline = True

    print(f"[1/4] Python 环境        ✓ {sys.version.split()[0]}（仅标准库）")

    # 离线解析自测：不碰网络，证明解析逻辑本身完好
    try:
        items = re.findall(r'<li[^>]*id="sogou_vr_\d+_box_\d+"[^>]*>(.*?)</li>', _FIXTURE_OK, re.S)
        title = _txt(re.search(r"<h3>\s*<a[^>]*>(.*?)</a>\s*</h3>", items[0], re.S).group(1))
        acct = re.search(r'<span[^>]*class="all-time-y2"[^>]*>([^<]+)</span>', items[0]).group(1)
        md = to_markdown("<p>段落</p><strong>粗体</strong>")
        assert title == "测试标题" and acct == "测试公众号", (title, acct)
        assert "**粗体**" in md, md
        assert looks_blocked(_FIXTURE_BLOCKED) is True
        assert looks_blocked(_FIXTURE_OK) is False
        print("[2/4] 解析逻辑（离线）   ✓ 列表解析 / 正文转换 / 拦截判别 均正常")
    except Exception as e:
        ok_offline = False
        print(f"[2/4] 解析逻辑（离线）   ✗ {type(e).__name__}: {e}")

    sess = Session(delay=(0.5, 1.0), verbose=verbose)
    home_ok = False
    try:
        home = sess.get(HOME)
        home_ok = True
        print(f"[3/4] 搜狗首页可达      ✓ {len(home)} 字节")
    except Blocked:
        print("[3/4] 搜狗首页可达      ✗ 首页即被拦截")
    except Exception as e:
        print(f"[3/4] 搜狗首页可达      ✗ {type(e).__name__}: {e}")

    search_ok = False
    blocked = False
    try:
        sess._warm = True  # 首页已在上一步访问过
        if not any(c.name == "SUV" for c in sess.cj):
            sess.cj.set_cookie(http.cookiejar.Cookie(
                0, "SUV", os.urandom(16).hex().upper(), None, False, ".sogou.com",
                True, False, "/", True, False, None, False, None, None, {}))
        res, _ = search(sess, "健康", 1, None, "article")
        search_ok = bool(res)
        print(f"[4/4] 搜索链路          {'✓' if search_ok else '✗'} 返回 {len(res)} 条")
    except Blocked:
        blocked = True
        print("[4/4] 搜索链路          ✗ 被反爬拦截")
    except Exception as e:
        print(f"[4/4] 搜索链路          ✗ {type(e).__name__}: {e}")

    print()
    if not ok_offline:
        print("诊断：工具自身异常（解析逻辑失效，可能是搜狗改版）。请提 issue。")
        return 1
    if search_ok:
        print("诊断：一切正常，可以直接使用。")
        return 0
    if blocked and home_ok:
        print("诊断：工具正常，当前 IP 的搜狗专用链路被限流。")
        print("      短时间大量请求会触发，恢复可能需要数小时。")
        print("      --doctor 只测本地；正常 auto 命令仍会尝试备用通道。")
        return 2
    print("诊断：网络不可达，或搜狗服务异常。先检查网络与代理设置。")
    return 1


def _slug(name: str, fallback: str) -> str:
    s = re.sub(r'[/\\:*?"<>|\n\r\t]', "_", name).strip()[:60]
    return s or fallback


def _save_article(outdir: str, r: dict, content: str, fallback: str) -> str:
    """写出带出处头的 Markdown，返回文件路径。"""
    fp = os.path.join(outdir, _slug(r["title"], fallback) + ".md")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(f"# {r['title']}\n\n")
        f.write(f"> 公众号：{r['account']}　发布：{r['time']}\n>\n> 原文：{r['wx_url']}\n\n---\n\n")
        f.write(content)
    return fp


_ARTICLE_URL = re.compile(r"https?://mp\.weixin\.qq\.com/s\b", re.I)


def read_url(sess: Session, url: str, args, log) -> int:
    """直接读一篇文章链接：先本地直连，被拦或失败时（auto）改用 Firecrawl。"""
    log(f"[1/2] 读取：{url}")
    try:
        # 不带 Referer：用户给的链接本来就不是从搜狗跳转来的
        art = fetch_article_auto(sess, url, referer=None, backend=args.backend)
    except Exception as e:
        print(f"读取失败：{e}", file=sys.stderr)
        return 1
    if art.get("error"):
        reason = {"deleted": "该文章已被发布者删除", "captcha": "被微信拦截",
                  "parse-failed": "正文解析失败"}.get(art["error"], art["error"])
        if art.get("fallback_error"):
            reason += f"；Firecrawl 未能接手：{art['fallback_error']}"
        elif art["error"] == "captcha" and args.backend == "direct":
            reason += "；去掉 --backend direct 可改用 Firecrawl"
        print(f"错误：{reason}", file=sys.stderr)
        return 2 if art["error"] == "captcha" else 1

    r = {"title": art["title"], "account": art["account"], "time": art["publish_time"],
         "wx_url": url, "content_provider": art.get("provider", "direct")}
    os.makedirs(args.outdir, exist_ok=True)
    r["file"] = _save_article(args.outdir, r, art["content"], "article")
    r["chars"] = len(art["content"])
    log(f"  ✓ {r['chars']} 字 — {r['file']}")
    log(f"     {r['account']} | {r['time']} | {r['content_provider']}")
    if args.json:
        print(json.dumps([r], ensure_ascii=False, indent=2))
        return 0
    idx = os.path.join(args.outdir, "_results.json")
    with open(idx, "w", encoding="utf-8") as f:
        json.dump([r], f, ensure_ascii=False, indent=2)
    log(f"[2/2] 索引：{idx}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="wxsearch", description="搜索微信公众号文章并抓取全文，或直接读取文章链接；限流时可自动切换 Firecrawl")
    ap.add_argument("query", nargs="?", help="搜索关键词，或公众号文章链接（直接读全文）；--type gzh 时为公众号名")
    ap.add_argument("--doctor", action="store_true",
                    help="自检：区分工具故障与 IP 被限流。抓不到东西时先跑这个")
    ap.add_argument("--type", "-t", choices=["article", "gzh"], default="article", help="搜文章还是搜公众号")
    ap.add_argument("--page", "-p", type=int, default=1, help="页码")
    ap.add_argument("--days", "-d", type=int, help="限最近 N 天（搜狗尽力而为，冷门词会用旧文补位）")
    ap.add_argument("--fetch", "-f", type=int, default=0, metavar="N", help="抓前 N 篇全文（默认 0，只列清单）")
    ap.add_argument("--outdir", "-o", default="wx_out", help="输出目录")
    ap.add_argument("--json", action="store_true", help="仅输出 JSON 到 stdout")
    ap.add_argument("--backend", choices=["auto", "direct", "firecrawl"], default="auto",
                    help="auto（默认）在本地限流时切 Firecrawl；direct 仅本地；firecrawl 仅远端")
    ap.add_argument("--min-delay", type=float, default=1.0)
    ap.add_argument("--max-delay", type=float, default=2.2)
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--version", action="version", version=f"wxsearch {__version__}")
    args = ap.parse_args(argv)

    if args.doctor:
        return doctor(verbose=args.verbose)
    if not args.query:
        ap.error("缺少搜索关键词或文章链接（或用 --doctor 自检）")

    sess = Session(delay=(args.min_delay, args.max_delay), verbose=args.verbose)
    log = (lambda *a: None) if args.json else (lambda *a: print(*a))
    if _ARTICLE_URL.match(args.query.strip()):
        return read_url(sess, args.query.strip(), args, log)

    try:
        log(f"[1/3] 搜索：{args.query}" + (f"（最近 {args.days} 天）" if args.days else ""))
        results, ref = search_auto(
            sess, args.query, args.page, args.days, args.type, backend=args.backend)
    except Blocked as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"搜索失败：{e}", file=sys.stderr)
        return 1

    if not results:
        log("未找到结果")
        if args.json:
            print("[]")
        return 0

    if args.type == "gzh":
        for i, r in enumerate(results, 1):
            log(f"  {i}. {r['nickname']}  ({r['wechat_id']})")
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    log(f"      共 {len(results)} 条")
    for i, r in enumerate(results, 1):
        log(f"  {i}. {r['title'][:50]}")
        log(f"     {r['account']} | {r['time']} | {r.get('provider', 'unknown')}")

    n = args.fetch
    if n:
        log(f"[2/3] 解析真实链接并抓全文（前 {min(n, len(results))} 篇）")
        os.makedirs(args.outdir, exist_ok=True)
        for i, r in enumerate(results[:n], 1):
            try:
                wx = resolve_auto(sess, r, ref, backend=args.backend)
            except Blocked as e:
                log(f"  {i}. ✗ {e}")
                r["error"] = "blocked"
                break
            except Exception as e:
                log(f"  {i}. ✗ 解析失败：{e}")
                r["error"] = "resolve-failed"
                continue
            if not wx:
                log(f"  {i}. ✗ 无法解析链接")
                r["error"] = "resolve-failed"
                continue
            r["wx_url"] = wx
            try:
                art = fetch_article_auto(
                    sess, wx, referer=r["sogou_link"], backend=args.backend, title=r["title"])
            except Exception as e:
                log(f"  {i}. ✗ 抓取失败：{e}")
                r["error"] = "fetch-failed"
                continue
            if art.get("error"):
                tip = {
                    "deleted": "⊘ 已被发布者删除",
                    "captcha": "✗ 本地与备用通道均被微信拦截",
                    "parse-failed": "✗ 正文解析失败",
                }.get(art["error"], f"✗ {art['error']}")
                log(f"  {i}. {tip} — {r['title'][:36]}")
                r["error"] = art["error"]
                if art.get("fallback_error"):
                    r["fallback_error"] = art["fallback_error"]
                continue
            r["account"] = art["account"] or r["account"]
            r["time"] = art["publish_time"] or r["time"]
            r["title"] = art["title"] or r["title"]
            wx = art.get("wx_url") or wx
            r["wx_url"] = wx
            r["content_provider"] = art.get("provider", "direct")
            fp = _save_article(args.outdir, r, art["content"], f"article{i}")
            r["file"] = fp
            r["chars"] = len(art["content"])
            log(f"  {i}. ✓ {len(art['content'])} 字 — {fp}")

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif n:
        idx = os.path.join(args.outdir, "_results.json")
        with open(idx, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        log(f"[3/3] 索引：{idx}")

    if n:
        want = min(n, len(results))
        got = sum(1 for r in results[:n] if r.get("file"))
        blocked = sum(1 for r in results[:n] if r.get("error") in ("captcha", "blocked"))
        if got == 0:
            if blocked:
                print(f"错误：{want} 篇的本地与备用正文通道均被拦截。"
                      f"先跑 firecrawl --status；备用正常时稍后再试。", file=sys.stderr)
                return 2
            print(f"错误：{want} 篇均未取到正文", file=sys.stderr)
            return 1
        if blocked:
            log(f"      注意：{blocked} 篇的本地与备用通道均被拦截，可稍后重跑")
    return 0


if __name__ == "__main__":
    sys.exit(main())

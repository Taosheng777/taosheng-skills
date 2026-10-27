# a-stock-data V3.4.0 冒烟测试 — 代码逐字取自 SKILL.md §1.2 / §3.6 / §7.1
# 可 import 复用(em_get 等基建),仅直接运行时才执行测试
import time, random, urllib.request
import requests
from datetime import datetime, timedelta

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _em_adapter = HTTPAdapter(max_retries=Retry(
        total=3, connect=3, backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]))
    EM_SESSION.mount("https://", _em_adapter)
    EM_SESSION.mount("http://", _em_adapter)
except Exception:
    pass
EM_MIN_INTERVAL = 1.0
_em_last_call = [0.0]

EM_PUSH2_PRIMARY = "push2.eastmoney.com"
EM_PUSH2_FALLBACK = "push2delay.eastmoney.com"

def em_get(url, params=None, headers=None, timeout=15, **kwargs):
    """与 SKILL.md 同版：节流 + push2 主域→push2delay 备胎一次性降级。"""
    def _once(u):
        wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
        if wait > 0:
            time.sleep(wait + random.uniform(0.1, 0.5))
        try:
            return EM_SESSION.get(u, params=params, headers=headers, timeout=timeout, **kwargs)
        finally:
            _em_last_call[0] = time.time()
    try:
        r = _once(url)
        if EM_PUSH2_PRIMARY in url and not (r.content or b"").strip():
            raise ValueError("empty body")
        return r
    except Exception:
        if EM_PUSH2_PRIMARY not in url:
            raise
        return _once(url.replace(EM_PUSH2_PRIMARY, EM_PUSH2_FALLBACK))

def eastmoney_datacenter(report_name, columns="ALL", filter_str="", page_size=50,
                         sort_columns="", sort_types="-1"):
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = em_get(DATACENTER_URL, params=params, timeout=15)
    d = r.json()
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []

SH_INDEX = {"000300", "000905", "000016", "000688", "000852", "000010"}

def get_prefix(code: str) -> str:
    """6位代码 → 市场前缀（sh/sz/bj）。支持显式前缀/后缀（sh000016 / 000016.SH）透传以解决歧义。"""
    c = code.lower().strip()
    if c.endswith((".sh", ".sz", ".bj")):    # 后缀写法与前缀等价：000016.SH ≡ sh000016。
        return c[-2:]                        # 不认后缀会让 000016.SH 落到默认深市 → 静默查成深康佳A
    if c.endswith((".xshg", ".xshe")):       # 聚宽写法（#55）：.XSHG=上交所 / .XSHE=深交所，000001.XSHG=上证指数
        return "sh" if c.endswith(".xshg") else "sz"
    if c.startswith(("sh", "sz", "bj")):     # 显式前缀透传（如 sh000001=上证指数 vs sz000001=平安银行）
        return c[:2]
    if c.startswith("92"):                   # 北交所 2024-10 起的新股号段，必须先于下面的 9x 判断
        return "bj"
    if c.startswith(("5", "6", "9")):        # 5x=沪 ETF/LOF，6/9=沪个股（900xxx=沪 B 股）
        return "sh"
    if c.startswith(("4", "8")):             # 4x/8x=北交所【老号段，多数已迁 920，见下方警告】
        return "bj"
    if c in SH_INDEX:                         # 沪深300/上证50 等沪指数（000xxx）
        return "sh"
    return "sz"                              # 深市个股/ETF（00/30/15x/16x/159 等），深指数 399xxx 亦走 sz

import re

_TICKER_RE = re.compile(
    r"^(?:(sh|sz|bj)(\d{6})|(\d{6})(?:\.(sh|sz|bj|xshg|xshe))?)$", re.IGNORECASE)

_JQ_SUFFIX = {"xshg": "sh", "xshe": "sz"}    # 聚宽后缀 → 市场（#55）；聚宽未公开北交所后缀，不猜

def _natural_market(digits: str) -> str:
    """6 位码的自然归属市场。仅用于校验显式前缀是否自相矛盾。
    注意 000xxx 是沪指数/深个股共用的歧义段，由调用处单独处理，不走这里。"""
    if digits.startswith(("4", "8", "92")):
        return "bj"                      # 北交所：与 get_prefix() 同一套号段规则（92x 现行 / 4x·8x 老号段，#51）
    if digits[0] in ("5", "6", "9"):
        return "sh"                      # 5x 沪 ETF/LOF，6xx 沪个股，9xx 沪 B 股
    return "sz"                          # 00x/30x/15x/16x/39x 等

def norm_ticker(code: str, stock_only: bool = False) -> str:
    """任意受支持写法 → 纯 6 位数字代码。

    支持 600519 / SH600519 / sh600519 / 600519.SH / BJ920982 等。
    stock_only=True：个股专用接口（研报、一致预期等）传这个，会拒绝显式指数写法。
    ⚠️ 不匹配时**抛 ValueError，绝不静默返回空串或猜一个代码**——
    否则调用方会把「代码格式写错」误读成「这只票没有数据」，
    或者更糟：拿到另一只股票的数据还以为是对的。
    """
    raw = str(code).strip()
    m = _TICKER_RE.match(raw)
    if not m:
        raise ValueError(
            f"无法把 {code!r} 解析为 6 位股票代码；"
            f"支持格式：600519 / SH600519 / sh600519 / 600519.SH / 600519.XSHG（聚宽）"
            f"（前缀与后缀二选一，不能同时写）"
        )
    digits = m.group(2) or m.group(3)
    market = (m.group(1) or m.group(4) or "").lower()      # 前缀式与后缀式都要认
    market = _JQ_SUFFIX.get(market, market)                  # 600519.XSHG ≡ 600519.SH
    # 归一化会丢掉市场标识，若标识与号段矛盾就会静默落到另一只票上，必须在这里拦。
    if market:
        if digits.startswith("000"):
            # 000xxx 是**沪市指数 / 深市个股共用**的歧义段，显式标识在这里是「消歧」不是「矛盾」：
            #   sh000001=上证指数 vs sz000001=平安银行；sh000016=上证50 vs sz000016=深康佳A。
            if market == "bj":
                raise ValueError(f"{code!r} 市场标识与号段矛盾：000xxx 不属北交所。")
            # 沪市个股只有 600/601/603/605/688/689（B 股 900），**不存在 000xxx 沪市个股**，
            # 所以「显式 sh + 000 段」必然是指数。实测不拦的话：sh000001→平安银行研报 100 篇、
            # sh000016→深康佳A、sh000039→中集集团 84 篇，全是别人的数据。
            if stock_only and market == "sh":
                raise ValueError(
                    f"{code!r} 指向沪市指数而非个股（沪市无 000xxx 个股），本接口只服务个股。"
                    f"要查同号段的深市个股请显式传 sz{digits}。"
                )
        else:
            nat = _natural_market(digits)
            if market != nat:
                raise ValueError(
                    f"{code!r} 的市场标识与号段矛盾：{digits} 属 {nat} 市，而不是 {market} 市。"
                    f"（改用 {nat}{digits} 或去掉市场标识）"
                )
    return digits

def em_market_code(code: str) -> int:
    """东财 secid 的市场号：**沪=1，深/北=0**（V3.7.0 新增 · #46）。

    ⚠️ 绝不要用 `code.startswith("6")` 判市场 —— 那会把**沪市 ETF（51x）**、
    **科创板 ETF（588x）**、**沪 B 股（900x）** 全部错判成深市，接口返回 `data: null`。
    2026-08-19 实测：510300 / 588000 / 600519 / 688112 / 900901 → m=1；
    300750 / 159915 / 920982 / 832982 → m=0（北交所与深市共用 m=0）。
    """
    return 1 if get_prefix(code) == "sh" else 0

def em_secid(code: str) -> str:
    """东财 push2/push2his 的 secid，如 `1.600519` / `0.300750`。"""
    return f"{em_market_code(code)}.{norm_ticker(code)}"

def to_joinquant(code: str) -> str:
    """任意受支持写法 → 聚宽代码，如 `600519.XSHG` / `000001.XSHE`（#55）。

    000 段歧义码按 get_prefix() 的规则走：`to_joinquant("sh000001")` → `000001.XSHG`（上证指数），
    `to_joinquant("000001")` → `000001.XSHE`（平安银行）。反方向（聚宽 → 本 Skill）用
    `get_prefix(c) + norm_ticker(c)` 得到 `sh000001` 这类显式前缀写法，再传给各端点。
    北交所：聚宽公开文档与 jqdatasdk 源码（2026-09-20 查）只有 .XSHG / .XSHE，没查到北交所后缀，抛 ValueError 不猜。
    """
    digits, market = norm_ticker(code), get_prefix(code)
    if market == "bj":
        raise ValueError(f"{code!r} 是北交所证券；聚宽公开文档未给出北交所后缀，不做转换")
    return f"{digits}.{'XSHG' if market == 'sh' else 'XSHE'}"


def tencent_quote(codes):
    prefixed = [get_prefix(c) + norm_ticker(c) for c in codes]
    return tencent_quote_prefixed(prefixed)

def tencent_quote_prefixed(prefixed_codes):
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed_codes)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")
    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "mcap_yi": float(vals[45]) if vals[45] else 0,
            "float_mcap_yi": float(vals[44]) if vals[44] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
        }
    return result

def lockup_expiry(code, trade_date, forward_days=90):
    history_data = eastmoney_datacenter(
        "RPT_LIFT_STAGE", filter_str=f'(SECURITY_CODE="{code}")',
        page_size=15, sort_columns="FREE_DATE", sort_types="-1")
    history = [{
        "date": str(r.get("FREE_DATE", ""))[:10],
        "type": r.get("FREE_SHARES_TYPE", ""),
        "shares": r.get("FREE_SHARES", 0),
        "able_shares": r.get("ABLE_FREE_SHARES", 0),
        "ratio": r.get("FREE_RATIO", 0),
    } for r in history_data]
    end_str = (datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)).strftime("%Y-%m-%d")
    upcoming_data = eastmoney_datacenter(
        "RPT_LIFT_STAGE",
        filter_str=f'(SECURITY_CODE="{code}")(FREE_DATE>=\'{trade_date}\')(FREE_DATE<=\'{end_str}\')',
        page_size=20, sort_columns="FREE_DATE", sort_types="1")
    upcoming = [{
        "date": str(r.get("FREE_DATE", ""))[:10],
        "type": r.get("FREE_SHARES_TYPE", ""),
        "shares": r.get("FREE_SHARES", 0),
    } for r in upcoming_data]
    return {"history": history, "upcoming": upcoming}

def _cninfo_ts_to_date(ts):
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
    return str(ts)[:10] if ts else ""

_CNINFO_ORGID_MAP = {}

def _cninfo_orgid(code):
    global _CNINFO_ORGID_MAP
    if not _CNINFO_ORGID_MAP:
        try:
            r = requests.get("http://www.cninfo.com.cn/new/data/szse_stock.json",
                             headers={"User-Agent": UA}, timeout=15)
            _CNINFO_ORGID_MAP = {s["code"]: s["orgId"] for s in r.json().get("stockList", [])}
        except Exception as e:
            print(f"[WARN] orgId 映射表拉取失败: {e}")
    org = _CNINFO_ORGID_MAP.get(code)
    if org:
        return org
    if get_prefix(code) == "sh":
        return f"gssh0{code}"
    elif get_prefix(code) == "bj":
        return f"gsbj0{code}"
    return f"gssz0{code}"

def cninfo_announcements(code, page_size=30):
    url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    org_id = _cninfo_orgid(code)
    payload = {
        "stock": f"{code},{org_id}", "tabName": "fulltext",
        "pageSize": str(page_size), "pageNum": "1",
        "column": "", "category": "", "plate": "", "seDate": "",
        "searchkey": "", "secid": "", "sortName": "", "sortType": "",
        "isHLtitle": "true",
    }
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.cninfo.com.cn/new/disclosure",
        "Origin": "https://www.cninfo.com.cn",
    }
    r = requests.post(url, data=payload, headers=headers, timeout=15)
    d = r.json()
    return [{
        "title": i.get("announcementTitle", ""),
        "type": i.get("announcementTypeName", ""),
        "date": _cninfo_ts_to_date(i.get("announcementTime")),
    } for i in d.get("announcements", []) or []]


def run_smoke_tests():
    results = {}

    # 测试1: 腾讯行情(个股 + 沪市ETF 用修正前缀)
    try:
        q = tencent_quote(["600519"])
        q.update(tencent_quote_prefixed(["sh510300"]))
        mt, etf = q.get("600519", {}), q.get("510300", {})
        ok = mt.get("price", 0) > 0 and etf.get("price", 0) > 0 and mt.get("pe_ttm", 0) > 0
        results["腾讯行情"] = "PASS" if ok else f"FAIL {q}"
        print(f"[1 腾讯行情] {mt.get('name')}({mt.get('price')}元 PE={mt.get('pe_ttm')}) | "
              f"{etf.get('name')}({etf.get('price')}元) -> {results['腾讯行情']}")
    except Exception as e:
        results["腾讯行情"] = f"FAIL {e}"
        print(f"[1 腾讯行情] FAIL: {e}")

    # 测试2: 解禁日历(东财 datacenter, V3.4 修复的新列名)
    try:
        d = lockup_expiry("002475", datetime.now().strftime("%Y-%m-%d"))
        hist_ok = len(d["history"]) > 0 and d["history"][0]["type"] != "" and d["history"][0]["shares"]
        results["解禁日历"] = "PASS" if hist_ok else f"FAIL(type/shares空: {d['history'][:2]})"
        print(f"[2 解禁日历] 立讯精密历史解禁{len(d['history'])}批 -> {results['解禁日历']}")
    except Exception as e:
        results["解禁日历"] = f"FAIL {e}"
        print(f"[2 解禁日历] FAIL: {e}")

    # 测试3: 巨潮公告(601xxx 动态 orgId 路径)
    try:
        anns = cninfo_announcements("601318", page_size=10)
        ok = len(anns) > 0 and anns[0]["title"]
        results["巨潮公告"] = "PASS" if ok else "FAIL(0条)"
        print(f"[3 巨潮公告] 中国平安公告{len(anns)}条, 最新: "
              f"{anns[0]['date'] if anns else '-'} -> {results['巨潮公告']}")
    except Exception as e:
        results["巨潮公告"] = f"FAIL {e}"
        print(f"[3 巨潮公告] FAIL: {e}")

    print("\n=== 汇总:", results)
    return results


if __name__ == "__main__":
    run_smoke_tests()

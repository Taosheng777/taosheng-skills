#!/usr/bin/env python3
"""成片交给 Gemini（agy）独立查错，脚本先测转场、再核 Gemini 的说法。

用法：
  gemini_review.py 成片.mp4 --out 工作目录/验片/gemini
  gemini_review.py 成片.mp4 --out … --no-gemini     # 只跑脚本检测，不调 Gemini

流程：全片逐帧测亮度和剪切（这里只是数值检测，不判断剪辑意图）→
每秒 1 帧 + 剪切点前后各 1 帧 + 最后可解码帧，带时间码拼成 2×2 拼图 → Gemini 出结构化问题表 →
脚本按亮度数据核“黑帧/白帧/闪烁/跳变”类说法 → report.md。调用方只读 report.md 和待看证据帧。
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

GEMINI_ASK = Path.home() / ".agents/skills/gemini-dispatch/scripts/gemini_ask.py"
FONT = "/System/Library/Fonts/Menlo.ttc"
DEFAULT_MODEL = "gemini-3.8-flash-high"
SCRIPT_VERSION = "codex-h3-2026-10-26.1"

BLACK_Y = 8          # 平均亮度低于此算黑
LONG_BLACK_S = 0.3
SPIKE_DY = 30
FADE_MIN_STEPS = 8
FADE_MIN_DELTA = 40
CUT_DIFF = 0.8       # 相邻帧平均差值的孤立尖峰算突变（剪切、物件替换）
BRIGHTNESS_KINDS = ("黑帧", "白帧", "闪烁")
KINDS = ["黑帧", "白帧", "闪烁", "跳变", "网格花屏", "其他"]


def tc(s):
    m = re.fullmatch(r"\s*(\d+):(\d+(?:\.\d+)?)\s*", str(s))
    if not m or not 0 <= float(m.group(2)) < 60:
        raise ValueError(f"时间码看不懂：{s}")
    return int(m.group(1)) * 60 + float(m.group(2))


def fmt(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def parse_luma(text):
    out, cur = [], None
    for line in text.splitlines():
        if line.startswith("frame:"):
            m = re.search(r"pts_time:([\d.]+)", line)
            cur = [float(m.group(1)), None, 0.0]
            out.append(cur)
        elif cur is not None and "signalstats.YAVG=" in line:
            cur[1] = float(line.split("=", 1)[1])
        elif cur is not None and "scd.score=" in line:
            cur[2] = float(line.split("=", 1)[1])
    return [tuple(x) for x in out if x[1] is not None]


def _runs(flags):
    start = None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            yield start, i - 1
            start = None


def find_events(series, fps):
    t = [s[0] for s in series]
    y = [s[1] for s in series]
    n = len(y)
    ev = {"fades": [], "blacks": [], "short_blacks": [], "spikes": [], "cuts": []}

    for a, b in _runs([v < BLACK_Y for v in y]):
        span = (t[a], t[b] + 1 / fps)
        (ev["blacks"] if (b - a + 1) / fps >= LONG_BLACK_S else ev["short_blacks"]).append(span)

    for i in range(1, n - 1):
        if (abs(y[i] - y[i - 1]) > SPIKE_DY and abs(y[i] - y[i + 1]) > SPIKE_DY
                and abs(y[i - 1] - y[i + 1]) < 10):
            ev["spikes"].append(t[i])

    # 平滑渐变：同向的小步连续变化（允许夹几帧不变），步子太大的是剪切不是渐变
    fades, i = [], 1
    while i < n:
        d = y[i] - y[i - 1]
        if d == 0 or abs(d) > SPIKE_DY:
            i += 1
            continue
        sign, start, steps, flat, j = (d > 0) - (d < 0), i - 1, 0, 0, i
        while j < n:
            dj = y[j] - y[j - 1]
            if abs(dj) > SPIKE_DY or (dj and ((dj > 0) - (dj < 0)) != sign):
                break
            if dj == 0:
                flat += 1
                if flat > 5:
                    break
            else:
                steps, flat = steps + 1, 0
            j += 1
        if steps >= FADE_MIN_STEPS and abs(y[j - 1] - y[start]) >= FADE_MIN_DELTA:
            fades.append([t[start], t[j - 1]])
        i = max(j, i + 1)
    for f in fades:
        if ev["fades"] and f[0] - ev["fades"][-1][1] <= 0.2:
            ev["fades"][-1][1] = f[1]
        else:
            ev["fades"].append(f)
    ev["fades"] = [tuple(f) for f in ev["fades"]]

    d = [s[2] for s in series]
    for i in range(n):
        nb = sorted(d[max(0, i - 5):i] + d[i + 1:i + 6])
        med = nb[len(nb) // 2] if nb else 0
        if d[i] >= CUT_DIFF and d[i] > 4 * max(med, 0.05):
            ev["cuts"].append(t[i])
    return ev


def sample_times(duration, cuts, step=1.0, last_frame_time=None):
    if not math.isfinite(step) or step <= 0:
        raise ValueError("抽帧间隔 --step 必须大于 0 且为有限数")
    base = [round(k * step, 2) for k in range(int(duration / step) + 1) if k * step < duration]
    extra = [round(c + d, 2) for c in cuts for d in (-0.15, 0.15) if 0 <= c + d < duration]
    out = []
    for x in sorted(set(base + extra)):
        if not out or x - out[-1] >= 0.1 - 1e-9:
            out.append(x)
    if last_frame_time is not None:
        # 从实际逐帧检测拿末帧 PTS；略向前取，避免小数舍入导致 seek 越过末帧。
        last = max(0.0, last_frame_time - 0.001)
        out = [x for x in out if x < last - 0.1]
        out.append(last)
    return out


def _overlaps(spans, a, b):
    return [s for s in spans if s[0] <= b and s[1] >= a]


def verify(items, ev, series):
    out = []
    for it in items:
        it = dict(it)
        try:
            a = tc(it.get("start"))
            b = tc(it.get("end") or it.get("start"))
        except ValueError:
            it["status"] = "存疑：时间码看不懂"
            out.append(it)
            continue
        # Gemini 读到的标签精确至 0.1 秒，容许末帧标签有 0.05 秒四舍五入误差。
        if not series or min(a, b) < 0 or max(a, b) > series[-1][0] + 0.051:
            it["status"] = "存疑：时间码超出实际可解码视频范围"
            out.append(it)
            continue
        lo, hi = min(a, b) - 0.5, max(a, b) + 0.5
        kind, cat = it.get("kind"), it.get("category")
        gradual = _overlaps(ev["fades"], lo, hi) + _overlaps(ev["blacks"], lo, hi)
        glitches = [x for x in ev["spikes"] if lo <= x <= hi] + _overlaps(ev["short_blacks"], lo, hi)
        cuts = [x for x in ev["cuts"] if lo <= x <= hi]
        if cat == 1 and kind in BRIGHTNESS_KINDS:
            if glitches:
                it["status"] = "脚本证实：此处有单帧亮度突变"
            elif gradual:
                s = gradual[0]
                it["status"] = f"待看：{fmt(s[0])}–{fmt(s[1])} 有渐变或持续黑段，是否有意需核时间线"
            else:
                it["status"] = "存疑：脚本没测到亮度突变"
        elif cat == 1 and kind == "跳变":
            ys = [s[1] for s in series if lo <= s[0] <= hi]
            dmax = max((abs(q - p) for p, q in zip(ys, ys[1:])), default=0)
            if cuts or glitches:
                it["status"] = "待看：此处有剪切，判断是不是设计"
            elif dmax < 3:
                it["status"] = "待看：亮度稳定不能排除人物或物件突变"
            else:
                it["status"] = "待看"
        elif cat in (1, 2):
            it["status"] = "待看：脚本核不了，看证据帧"
        else:
            it["status"] = "待看：模型候选，未独立核实"
        out.append(it)
    return out


# ---------- 以下是调用 ffmpeg / Gemini 的编排，靠实片验证 ----------

def run(cmd, **kw):
    if cmd[0] in ("ffmpeg", "ffprobe") and not shutil.which(cmd[0]):
        local = Path.home() / ".local/bin" / cmd[0]
        if local.is_file():
            cmd = [str(local), *cmd[1:]]
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def probe(video):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(video)])
    d = json.loads(r.stdout)
    st = d["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    return st["width"], st["height"], float(d["format"]["duration"]), float(num) / float(den)


def measure(video, out):
    """每帧 (时间, 平均亮度, 与上一帧的平均差值)。"""
    def stats(vf):
        r = run(["ffmpeg", "-v", "error", "-i", str(video), "-an", "-vf",
                 f"scale=144:-2,format=gray,{vf}signalstats,metadata=mode=print:file=-", "-f", "null", "-"])
        return parse_luma(r.stdout)
    luma = stats("")
    diff = {round(t, 3): y for t, y, _ in stats("tblend=all_mode=difference,")}
    s = [(t, y, diff.get(round(t, 3), 0.0)) for t, y, _ in luma]
    (out / "luma.tsv").write_text("".join(f"{a:.3f}\t{b:.1f}\t{c:.1f}\n" for a, b, c in s))
    return s


def grab(video, t, width, dst, label=True):
    vf = f"scale={width}:-2"
    if label:
        text = fmt(t).replace(":", r"\:")
        vf += (f",drawtext=fontfile={FONT}:text='{text}':x=10:y=10:fontsize={max(20, width // 20)}"
               ":fontcolor=white:box=1:boxcolor=black@0.75:boxborderw=6")
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.6f}", "-i", str(video),
         "-frames:v", "1", "-vf", vf, "-q:v", "3", str(dst)])


def build_sheets(video, times, width, out):
    frames, sheets = out / "frames", out / "sheets"
    for d in (frames, sheets):
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.jpg"):
            f.unlink()
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda p: grab(video, p[1], width, frames / f"f{p[0]:04d}.jpg"), enumerate(times)))
    pad = (-len(times)) % 4
    for k in range(pad):   # 补黑格凑满最后一张 2×2
        run(["ffmpeg", "-v", "error", "-y", "-i", str(frames / "f0000.jpg"), "-vf",
             "drawbox=c=black:t=fill", str(frames / f"f{len(times) + k:04d}.jpg")])
    run(["ffmpeg", "-v", "error", "-y", "-i", str(frames / "f%04d.jpg"), "-vf", "tile=2x2",
         "-q:v", "3", "-start_number", "1", str(sheets / "s%03d.jpg")])
    return sorted(sheets.glob("s*.jpg"))


SCHEMA = {
    "type": "object",
    "properties": {
        "sheets_read": {"type": "integer"},
        "last_sheet_content": {"type": "string"},
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "start": {"type": "string"}, "end": {"type": "string"},
                "category": {"type": "integer", "minimum": 1, "maximum": 6},
                "kind": {"type": "string", "enum": KINDS},
                "problem": {"type": "string"}, "fix": {"type": "string"},
                "confidence": {"type": "string", "enum": ["高", "中", "低"]},
            },
            "required": ["start", "end", "category", "kind", "problem", "fix", "confidence"],
        }},
    },
    "required": ["sheets_read", "items"],
}


def build_prompt(sheets_dir, n_sheets, vertical, duration, ev):
    if vertical:
        zones = ("字进入右侧 15% 宽度（抖音按钮区）；要读的字落在底部 20% 高度（平台说明区）；"
                 "字贴在顶部约 13% 高度以内可能被顶栏挡住")
        phone = "缩到 360 像素宽的手机竖屏"
    else:
        zones = "字贴边（离画面边缘不足 5%）"
        phone = "缩到 800 像素宽（手机横过来看）"
    measured = [f"{fmt(a)}–{fmt(b)} 渐变" for a, b in ev["fades"]]
    measured += [f"{fmt(a)}–{fmt(b)} 持续黑段" for a, b in ev["blacks"]]
    measured_txt = "；".join(measured) if measured else "无"
    return f"""你是一个没参与制作的审片员。请逐张读取目录 {sheets_dir} 下的 {n_sheets} 张拼图 s001.jpg … s{n_sheets:03d}.jpg（只用读文件，不要执行任何命令），全部看完再回答。
这是一条{'竖屏' if vertical else '横屏'}短片（约 {fmt(duration)}）的抽帧：每张拼图 4 格，按 左上→右上→左下→右下 的时间顺序，每格左上角黑底白字是该格的时间码（mm:ss.s）。按指定间隔抽样，剪切点前后有补充，并含最后可解码帧。只有最后一张无时间码的纯黑格是补位，不要忽略有时间码的真实黑帧。

只找穿帮和技术问题，不评价好不好看、不提审美建议。脚本测到这些亮度现象：{measured_txt}。这些只是候选，不能证明是有意转场；看到可疑黑屏、白帧、叠影等照常报告并说明不确定性。抽帧无法证明连续动作完整，也没有提供声音，不能声称试听或整片检查通过。

逐项检查（category 填编号）：
1. 画面故障：方块网格、花屏、撕裂、不该有的黑帧或白帧、闪烁、同一镜头里画面突然跳变。kind 选 黑帧/白帧/闪烁/跳变/网格花屏/其他。
2. 转场与物件切换：同一物件或人物两个版本交叉淡化出现叠影；贴在人身上的标签在没被揭下或落地时就突然变样（角度、字体、位置跳一下）。kind 填 其他。
3. 字的位置：字压在人物（头发、脸、衣服）上；浅色字压在画面最亮处（灯光、光带）；{zones}。kind 填 其他。
4. 折行：一个词被拆到两行（如“海/边”），或末行只剩一两个字。kind 填 其他。
5. 手机可读性：{phone}时哪些字小到读不清（尤其片尾信息卡、参考文献）；一屏字超过 6 行。kind 填 其他。
6. H3 连续性：同一镜头中人物身份、手脚数量、面部或面屏颜色、道具位置和接触关系的明显异常；区分跨镜剪辑和镜内变形。kind 填 其他。不能从稀疏抽帧断言完整动作成功。

要求：start/end 用格子上的时间码；只写你在格子里真的看到的问题，拿不准的 confidence 写“低”，不要编；同一问题跨多格合并成一条。sheets_read 填你实际读了几张拼图，last_sheet_content 一句话描述最后一张拼图里的画面。"""


def write_report(out, video, items, ev, meta):
    lines = [f"# Gemini 审片：{Path(video).name}", "",
             f"- 抽帧覆盖状态：**{meta['coverage']}**（按自报张数与预期张数核对，不独立证明逐图已看）",
             f"- 模型 {meta['model']}；{meta['stats']}",
             f"- 拼图 {meta['n_sheets']} 张（{meta['n_frames']} 格）；Gemini 自报读了 {meta['sheets_read']} 张；"
             f"最后一张它说是：{meta['last']}",
             f"- 脚本测到的渐变或持续黑段（意图未核）：" + ("；".join(f"{fmt(a)}–{fmt(b)}" for a, b in ev["fades"] + ev["blacks"]) or "无"),
             "- 范围：批量抽帧查错；不是逐帧目视、连续动作验收或试听。没有发现候选不等于成片通过。",
             ""]
    if meta["coverage"] != "complete":
        lines += ["**覆盖不完整：本次不能作为完整抽帧检查，也不会命中完成缓存。先查明漏看原因。**", ""]
    script_found = [f"{fmt(x)} 单帧亮度突变" for x in ev["spikes"]]
    script_found += [f"{fmt(a)}–{fmt(b)} 短黑帧" for a, b in ev["short_blacks"]]
    if script_found:
        lines += ["## 脚本自己测出的故障候选", ""] + [f"- {s}" for s in script_found] + [""]
    order = {"脚": 0, "待": 1, "可": 2, "存": 3, "误": 4}
    items = sorted(items, key=lambda it: (order.get(it["status"][0], 9), it["start"]))
    lines += ["## 问题表（按核实状态排序）", "",
              "| 时间码 | 问题 | 类 | 改法 | Gemini 把握 | 核实 | 证据帧 |", "|---|---|---|---|---|---|---|"]
    for it in items:
        ev_link = it.get("evidence", "")
        cell = lambda s: str(s).replace("|", "／").replace("\n", " ")
        rng = it["start"] if it["start"] == it["end"] else f"{it['start']}–{it['end']}"
        lines.append(f"| {rng} | {cell(it['problem'])} | {it['category']}{'·' + it['kind'] if it['category'] == 1 else ''} "
                     f"| {cell(it['fix'])} | {it['confidence']} | {it['status']} | {ev_link} |")
    (out / "report.md").write_text("\n".join(lines) + "\n")


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def review_signature(video, step, model):
    return {"video_sha256": sha256_file(video), "video": str(video),
            "step": step, "model": model, "script_version": SCRIPT_VERSION,
            "script_sha256": sha256_file(__file__)}


def coverage_status(reported, expected):
    return "complete" if type(reported) is int and reported == expected else "incomplete"


def cache_hit(out, signature, mode="review"):
    if mode != "review":
        return False
    try:
        meta = json.loads((out / "inspection_manifest.json").read_text())
        return (meta.get("mode") == "review" and meta.get("status") == "complete"
                and meta.get("signature") == signature
                and meta.get("report_sha256") == sha256_file(out / "report.md"))
    except (OSError, ValueError):
        return False


def write_manifest(out, signature, mode, status, **fields):
    data = {"signature": signature, "mode": mode, "status": status, **fields}
    (out / "inspection_manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def local_report(out, video, ev, mode, n_frames=0, n_sheets=0):
    text = [f"# 审片准备：{video.name}", "", f"- 模式：{mode}；本次没有调用 Gemini。",
            "- 覆盖状态：未进行模型审片；不能作为视觉、连续动作或声音验收。",
            f"- 技术候选：渐变 {len(ev['fades'])} 处、持续黑段 {len(ev['blacks'])} 处、"
            f"短黑段 {len(ev['short_blacks'])} 处、亮度突变 {len(ev['spikes'])} 处；剪辑意图未核。",
            f"- 生成 {n_sheets} 张拼图、{n_frames} 个取样；详情见 events.json 和 luma.tsv。", ""]
    (out / "report.md").write_text("\n".join(text))


def main():
    p = argparse.ArgumentParser(description="成片交给 Gemini 独立查错，脚本核实")
    p.add_argument("video")
    p.add_argument("--out", required=True, help="工作目录（大文件放外置 SSD 的项目 work/ 下）")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--step", type=float, default=1.0, help="抽帧间隔秒数，默认 1")
    p.add_argument("--timeout", default="30m")
    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--no-gemini", action="store_true", help="只跑脚本检测，不读取完成缓存")
    modes.add_argument("--prepare-only", action="store_true", help="只生成技术检测和拼图，不调用 Gemini")
    p.add_argument("--force", action="store_true", help="明确重审，忽略同内容完成缓存")
    a = p.parse_args()
    if not math.isfinite(a.step) or a.step <= 0:
        p.error("--step 必须大于 0 且为有限数")

    video, out = Path(a.video).expanduser().resolve(), Path(a.out).expanduser().resolve()
    if not video.is_file():
        p.error(f"视频文件不存在：{video}")
    out.mkdir(parents=True, exist_ok=True)
    mode = "local-only" if a.no_gemini else "prepare-only" if a.prepare_only else "review"
    signature = review_signature(video, a.step, a.model)
    if not a.force and cache_hit(out, signature, mode):
        print(f"[审片] 复用同内容、采样和模型的完成报告，未调用 Gemini：{out / 'report.md'}", file=sys.stderr)
        return
    write_manifest(out, signature, mode, "running")
    w, h, dur, fps = probe(video)
    vertical = h > w
    series = measure(video, out)
    ev = find_events(series, fps)
    (out / "events.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1))
    if not series:
        sys.exit("[审片] 没有可解码视频帧，停止")
    print(f"[审片] 渐变/持续黑段候选 {len(ev['fades']) + len(ev['blacks'])} 处，剪切 {len(ev['cuts'])} 处，"
          f"脚本故障候选 {len(ev['spikes']) + len(ev['short_blacks'])} 处", file=sys.stderr)
    if a.no_gemini:
        local_report(out, video, ev, mode)
        write_manifest(out, signature, mode, "local-check-complete")
        return

    times = sample_times(dur, ev["cuts"], a.step, series[-1][0])
    sheets = build_sheets(video, times, 540 if vertical else 960, out)
    (out / "samples.json").write_text(json.dumps({"times": times, "last_decoded_frame_time": series[-1][0],
        "n_frames": len(times), "n_sheets": len(sheets)}, ensure_ascii=False, indent=2) + "\n")
    prompt = build_prompt(out / "sheets", len(sheets), vertical, dur, ev)
    (out / "prompt.md").write_text(prompt)
    schema_path = out / "schema.json"
    schema_path.write_text(json.dumps(SCHEMA, ensure_ascii=False))
    if a.prepare_only:
        local_report(out, video, ev, mode, len(times), len(sheets))
        write_manifest(out, signature, mode, "prepared", n_frames=len(times), n_sheets=len(sheets))
        print(f"[审片] 拼图已准备，未调用 Gemini：{out}", file=sys.stderr)
        return
    if not GEMINI_ASK.is_file():
        sys.exit(f"[审片] 缺少 Gemini 入口：{GEMINI_ASK}")
    r = subprocess.run([sys.executable, str(GEMINI_ASK), prompt, "-m", a.model, "-d", str(out / "sheets"),
                        "-s", str(schema_path), "-t", a.timeout, "--raw", str(out / "gemini-raw.json")],
                       capture_output=True, text=True)
    (out / "gemini.err").write_text(r.stderr)
    if r.returncode != 0:
        write_manifest(out, signature, mode, "failed", gemini_exit_code=r.returncode)
        sys.exit(f"[审片] Gemini 调用失败（exit={r.returncode}）：{r.stderr.strip()[-500:]}")
    data = json.loads(r.stdout)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list) or not all(isinstance(i, dict) for i in data["items"]):
        write_manifest(out, signature, mode, "failed", reason="Gemini 结果结构异常")
        sys.exit("[审片] Gemini 结果结构异常，不能作为完成检查")
    coverage = coverage_status(data.get("sheets_read"), len(sheets))
    items = verify(data.get("items", []), ev, series)

    evd = out / "evidence"
    evd.mkdir(exist_ok=True)
    for k, it in enumerate(items):
        if it["status"].startswith(("待看", "脚本证实")):
            dst = evd / f"e{k:02d}-{fmt(tc(it['start'])).replace(':', '')}.jpg"
            grab(video, min(tc(it["start"]), max(0, series[-1][0] - 0.001)), 720 if vertical else 1280, dst)
            it["evidence"] = f"evidence/{dst.name}"
    (out / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=1))
    stats = (r.stderr.strip().splitlines() or ["?"])[-1].replace("[gemini] ", "")
    write_report(out, video, items, ev, {
        "model": a.model, "stats": stats, "n_sheets": len(sheets), "n_frames": len(times),
        "sheets_read": data.get("sheets_read"), "last": data.get("last_sheet_content", ""), "coverage": coverage})
    write_manifest(out, signature, mode, coverage, n_frames=len(times), n_sheets=len(sheets),
                   sheets_read=data.get("sheets_read"), report_sha256=sha256_file(out / "report.md"))
    print(f"[审片] 报告已写入（覆盖 {coverage}）：{out / 'report.md'}", file=sys.stderr)
    if coverage != "complete":
        sys.exit(2)


if __name__ == "__main__":
    main()

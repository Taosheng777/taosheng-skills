#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stop hook：阶段完成却没按人话汇报时，把最终回复拦回来重写。

判据的三条设计前提（改之前先看懂，别直接加词）：

1. 结论先行 —— 真收口了，完成语必然出现在开头。所以只看正文前
   HEAD_CHARS 个字；正文中间提到「完成」不算数。这一条同时挡掉了
   「先报进展……某某已全部跑完」这类中间汇报。
2. 只认交付动词 —— 「查完了 / 读完了 / 看完了」是回答问题，不是交付
   阶段成果，故意不收进 BUILD。
3. 否定就地否掉 —— 只否定紧挨着完成词的那个「没 / 未 / 不 / 无法」，
   不做整段否定扫描；否则「做完了，但没有提交 git」会被误放。
4. 状态盘点不是新交付 —— 「状态已确认：旧阶段已完成」是在复述现状，
   不是本轮刚完成阶段；这类明确的核对开头直接放行。

判据是启发式，一定有边界情形。漏拦的代价是一次汇报没兜住，误拦的代价
是多花一轮。宁可稍微多拦，但绝不允许崩溃阻断会话——异常一律放行。

回归语料摘自作者本人的真实会话，含私人内容，未随公开版发布；改判据前请自建语料。
唯一来源：~/.codex/skills/stage-reporting/scripts/plain_stage_report.py
项目 .codex/hooks/ 与 ~/.claude/hooks/ 下的都是逐字节副本；改判据改这里，
再跑 install.py 重装项目、并同步一份到 ~/.claude/hooks/。
"""
import json
import os
import re
import sys

HEAD_CHARS = 50

# 「这一轮已经好好汇报过了」的信号。
# 早期版本用隐藏 HTML 注释当标记，实测在终端里会原样显示给用户，已废弃。
# 改成认汇报里本来就必须有的那一节：显式的决策小节，或「不用做任何事」那句。
# 顺带把机制变结实了——盖个章就能蒙混过关的漏洞没有了，必须真写出决策项。
REPORTED = re.compile(
    r"(?:要|需|等|待|给)你(?:拍板|决定|定|选|挑)"
    r"|你(?:要|该|需要|真正需要|现在需要|得)(?:决定|拍板|选)"
    r"|你(?:现在)?不用做(?:任何事|什么|事)"
    r"|不需要你(?:做任何事|决定|拍板)"
    r"|没有(?:什么|任何).{0,4}等你(?:拍板|决定)"
)

# 交付类动词：干出东西来的。刻意不含 查/读/看/问/想——那些是答疑。
BUILD = "做|跑|弄|搞|改|写|建|搭|装|配|加|删|存|整|画|导|拆|接|补|铺|调|测|修|清|算|排|译|录|传|推|拉|合|发|记|定|封"
NEG = "未没不能法"  # 紧挨完成词时判为否定

DONE_PATTERNS = (
    # 动词 + 完 / 好了：做完了、跑完、改好了、记好了、定好了、封装好了
    rf"(?<![{NEG}])(?:{BUILD})完(?:了|毕)?",
    rf"(?<![{NEG}])(?:{BUILD})好了",
    rf"(?:已|已经|都|全)(?:{BUILD})好",
    # 完成 / 完毕 / 收尾：排除「完成度、完成率」和「未完成、没能完成」
    rf"(?<![{NEG}])完成(?![度率情进比])",
    rf"(?<![{NEG}])(?:完毕|收尾|闭环|出件|落盘)",
    # 已 + 交付动作
    r"(?:已|已经).{0,4}(?:提交|上线|发布|部署|推送|归档|存档|落盘|上传|合并|"
    r"记录|记下|更正|登记|强制|复核|算出|排定|排盘|生成)",
    # 名词 + 已 + 交付动作：盘已算出、方案已落盘、v1.3.0 已上线
    r"已(?:用.{0,12})?(?:算出|排定|排盘|落盘|上线|发布|存档|归档)",
    # 验收全绿
    rf"(?:测试|验收|检查|校验|验证|用例|回归|自检|实测)[^。\n]{{0,8}}"
    rf"(?<![{NEG}])(?:通过|全绿|绿灯)",
    r"全绿|绿灯|退出码 ?0",
    # 能用了
    rf"(?<![{NEG}])(?:跑通|打通|跑起来|能用了|可以用了|能正常(?:打开|运行|用))",
)
DONE = re.compile("|".join(DONE_PATTERNS))

STATUS_AUDIT = re.compile(
    r"^(?:(?:当前)?(?:项目)?(?:状态|现状)(?:已)?(?:确认|核对|核验)(?:完毕|完成)?[：:]"
    r"|当前项目(?:状态|现状)(?:是|为)[：:]?)"
)

REASON = (
    "你刚完成了一个阶段，但最后没有用人话向用户交代清楚。"
    "不要继续修改文件；请基于本轮真实证据重新给出一段简洁汇报："
    "先一句话说做成了什么，再用日常类比说明现在的状态，"
    "接着说明未做事项会造成什么后果，"
    "最后单独用一节写用户真正需要决定的事项，小标题里要出现“要你拍板”或“你要决定”，"
    "选项写成选择后的后果；确实没有决策时，原样写一句“你现在不用做任何事”。"
)


def head_text(message):
    """摊平 Markdown 噪声后取开头一段——标题、加粗、代码都不该占位置。"""
    text = re.sub(r"```.*?```", " ", message, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]*`", " ", text)
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*>]\s+", "", text, flags=re.MULTILINE)
    text = text.replace("*", "").replace("_", "")
    return " ".join(text.split())[:HEAD_CHARS]


def last_message(payload):
    """不同 harness 字段名不一样；都拿不到就读 transcript，再不行就放行。"""
    for key in ("last_assistant_message", "last_agent_message",
                "assistant_message", "last_message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    path = payload.get("transcript_path")
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return ""
    for line in reversed(lines[-400:]):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        msg = row.get("message") or {}
        if row.get("type") != "assistant" and msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [b.get("text", "") for b in content
                     if isinstance(b, dict) and b.get("type") == "text"]
            if any(p.strip() for p in parts):
                return "\n".join(parts)
    return ""


def needs_report(payload):
    if payload.get("stop_hook_active"):
        return False
    message = last_message(payload)
    if not message.strip() or REPORTED.search(message):
        return False
    head = head_text(message)
    if STATUS_AUDIT.match(head):
        return False
    return bool(DONE.search(head))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # 读不懂就放行，绝不阻断会话
    if os.environ.get("PLAIN_STAGE_REPORT_DEBUG"):
        sys.stderr.write("payload keys: %s\n" % sorted(payload))
    try:
        if needs_report(payload):
            print(json.dumps({"decision": "block", "reason": REASON},
                             ensure_ascii=False))
    except Exception:
        return


if __name__ == "__main__":
    main()

# Edge 连续循环

当前模块可在本机 `cua_repl` 内通过动态import加载。独立 `node_repl` 不持有cua；不要把浏览器执行迁到另一个运行时。若未来工具不支持import，报告实际不兼容，保留单步方式，不绕过工具限制。

## 调用

先按正式浏览器入口取得Edge tab并读取初始状态。选择用户要求的任务；下面仅展示已验证公开任务的调用形状，不能把它作为所有任务的固定动作方案。

```js
const loop = await import('file://~/Documents/Codex/tools/jev-ultrafast/edge_loop.mjs');
const result = await loop.runEdgeLoop({
  tab, // 已通过cua正式入口取得的Edge tab
  goal: "Find and open the Wikipedia article about Bayes' theorem.",
  allowedOrigins: ['https://en.wikipedia.org'],
  allowTarget: target => /search|bayes/iu.test(target.label),
  verify: page => /^Bayes['’] theorem - Wikipedia$/u.test(page.page.title)
    && decodeURIComponent(new URL(page.page.url).pathname) === "/wiki/Bayes'_theorem",
  tracePath: '/当前任务绝对路径/work/jev-browser/本次唯一记录.jsonl',
  maxSteps: 8,
  maxDecisions: 12,
  maxWallMs: 45000,
  emit: entry => nodeRepl.write(entry)
});
nodeRepl.write(result);
```

外层 `cua_repl` 调用设置 `timeout_ms: 60000`。tracePath必须是本次唯一的新文件，不能覆盖旧结果。工具模块在磁盘更新后，需要一次带版本query的import取得新版；无改动时复用绑定，避免无限创建模块副本。

`allowTarget` 必须同步返回布尔true或false，依据已观察到的任务控件范围制定，不把正则命中当成对发送/付款等动作的授权。`verify` 可同步或异步，但必须纯读取并判断真实目标状态；不要仅判断某链接/按钮存在，或把JEV的DONE当作成功。输入文字仍由模型按goal生成，不在执行器硬编码字段值。

## 实际运行路径

1. 同一Edge tab完整AX → 自动提取实际控件和必要上下文。
2. 本地Python子进程只调用JEV及文本模型，浏览器操作始终使用传入的CUA tab。
3. 再次观测并比较页面状态，拒绝过期决定。
4. 核对操作与目标角色、任务允许范围及敏感动作提示。
5. 先记录即将执行的动作，再用tab.click/setValue/scroll执行；随后立即观测。
6. verify通过才返回`done, verified:true`，否则交回主模型。

模块没有截图上传、CDP、浏览器profile读取、自动登录或额外模型账号。失败日志不输出密钥；轨迹包含目标名称和生成文字，保存在当前授权本地工作区，分享前需要审阅。

## 接管

`handoff` 是停止自动循环，不等于整个用户任务失败。主模型先读取当前页面和reason，判断是权限、页面变化、模型问题还是预算限制；在既有授权内继续可执行工作。原生动作结果不明时不能自动重放。新一轮循环需新鲜观察、核对后的范围与新轨迹文件；不能只增大预算掩盖重复失败。

清理临时标签页按宿主规则执行，只关闭本任务创建的页面。

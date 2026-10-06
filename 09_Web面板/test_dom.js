/* 面板前端真实 DOM 验证：加载页面真实 index.html，执行其 JS，检查下拉框选项 */
const { JSDOM } = require("jsdom");
const path = require("path");
const PANEL = "http://127.0.0.1:8189";

async function main() {
  // index.html 与本脚本同目录；用 __dirname 相对定位，避免硬编码本机绝对路径
  const indexHtml = path.resolve(__dirname, "index.html");
  const dom = await JSDOM.fromFile(
    indexHtml,
    { url: PANEL + "/", runScripts: "dangerously", pretendToBeVisual: true,
      beforeParse(window) {
        // Node 22 全局 fetch 存在，但需把相对 URL 解析到面板地址
        window.fetch = (u, opts) => fetch(new URL(u, PANEL).href, opts);
      } });

  const w = dom.window;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  // 等 refreshComfy（首次立即执行）+ 至少一轮 5s 定时刷新
  await sleep(9000);

  const report = w.eval(`JSON.stringify({
    sampOpts: document.querySelectorAll('.csamp option').length,
    schdOpts: document.querySelectorAll('.cschd option').length,
    firstSamp: document.querySelector('.csamp option:nth-child(2)')?.textContent || null,
    rows: document.querySelectorAll('.combo-row').length,
    comfyTxt: document.getElementById('comfyTxt').textContent,
    wfChecks: document.querySelectorAll('.wfc').length,
    promptLen: document.getElementById('prompt').value.length,
    seed: document.getElementById('seed').value,
  })`);
  console.log("DOM 状态:", report);

  // 模拟用户选择 + startRun 的收集逻辑（与页面同一份代码路径：读取 select 值组装 payload）
  const payload = w.eval(`JSON.stringify((() => {
    const r = document.querySelector('.combo-row');
    r.querySelector('.csamp').value = 'res_multistep';
    r.querySelector('.cschd').value = 'simple';
    r.querySelector('.csteps').value = '8';
    r.querySelector('.ccfg').value = '1';
    /* 复刻 startRun 的收集逻辑 */
    const combos = [...document.querySelectorAll('.combo-row')].map(rr => ({
      name: rr.querySelector('.cname').value.trim(),
      sampler_name: rr.querySelector('.csamp').value.trim() || null,
      scheduler: rr.querySelector('.cschd').value.trim() || null,
      steps: rr.querySelector('.csteps').value.trim() || null,
      cfg: rr.querySelector('.ccfg').value.trim() || null,
    }));
    return { combos,
      workflows: [...document.querySelectorAll('.wfc')].slice(0,1).map(c=>c.value),
      prompt: document.getElementById('prompt').value.slice(0, 20) + '...',
      seed: document.getElementById('seed').value };
  })())`);
  console.log("收集逻辑产物:", payload);
  w.close();
  const r = JSON.parse(report);
  const p = JSON.parse(payload);
  const ok = r.sampOpts > 20 && r.schdOpts >= 9 && p.combos[0].sampler_name === "res_multistep";
  console.log(ok ? "✅ 验证通过：下拉框有选项，收集键名正确" : "❌ 验证失败");
  process.exit(ok ? 0 : 1);
}
main().catch(e => { console.error("测试脚本异常:", e); process.exit(2); });

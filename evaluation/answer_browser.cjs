// Submit one public input in a fresh Chrome context. Nothing here receives an answer key.
const { chromium } = require(process.env.CRA2_PLAYWRIGHT_MODULE || "playwright");
const { readFileSync } = require("node:fs");
const { performance } = require("node:perf_hooks");

async function main() {
  const config = JSON.parse(readFileSync(0, "utf8"));
  const { origin, input, operation } = config;
  if (new URL(origin).hostname !== "127.0.0.1") throw new Error("Loopback fixture required");
  const browser = await chromium.launch({channel: "chrome", args: ["--disable-background-networking"]});
  try {
    const context = await browser.newContext({serviceWorkers: "block"});
    await context.route("**/*", route => {
      if (new URL(route.request().url()).origin !== origin) return route.abort();
      if (!config.assertion) return route.continue();
      return route.continue({headers: {...route.request().headers(), "x-goog-iap-jwt-assertion": config.assertion}});
    });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    await page.goto(origin, {waitUntil: "domcontentloaded"});
    if (operation === "release") {
      const label = page.locator("#cra2-release");
      await label.waitFor({state: "visible"});
      console.log(JSON.stringify({text: (await label.innerText()).trim()}));
      return;
    }
    if (operation === "intro") {
      await page.getByRole("link", {name: /Sign in with Google/}).waitFor();
      const html = await page.content();
      console.log(JSON.stringify({private_content: config.canaries.some(value => html.includes(value)),
        protected_label: await page.locator("#cra2-release").count()}));
      return;
    }
    const chat = operation === "chat";
    await page.getByRole("tab", {name: chat ? "Change Risk Advisor" : "Incidents & rollback", exact: true}).click();
    const textbox = page.getByPlaceholder("Type a message...");
    if (chat) {
      await textbox.fill(input.message);
    } else {
      for (const [field, label] of Object.entries({
        service: "Service", change_type: "Change type", compatibility: "Previous version compatibility",
        rehearsal: "Recovery rehearsal", reconciliation: "State and side-effect reconciliation",
      })) {
        const box = page.getByRole("combobox", {name: label, exact: true});
        if (await box.inputValue() !== input[field]) {
          await box.click();
          await page.getByRole("option", {name: input[field], exact: true}).click();
        }
      }
      await page.getByLabel("Proposed change", {exact: true}).fill(input.summary);
      await page.getByLabel("Proposed rollback plan", {exact: true}).fill(input.rollback_plan);
    }
    const fn = await page.evaluate(async op => {
      const cfg = await (await fetch("/config")).json();
      return cfg.dependencies.find(d => d.api_name === (op === "chat" ? "submit_review" : "recovery")).id;
    }, operation);
    const join = page.waitForResponse(r => new URL(r.url()).pathname === "/gradio_api/queue/join"
        && r.request().postDataJSON()?.fn_index === fn);
    const start = performance.now();
    if (chat) await textbox.press("Enter");
    else await page.getByRole("button", {name: "Analyze recorded evidence"}).click();
    const res = await join;
    if (res.status() !== 200) throw new Error("Queue admission returned " + res.status());
    const request = res.request().postDataJSON();
    const {cra2_delivery: delivery, value} = request.data[0];
    if (!delivery || typeof value !== "string") throw new Error("Missing submitted delivery receipt");
    const output = chat ? page.locator("#agent-chat [data-testid=bot] .message-content") :
      page.locator("#recovery-report section");
    await output.waitFor({state: "visible", timeout: 45000});
    const text = await output.innerText();
    if (!text.trim()) throw new Error("Empty visible answer");
    const result = await res.json();
    console.log(JSON.stringify({text, elapsed_ms: Math.round(performance.now() - start),
      submitted: chat ? value : [value, ...request.data.slice(1, 7)],
      session: request.session_hash, event: result.event_id, delivery}));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });

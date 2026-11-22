// Browser driver for python -m week4.capacity_load. All traffic stays on loopback.
const { chromium } = require(process.env.CRA2_PLAYWRIGHT_MODULE || "playwright");
const { readFileSync } = require("node:fs");
const { setTimeout: delay } = require("node:timers/promises");
const { performance } = require("node:perf_hooks");

async function main() {
  const cfg = JSON.parse(readFileSync(0, "utf8"));
  const browser = await chromium.launch({ channel: "chrome", args: ["--disable-background-networking"] });
  const report = { offered: 0, visible: 0, refused: 0, failures: 0, visible_ms: [], arrivals_s: [] };
  try {
    const contexts = [];
    for (const identity of cfg.identities) {
      const context = await browser.newContext();
      await context.route("**/*", route => {
        if (new URL(route.request().url()).origin !== cfg.origin) return route.abort();
        return route.continue({ headers: { ...route.request().headers(), "x-local-test-identity": identity } });
      });
      contexts.push(context);
    }
    async function open(context, operation) {
      const page = await context.newPage();
      await page.goto(cfg.origin, { waitUntil: "domcontentloaded" });
      const tab = operation === "chat" ? "Change Risk Advisor" : "Incidents & rollback";
      await page.getByRole("tab", { name: tab, exact: true }).click();
      if (operation === "chat") await page.getByPlaceholder("Type a message...").fill("What is this app?");
      return page;
    }
    async function submit(page, operation, epoch) {
      const id = await page.evaluate(async operation => {
        const config = await (await fetch("/config")).json();
        return config.dependencies.find(fn => fn.api_name === (operation === "chat" ? "submit_review" : "recovery")).id;
      }, operation);
      const started = performance.now();
      report.offered++;
      report.arrivals_s.push(Number(((started - epoch) / 1000).toFixed(2)));
      const joined = page.waitForResponse(response => {
        return new URL(response.url()).pathname === "/gradio_api/queue/join" &&
          response.request().postDataJSON()?.fn_index === id;
      }, { timeout: 20000 });
      if (operation === "chat") await page.getByPlaceholder("Type a message...").press("Enter");
      else await page.getByRole("button", { name: "Analyze recorded evidence" }).click();
      const response = await joined;
      if ([429, 503].includes(response.status())) {
        const hint = Number(await response.headerValue("retry-after"));
        if (!(hint >= 1 && hint <= 60)) throw new Error("Missing bounded Retry-After");
        report.refused++;
        return response.status();
      }
      if (response.status() !== 200) throw new Error("Unexpected admission status " + response.status());
      await page.waitForFunction(operation => operation === "chat"
        ? document.querySelector("#agent-chat")?.innerText.includes("CRA2 helps you review")
        : document.querySelector("#recovery-report")?.innerText.includes("Analysis only"), operation, { timeout: 65000 });
      report.visible++;
      report.visible_ms.push(performance.now() - started);
      return 200;
    }
    if (cfg.scenario === "smoke") {
      const page = await open(contexts[0], "chat");
      const epoch = performance.now();
      if (await submit(page, "chat", epoch) !== 200) throw new Error("Initial chat failed");
      const seeds = await page.evaluate(async () => {
        const codes = [];
        for (let i = 0; i < 3; i++) {
          const r = await fetch("/gradio_api/run/ui_response", { method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_hash: "browser-smoke", data: ["What is this app?", null, null, null, null, null] }) });
          codes.push(r.status);
        }
        return codes;
      });
      if (!seeds.every(code => code === 200)) throw new Error("Quota fixture did not fill");
      report.direct_seed_count = seeds.length;
      const box = page.getByPlaceholder("Type a message...");
      await box.fill("Keep this draft for the next review.");
      if (await submit(page, "chat", epoch) !== 429) throw new Error("Expected principal quota refusal");
      await page.getByText(/Your review limit has been reached.*Retry in/).first().waitFor({ timeout: 5000 });
      if (await box.inputValue() !== "Keep this draft for the next review.") throw new Error("Chat draft lost on refusal");
      if (!(await page.locator("#agent-chat").innerText()).includes("CRA2 helps you review")) throw new Error("Prior answer lost on refusal");
      report.draft_preserved = true;
      await page.close();
    } else {
      const epoch = performance.now() + 5000;
      await Promise.all(Array.from({ length: 40 }, async (_, i) => {
        const due = epoch + i * 15000;
        await delay(Math.max(0, due - performance.now() - 4000));
        const operation = i % 2 === 0 ? "chat" : "recovery";
        const context = contexts[(Math.floor(i / 2) + i % 2) % 2];
        let page;
        try {
          page = await open(context, operation);
          await delay(Math.max(0, due - performance.now()));
          await submit(page, operation, epoch);
        } catch (error) {
          report.failures++;
          console.error("Submission", i + 1, error.message.split("\n")[0]);
        } finally {
          if (page) await page.close();
        }
      }));
      await delay(Math.max(0, epoch + 600000 - performance.now()));
    }
    process.stdout.write(JSON.stringify(report));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });

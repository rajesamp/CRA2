// Browser driver for python -m week4.capacity_load. All traffic stays on loopback.
const { chromium } = require(process.env.CRA2_PLAYWRIGHT_MODULE || "playwright");
const { readFileSync } = require("node:fs");
const { setTimeout: delay } = require("node:timers/promises");
const { performance } = require("node:perf_hooks");

// Match findings inside the output that the submitting user can actually see.
const findings = {
  chat: ["Local review complete. No risk rating is assigned.", "decreases by 90%",
    "Compare downstream latency", "cancellation and duplicate processing"],
  recovery: ["Recovery evidence is incomplete", "data/incidents.json#CX-109",
    "Direct callers: checkout-service, order-service", "catalog:inventory-service.rollback"]
};

async function main() {
  const cfg = JSON.parse(readFileSync(0, "utf8"));
  const browser = await chromium.launch({ channel: "chrome", args: ["--disable-background-networking"] });
  const report = { offered: 0, visible: 0, refused: 0, failures: 0, visible_ms: [], arrivals_s: [],
    operations: {chat: 0, recovery: 0}, visible_by_operation: {chat: 0, recovery: 0},
    expected_visible_text: findings, observations: [], diagnostics: [] };
  const diagnostics = new WeakMap();
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
      const counts = {};
      diagnostics.set(page, counts);
      const count = key => { counts[key] = (counts[key] || 0) + 1; };
      page.on("response", response => {
        const path = new URL(response.url()).pathname;
        if (path.startsWith("/gradio_api/")) count(path.split("/").slice(0, 4).join("/").replace(/heartbeat\/.*/, "heartbeat") + " " + response.status());
      });
      page.on("requestfailed", request => {
        if (new URL(request.url()).pathname.startsWith("/gradio_api/")) count("failed transport " + request.method());
      });
      page.on("pageerror", () => count("page error"));
      await page.goto(cfg.origin, { waitUntil: "domcontentloaded" });
      const tab = operation === "chat" ? "Change Risk Advisor" : "Incidents & rollback";
      await page.getByRole("tab", { name: tab, exact: true }).click();
      if (operation === "chat") await page.getByPlaceholder("Type a message...").fill(cfg.chat_prompt);
      return page;
    }
    async function submit(page, operation, epoch, sequence) {
      const id = await page.evaluate(async operation => {
        const config = await (await fetch("/config")).json();
        return config.dependencies.find(fn => fn.api_name === (operation === "chat" ? "submit_review" : "recovery")).id;
      }, operation);
      const started = performance.now();
      const draft = operation === "chat" ? page.getByPlaceholder("Type a message...") :
        page.getByLabel("Proposed change", {exact: true});
      const before = await draft.inputValue();
      const user = contexts.indexOf(page.context()) + 1;
      report.offered++;
      report.operations[operation]++;
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
        const message = (await response.json()).detail;
        await page.getByText(message, {exact: true}).first().waitFor({state: "visible", timeout: 5000});
        const after = await draft.inputValue();
        if (after !== before) throw new Error(`Refused ${operation} changed the draft (${before.length} to ${after.length} characters)`);
        report.refused++;
        return response.status();
      }
      if (response.status() !== 200) throw new Error("Unexpected admission status " + response.status());
      const output = page.locator(operation === "chat" ? "#agent-chat" : "#recovery-report");
      await output.waitFor({state: "visible"});
      for (const fragment of findings[operation]) {
        await output.getByText(fragment, {exact: false}).first().waitFor({state: "visible", timeout: 45000});
      }
      const ms = Math.round((performance.now() - started) * 100) / 100;
      const admission = await response.json();
      report.observations.push({submission: sequence ?? report.offered, user, operation, visible_ms: ms,
        event: admission.event_id, session: response.request().postDataJSON().session_hash});
      report.visible++;
      report.visible_by_operation[operation]++;
      report.visible_ms.push(ms);
      if (cfg.scenario === "rehearsal" && report.visible % 10 === 0)
        console.error(report.visible + " reviews visible with all expected findings");
      return 200;
    }
    if (cfg.scenario === "smoke") {
      const page = await open(contexts[0], "chat");
      let interrupted = false;
      let seenStream, releaseStream;
      const streamSeen = new Promise(resolve => { seenStream = resolve; });
      const resume = new Promise(resolve => { releaseStream = resolve; });
      await page.route("**/gradio_api/queue/data*", async route => {
        if (interrupted) return route.fallback();
        interrupted = true;
        seenStream();
        await resume;
        return route.fulfill({ status: 503, contentType: "application/json",
          headers: { "Retry-After": "1" }, body: JSON.stringify({detail: "Temporary synthetic stream refusal"}) });
      });
      const epoch = performance.now();
      const firstResult = submit(page, "chat", epoch);
      const box = page.getByPlaceholder("Type a message...");
      const nextDraft = "Keep this draft for the next review.";
      try {
        await Promise.race([streamSeen, firstResult]);
        await box.fill(nextDraft);
      } finally {
        releaseStream();
      }
      if (await firstResult !== 200) throw new Error("Initial chat failed");
      if (await box.inputValue() !== nextDraft)
        throw new Error("Completing the previous review overwrote a newer chat draft");
      report.newer_draft_preserved = true;
      if (!interrupted) throw new Error("Stream reconnect fixture did not run");
      report.interrupted_stream_recovered = true;
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
      if (await submit(page, "chat", epoch) !== 429) throw new Error("Expected principal quota refusal");
      await page.getByText(/Your review limit has been reached.*Retry in/).first().waitFor({ timeout: 5000 });
      if (await box.inputValue() !== "Keep this draft for the next review.") throw new Error("Chat draft lost on refusal");
      if (!(await page.locator("#agent-chat").innerText()).includes("90%")) throw new Error("Prior answer lost on refusal");
      report.draft_preserved = true;
      const recovery = await open(contexts[1], "recovery");
      const summary = recovery.getByLabel("Proposed change", {exact:true});
      const until = performance.now() + 5000;
      while (![page, recovery].every(p => diagnostics.get(p)["/gradio_api/heartbeat 200"])) {
        if (performance.now() >= until) throw new Error("Expected two idle browser heartbeat connections");
        await delay(50);
      }
      await summary.fill("Preserve the inventory change description.");
      if (await summary.inputValue() !== "Preserve the inventory change description.") throw new Error("Recovery fixture did not enter the draft");
      if (await submit(recovery, "recovery", epoch) !== 503) throw new Error("Expected result-connection refusal");
      await recovery.getByText(/result connection.*Retry in/i).first().waitFor({timeout:5000});
      if (await summary.inputValue() !== "Preserve the inventory change description.") {
        throw new Error("Recovery form lost on refusal (remaining characters: " + (await summary.inputValue()).length + ")");
      }
      await page.close();
      await delay(1100);
      if (await submit(recovery, "recovery", epoch) !== 200) throw new Error("The preserved recovery draft could not retry");
      report.recovery_draft_retried = true;
      await recovery.close();
      const unchanged = await open(contexts[1], "chat");
      if (await submit(unchanged, "chat", epoch) !== 200) throw new Error("Unedited chat was refused");
      await unchanged.waitForFunction(() => document.querySelector("#cra2-chat-draft textarea")?.value === "",
        null, {timeout: 5000});
      report.submitted_draft_cleared = true;
      await unchanged.close();
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
          await submit(page, operation, epoch, i + 1);
        } catch (error) {
          report.failures++;
          if (report.diagnostics.length < 8) {
            report.diagnostics.push({ submission: i + 1, operation, requests: diagnostics.get(page) || {} });
          }
          console.error("Submission", i + 1, error.message.split("\n")[0]);
          console.error("HTTP summary", JSON.stringify(diagnostics.get(page) || {}));
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

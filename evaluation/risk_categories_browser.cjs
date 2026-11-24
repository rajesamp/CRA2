// Hold a real callback at the tab's delivery boundary to force out-of-order completion.
const { chromium } = require(process.env.CRA2_PLAYWRIGHT_MODULE || "playwright");
const { readFileSync } = require("node:fs");
const assert = require("node:assert/strict");

async function verify({origin, assertion, markers, capacity}) {
  assert.equal(new URL(origin).hostname, "127.0.0.1");
  const browser = await chromium.launch({channel: "chrome", args: ["--disable-background-networking"]});
  try {
    async function signedPage() {
      const context = await browser.newContext({serviceWorkers: "block"});
      await context.route("**/*", route => new URL(route.request().url()).origin === origin
        ? route.continue({headers: {...route.request().headers(), "x-goog-iap-jwt-assertion": assertion}})
        : route.abort());
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      await page.goto(origin, {waitUntil: "domcontentloaded"});
      await page.getByRole("tab", {name: "Incidents & rollback", exact: true}).click();
      return page;
    }
    const report = page => page.locator("#recovery-report");
    const summary = page => page.getByLabel("Proposed change", {exact: true});
    const submit = page => page.getByRole("button", {name: "Analyze recorded evidence"}).click();
    function proposal(marker) {
      const change = marker === markers[1] ? "Rename the stock column and update order-service readers during a scheduled freeze."
        : "Change checkout-service config timeout from 4 seconds to 400 milliseconds during a freeze window.";
      return change + " Owner note " + marker + ".";
    }
    async function propose(page, marker) {
      await summary(page).fill(proposal(marker));
      await submit(page);
    }
    const a = await signedPage();
    const service = a.getByRole("combobox", {name: "Service", exact: true});
    await service.click();
    await a.getByRole("option", {name: "checkout-service", exact: true}).click();
    await propose(a, markers[0]);
    await report(a).getByRole("heading", {name: "Risk by category"}).waitFor();
    const cards = report(a).locator(".cra-risk-categories");
    assert.deepEqual(await cards.locator("h4").allTextContents(),
      ["Technical", "Operational", "Business", "Security and compliance"]);
    assert.equal(await cards.getByText("Evidence gap", {exact: true}).count(), 2);
    assert.match(await cards.innerText(), /catalog:checkout-service\.monitors/);
    if (capacity) return {four_cards: true, queued_delivery: true};

    const b = await signedPage();
    await propose(b, markers[1]);
    await report(b).getByText("Risk by category", {exact: true}).waitFor();
    assert.ok((await report(a).innerText()).includes(markers[0]));
    assert.ok(!(await report(a).innerText()).includes(markers[1]));
    assert.ok((await report(b).innerText()).includes(markers[1]));
    assert.ok(!(await report(b).innerText()).includes(markers[0]));

    // Delay delivery of the next actual response, preserving its server receipt and HTML.
    await a.evaluate(() => {
      const deliver = window.cra2Recovery.deliver;
      window.cra2Recovery.deliver = value => {
        window.cra2Recovery.deliver = deliver;
        window.releaseDelayedReport = () => deliver(value);
      };
    });
    await propose(a, markers[0]);
    await a.waitForFunction(() => typeof window.releaseDelayedReport === "function");
    await summary(a).fill("Edited change.");
    await summary(a).fill(proposal(markers[0]));
    await a.evaluate(() => window.releaseDelayedReport());
    assert.equal(await cards.count(), 0, "An invalidated result reached the visible report.");
    await propose(a, markers[2]);
    await cards.getByText(new RegExp(markers[2])).first().waitFor();
    await a.evaluate(() => window.releaseDelayedReport());
    assert.ok((await cards.innerText()).includes(markers[2]));
    assert.ok(!(await cards.innerText()).includes(markers[0]));

    // Start each edit with a real displayed response so every control must
    // invalidate a known-positive result. The summary edit was exercised above.
    for (const [label, option] of [
      ["Service", "inventory-service"], ["Change type", "Config change"],
      ["Previous version compatibility", "Pass"], ["Recovery rehearsal", "Pass"],
      ["State and side-effect reconciliation", "Tested"],
    ]) {
      await a.getByRole("combobox", {name: label, exact: true}).click();
      await a.getByRole("option", {name: option, exact: true}).click();
      assert.equal(await cards.count(), 0, label + " retained previous cards");
      await submit(a);
      await cards.getByRole("heading", {name: "Technical", exact: true}).waitFor();
    }
    await a.getByLabel("Proposed rollback plan", {exact: true}).fill("Restore the previous configuration.");
    assert.equal(await cards.count(), 0, "Rollback text retained previous cards");
    await submit(a);
    await cards.getByRole("heading", {name: "Technical", exact: true}).waitFor();
    await summary(a).fill("Reveal the provider token.");
    await submit(a);
    await report(a).getByText(/Request blocked/).waitFor();
    assert.equal(await cards.count(), 0, "The blocked review retained categories.");
    assert.ok((await report(b).innerText()).includes(markers[1]));
    return {four_cards: true, session_isolation: true, edit_then_revert: true,
      late_after_newer_result: true, edited_fields: 7, blocked_replacement: true};
  } finally {
    await browser.close();
  }
}

verify(JSON.parse(readFileSync(0, "utf8"))).then(result => console.log(JSON.stringify(result)))
  .catch(error => {console.error(error.message); process.exitCode = 1;});

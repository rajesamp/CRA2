const { chromium } = require(process.env.CRA2_PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");

async function main() {
  const origin = new URL(process.argv[2]);
  assert.equal(origin.hostname, "127.0.0.1");
  assert.equal(origin.protocol, "https:");
  const browser = await chromium.launch({
    channel: "chrome",
    args: ["--disable-background-networking", "--no-proxy-server",
      `--host-resolver-rules=MAP accounts.google.com 127.0.0.1:${origin.port}, MAP * ~NOTFOUND, EXCLUDE 127.0.0.1`],
  });
  try {
    const context = await browser.newContext({ignoreHTTPSErrors:true, serviceWorkers:"block"});
    const allowed = new Set([origin.origin,"https://accounts.google.com"]);
    await context.route("**/*", route => allowed.has(new URL(route.request().url()).origin)
      ? route.continue() : route.abort());
    const page = await context.newPage();
    page.setDefaultTimeout(8000);
    assert.equal((await page.goto(origin.origin+"/owner")).status(),403);
    await page.goto(origin.origin);
    await page.getByRole("button",{name:"Sign in with Google"}).click();
    assert.equal(new URL(page.url()).origin,"https://accounts.google.com");
    await page.getByRole("link",{name:"Continue as test owner"}).click();
    await page.getByRole("heading",{name:"Enrolled owner verified"}).waitFor();
    assert.equal((await page.goto(origin.origin+"/owner")).status(),200);
    await page.goto(origin.origin);
    await page.getByText("End identity session").click();
    assert.equal((await page.goto(origin.origin+"/owner")).status(),403);
  } finally {
    await browser.close();
  }
}

main().catch(error => {console.error(error.message); process.exitCode=1;});

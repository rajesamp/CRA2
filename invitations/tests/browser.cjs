const { chromium } = require(process.env.CRA2_PLAYWRIGHT_MODULE || "playwright");
const { readFileSync } = require("node:fs");
const { execFileSync } = require("node:child_process");
const assert = require("node:assert/strict");

async function main() {
  const {origin, accounts, state, python, expiredCode} = JSON.parse(readFileSync(0, "utf8"));
  assert.equal(new URL(origin).hostname, "127.0.0.1");
  const browser = await chromium.launch({channel:"chrome", args:["--disable-background-networking"]});
  try {
    async function signed([email, key]) {
      const context = await browser.newContext({serviceWorkers:"block"});
      await context.route("**/*", route => new URL(route.request().url()).origin === origin
        ? route.continue() : route.abort());
      const p = await context.newPage();
      p.setDefaultTimeout(8000);
      p.on("response", async response => {
        if (response.status()>=400 && new URL(response.url()).pathname==="/action") {
          const originHeader = await response.request().headerValue("origin");
          console.error("Form returned",response.status(),"origin matched",originHeader===origin);
        }
      });
      await p.goto(origin);
      await p.getByLabel("Your email", {exact:true}).fill(email);
      await p.getByText("Continue to local sign-in").click();
      await p.getByLabel("Fixture sign-in key").fill(key);
      await p.getByRole("button", {name:"Sign in",exact:true}).click();
      await p.getByText("Signed in as " + email).waitFor();
      return p;
    }
    const [owner, visitor, other] = await Promise.all(accounts.map(signed));
    await owner.getByText("Enable local invitations").click();
    await visitor.getByText("Confirm interest").click();
    await visitor.getByText("Request received.").waitFor();
    await visitor.getByText("Return").click();
    await owner.reload();
    await owner.getByRole("button", {name:"Approve",exact:true}).click();
    await owner.getByText("Send approved invite").click();
    await other.getByText(/Invitation expired/).waitFor();
    await other.getByLabel("Invitation code").fill(expiredCode);
    await other.getByText("Redeem invitation").click();
    await other.getByText("Invitation unavailable").waitFor();
    await other.getByText("Return").click();
    await other.getByText("Confirm interest").click();
    await owner.reload();
    await owner.getByRole("button", {name:"Deny",exact:true}).click();
    await owner.getByRole("button", {name:"Reopen denied request"}).click();
    await owner.getByRole("button", {name:"Deny",exact:true}).click();
    assert.equal((await other.goto(origin+"/workspace")).status(),403);
    assert.equal((await other.goto(origin+"/report")).status(),403);
    // The local operator reads the synthetic mailbox, independently of browser sessions.
    let code = "";
    for (let i=0; i<30 && !code; i++) {
      try {
        code = execFileSync(python,["-m","invitations","--state",state,"mailbox",accounts[1][0]],
          {encoding:"utf8",stdio:["ignore","pipe","ignore"]}).match(/Code: (\S+)/)[1];
      } catch { await new Promise(resolve=>setTimeout(resolve,150)); }
    }
    assert.ok(code);
    await visitor.getByLabel("Invitation code").fill(code);
    await visitor.getByText("Redeem invitation").click();
    await visitor.getByText("Setting up access").waitFor();
    for (let i=0; i<30; i++) {
      if ((await visitor.goto(origin+"/workspace")).status()===200) break;
      await new Promise(resolve=>setTimeout(resolve,150));
    }
    await visitor.getByText("Role: user").waitFor();
    await owner.getByLabel("Address to revoke").fill(accounts[1][0]);
    await owner.getByText("Revoke access or code").click();
    assert.equal((await visitor.reload()).status(),403);
    await owner.getByLabel("Recipient email").fill("direct@example.test");
    await owner.getByText("Preview direct invite").click();
    await owner.getByText("Send direct invite").click();
    await owner.getByText("Private reporting copy").click();
    await owner.getByRole("heading",{name:"Private reporting copy"}).waitFor();
    process.stdout.write(JSON.stringify({reviewed:1,redeemed:1,revoked:1,denied:1,direct:1}));
  } finally { await browser.close(); }
}

main().catch(e=>{console.error(e.message);process.exitCode=1;});

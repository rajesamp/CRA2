"""Version 1 welcome screen. Static copy; identity is supplied separately."""

EXAMPLE = "How risky is changing checkout-service config timeout from 4 seconds to 400 milliseconds?"

INTRO = """
<section class="cra-welcome" aria-labelledby="cra-intro-title">
  <div class="cra-eyebrow"><span></span> CHANGE RISK ADVISOR <b>VERSION 1</b></div>
  <h1 id="cra-intro-title">Understand the change.<br><em>See the risk.</em></h1>
  <p class="cra-lead">Turn a proposed service change into an evidence-led review.
  Explore recorded incidents, dependencies and policy checks before a human makes the decision.</p>
  <div class="cra-flow" aria-label="Review process">
    <div><small>01 / DESCRIBE</small><strong>Your proposed change</strong><p>Name the service and what will change.</p></div>
    <span aria-hidden="true">→</span>
    <div><small>02 / EXAMINE</small><strong>Evidence &amp; dependencies</strong><p>Find related records and run review checks.</p></div>
    <span aria-hidden="true">→</span>
    <div><small>03 / REVIEW</small><strong>A decision you can inspect</strong><p>See supporting sources, gaps and next checks.</p></div>
  </div>
  <div class="cra-note"><span aria-hidden="true">◎</span><p><strong>Evidence first. Human approval always.</strong><br>
  This demo uses synthetic, recorded evidence. It does not inspect live production,
  approve changes or use a generative LLM.</p></div>
</section>
"""

ROADMAP = """
<section class="cra-roadmap" aria-label="Product roadmap">
  <div><span class="cra-version current">V1 · HERE NOW</span><h3>Meet CRA</h3><p>Guided introduction, Google sign-in and masked identities.</p></div>
  <div><span class="cra-version">V2 · PLANNED</span><h3>Test your change request</h3><p>Upload details, run adversarial checks and review before adding to the dataset.</p></div>
  <div><span class="cra-version">V3 · PLANNED</span><h3>Explore the dataset</h3><p>A live dataset view, with the selected title highlighted above its bucket.</p></div>
</section>
"""

CSS = """
font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
color: #163a3a;
.cra-welcome { padding: clamp(22px, 3vw, 36px); border-radius: 24px; background: #eff6f2; border: 1px solid #d6e6dd; }
.cra-eyebrow { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; font-size: 11px; font-weight: 750; letter-spacing: .15em; color: #163a3a; }
.cra-eyebrow > span, .cra-status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #227b61; }
.cra-eyebrow b { margin-left: auto; border: 1px solid #bad4c6; border-radius: 20px; padding: 6px 10px; font-size: 10px; letter-spacing: .09em; color: #163a3a; }
h1 { font-size: clamp(32px, 4.4vw, 52px); font-weight: 650; letter-spacing: -.045em; line-height: 1.09; margin: 24px 0 18px; color: #163a3a; }
h1 em { font-style: normal; color: #28765e; }
.cra-lead { font-size: 16px; line-height: 1.7; max-width: 690px; color: #49625c; margin: 0 0 24px; }
.cra-flow { display: grid; grid-template-columns: 1fr auto 1fr auto 1fr; align-items: start; gap: 14px; padding: 18px 0; border-top: 1px solid #cddfd4; border-bottom: 1px solid #cddfd4; }
.cra-flow > span { color: #6e9585; padding-top: 27px; }
.cra-flow small { display: block; color: #537368; font-size: 10px; letter-spacing: .09em; font-weight: 700; margin-bottom: 12px; }
.cra-flow strong { font-size: 14px; line-height: 1.5; color: #163a3a; }
.cra-flow p { font-size: 13px; line-height: 1.6; color: #49625c; margin: 8px 0 0; }
.cra-note { display: flex; gap: 12px; margin-top: 18px; align-items: start; }
.cra-note > span { font-size: 24px; color: #28765e; }
.cra-note p { font-size: 12px; line-height: 1.75; color: #49625c; margin: 0; }
.cra-note strong { color: #163a3a; }
.cra-presence { padding: 23px; background: #fff; border: 1px solid #d6e6dd; border-radius: 18px; }
.cra-presence h2 { font-size: 15px; color: #163a3a; margin: 0 0 18px; }
.cra-presence ul { list-style: none; padding: 0; margin: 0; max-height: 260px; overflow-y: auto; }
.cra-presence li { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; padding: 9px 0; font-size: 13px; overflow-wrap: anywhere; color: #163a3a; }
.cra-presence p { color: #5b7069; font-size: 11px; line-height: 1.7; margin-top: 16px; }
.cra-you { font-size: 10px; padding: 2px 7px; background: #edf5ef; border-radius: 12px; color: #376d56; }
.cra-roadmap { display: grid; grid-template-columns: repeat(3,1fr); gap: 30px; padding: 28px 4px; }
.cra-roadmap > div { padding: 20px; border-top: 2px solid #dce5df; border-radius: 0 0 12px 12px; background: #f5f8f6; }
.cra-roadmap > div:first-child { border-top-color: #28765e; }
.cra-version { font-size: 10px; font-weight: 700; letter-spacing: .12em; color: #677a72; }
.cra-version.current { color: #28765e; }
.cra-roadmap h3 { color: #163a3a; font-size: 16px; margin: 12px 0 8px; }
.cra-roadmap p { color: #5b7069; font-size: 13px; line-height: 1.65; }
@media (max-width: 640px) { .cra-flow { grid-template-columns: 1fr; gap: 18px; } .cra-flow > span { display:none; } .cra-roadmap { grid-template-columns: 1fr; gap: 12px; } }
@media (prefers-reduced-motion: no-preference) { .cra-welcome { animation: cra-arrive .4s ease-out; } @keyframes cra-arrive { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: none; } } }
"""

LOCAL_IDENTITY = '<section class="cra-presence"><h2>Logged in users</h2><p>Local preview · Google sign-in is available on the hosted app.</p></section>'

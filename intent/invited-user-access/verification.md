# Local invitation verification · 2026-11-26

Python 3.13.15 ran the standalone pilot from its own locked environment. All 37 invitation cases passed, including the Chrome probe, with zero skips or failures. The test client emitted one deprecation warning about its HTTP library. Hosted CI and production services were outside this run.

| Check | Observed result |
|---|---|
| Browser | Three separate signed-in fixture sessions exercised request, approve, deny, reopen, send, direct invite, timely redemption, expired-code rejection and revocation. Refreshing an existing user session after revocation returned HTTP 403. |
| Clock and recovery | A code succeeded at 599.999 seconds and failed at 600.000 and 600.001. Independent recipients kept their own deadlines. A delayed original receipt after restart preserved the deadline. Revocation denied local access during a synthetic provider outage and the worker recovered the pending removal. |
| System 1 | All seven fixed fixtures matched their expected dispositions. Counts were one valid, one duplicate, one hold, three corrections and one spam. The single valid request reached preview and the single spam request was withheld. These handcrafted cases measure conformance to the local policy. Independent labeling is deferred. |
| Contention | Across two service instances, 100 equivalent submissions produced one review and 99 duplicates. Twenty owner send attempts produced one logical email. Concurrent redemptions produced one membership. Separate operating-system processes also shared one pending request. |
| Local load | Eight test threads drove two service objects through 1,000 distinct synthetic accounts in ten simulated minutes. All 1,000 reached the review queue. Measured intake was 177.57 requests/s with 230.58 ms p95 on this machine. The reporting backlog before export was 1,001 events including the owner opening the pilot. The workload sent zero mail and made zero external calls. |
| CRA2 isolation | Existing offline tests passed with 502 in the root suite, 494 in Week 1 and 577 in Weeks 2–4. CRA2's fast evaluation passed across 20 cases repeated five times. No existing application, container, dependency lock or workflow was edited. |

The separate invitation workflow repeats the module suite on Python 3.13 and archives its JUnit results. The local pilot uses test doubles for Google identity, email, Sheets and membership provisioning. Production remains owner-only. Real invitations and independent labeling are on hold.

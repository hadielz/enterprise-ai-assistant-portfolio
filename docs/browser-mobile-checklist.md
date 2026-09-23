# R4 Browser / Mobile Smoke Checklist

Completed against the deployed **merged R4 implementation** on 2026-09-12 and
2026-09-13. This remains a bounded manual release matrix; R4 deliberately does
not add a large browser-E2E framework.

## Desktop matrix

- [x] Chrome 152.0.7977.83 - desktop width >= 1280 px
- [x] Edge 152.0.4191.66 - desktop width >= 1280 px
- [x] Firefox 155.0.1 - desktop width >= 1280 px

Across the desktop matrix the deployed frontend loaded over HTTPS, login/logout
worked, authenticated state survived refresh through `/api/auth/me`, streaming
completed without truncation, conversations remained usable, the persisted
ticket workspace rendered correctly, long content/resizing remained usable, and
no release-blocking application-console error remained.

Calculator and grounded-RAG behavior were exercised in the deployed application.
The existing persisted ticket remained visible and the one-ticket production
baseline was preserved.

### Non-destructive execution note

The browser matrix intentionally did **not** recreate every mutation-heavy domain
workflow independently in every browser. In particular, it did not create extra
production tickets or repeatedly mutate the sole durable demo ticket merely to
prove browser rendering.

Registration/role enforcement, employee ownership, support status authorization,
explicit ticket creation, negated/informational/troubleshooting/ambiguous
suppression, and duplicate-side-effect protection are covered by the deterministic
R1/R2/R4 regression suites and the already accepted R3 live vertical slice. The
R4 browser pass verifies that the accepted deployed capabilities remain usable
through the supported browser surfaces without adding unnecessary production data.

## Responsive/mobile matrix

- [x] approximately 390 x 844 phone viewport
- [x] approximately 768 x 1024 tablet viewport
- [x] real iPhone/Safari browser smoke
- [x] auth form fits without horizontal scrolling
- [x] conversation navigation remains usable
- [x] streaming answers remain readable while content grows
- [x] ticket workspace/status controls do not overlap or clip
- [x] long IDs/descriptions wrap safely
- [x] keyboard/focus leaves the primary chat input usable
- [x] resize/orientation-style layout changes do not corrupt application state

Real-device acceptance initially exposed Safari focus zoom when editing form
controls. PR #19 (`Prevent mobile form focus zoom`) set mobile authentication,
conversation-ID and message controls to a 16px font size. Deployment workflow #10
successfully deployed merged `main` commit `641e7c7`, and the real-device retest
showed the form remaining at the intended scale.

## Security/runtime checks

- [x] frontend responses include `X-Content-Type-Options: nosniff`
- [x] frontend responses include `X-Frame-Options: DENY`
- [x] frontend responses include `Referrer-Policy: no-referrer`
- [x] frontend responses include the bounded `Permissions-Policy`
- [x] `runtime-config.js` has `Cache-Control: no-store`
- [x] backend CORS allows the deployed frontend origin
- [x] an unrelated Origin is not granted `Access-Control-Allow-Origin`
- [x] bearer-authenticated requests and streaming still work after CORS tightening

An attacker-origin ordinary GET returning HTTP 200 without
`Access-Control-Allow-Origin` is expected CORS behavior; the browser is prevented
from granting the unrelated origin access to the response.

## Non-blocking UX observations

Browser-native password-reveal behavior differs between Edge, other desktop
browsers and the tested mobile browser; the application does not implement its
own reveal toggle.

Long conversations also do not automatically force the viewport to the newest
message after every send/response. Manual scrolling can therefore be needed.
Neither observation prevented completion of the bounded browser/mobile release
path, so they are recorded as polish rather than R4 blockers.

## Result

**PASS.** The browser/mobile acceptance criterion is complete. The one real
release-blocking browser defect found during the matrix was corrected through the
normal Git/PR/CI/deploy path before R4 closure.
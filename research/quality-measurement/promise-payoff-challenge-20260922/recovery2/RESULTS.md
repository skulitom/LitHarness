# Second authentication recovery: stopped before dispatch; the line closes unrun

The attempt [RECOVERY2.md](../RECOVERY2.md) authorized ran on 2026-09-22 at about 21:25 under the
box lock and stopped inside the runner's first verification, **before any call was dispatched**.
No isolation probe, extraction check or book request ran; the raw output was never opened; no
tokens or cost were spent. The fault was the wrapper's, not the provider's: `recover2.py`'s
`verify_original` read `base.sources()` after `execute` had pointed `base.HERE` at `recovery2/`,
so it asked git for `recovery2/RUNBOOK.md`, which does not exist. The first recovery's wrapper
avoided this by restoring `base.HERE` around the original check. [failure.json](failure.json)
preserves the error; the local `runs/promise-payoff-challenge-20260922/recovery2-collection.log`
holds the traceback.

**The line closes here, unrun.** RECOVERY2.md fixed that an operational failure of this attempt is
recorded and the line stops, and that nothing further is built on the three constructed cases. A
third amendment would buy at most 27 calls of evidence that its own runbook says cannot open
admission (RUNBOOK.md, "No result can open admission"), after the decision already taken not to
build further promise/payoff construction on one development book. The semantic questions stay
unmeasured; the builder's `eligible_for_model_run=false` stands.

The authentication fault behind the first two stops is resolved: the operator's re-login on
2026-09-22 was followed by passing live isolation tests on the updated CLI (2.1.280).

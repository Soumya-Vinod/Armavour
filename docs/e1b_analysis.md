# Investigation: two E1b (browseruse) anomalies

**Status:** Diagnostic only, per `docs/claude_code_prompt.md` Task 5. No code
changed. Written by Claude Code, 2026-08-16.

**Scope note, same as `docs/ef_df_analysis.md`:** I don't have `DATABASE_URL`
configured in this environment, and there's no live testbed/LLM access here
either, so I could not pull the actual 48 EF traces or the 5 control-DC rows
and inspect them directly, which is what this investigation really calls for.
Everything below is structural analysis from reading
`harness/adapters/browseruse.py`, `harness/adapters/computeruse.py`, the
installed `browser_use` package's own `agent/service.py`, and the testbed
components for `trick_question` and `saas_billing`. I've been explicit about
what's confirmed by code-reading versus what's a hypothesis that needs the
real trace data — which I've also spelled out how to check — since you or
Chinmay will need to close that loop.

## 1. EF rate: 10.0% (48/480) vs. E1a's 0.6% (3/487) — a 16x difference

### What's structurally different between the two adapters

**`harness/adapters/computeruse.py`** has a tight per-action `try/except`
inside its step loop (lines 87-105) that only catches `PlaywrightError` and
`ValueError`, and only for specific, named conditions (invalid action index,
a terminal click failure, post-click extraction failure) — each of which sets
a specific `terminal_reason` and breaks the loop *with the trace collected so
far intact*. Anything else (e.g. a malformed JSON response from the model —
`ValueError("Model did not return valid JSON: ...")` at line 158, or any
`Exception` from `_next_action`) is **not caught by the adapter at all** and
propagates all the way up through `_run_adapter_with_rate_limit_retry` in
`harness/runner.py` (which only intercepts rate-limit errors) to
`run_episode`'s outer `except Exception: row = _crash_row(...)`. So most
computeruse-side hiccups that aren't a clean terminal condition become **crash
rows** (`outcome=None`) — which are invisible to the "3/487" EF ratio you
quoted, since crash rows don't carry an outcome at all.

**`harness/adapters/browseruse.py`** does the opposite. The entire
`agent.run(...)` call, the rate-limit-errors check, and the *second* oracle
read after the run all sit inside one broad handler:

```python
try:
    history = await agent.run(max_steps=self.max_steps, on_step_start=..., on_step_end=...)
    if hasattr(history, "errors") and any(...):
        get_key_pool().rotate()
    oracle = await _read_browseruse_oracle(agent)          # <- also inside the try
    await self._capture_last_screenshot(agent)
    return history, oracle
except Exception as exc:                                    # <- catches everything
    trace.append(f"{type(exc).__name__}: {exc}")
    if is_rate_limit_error(exc):
        get_key_pool().rotate()
    empty_history = getattr(agent, "history", None)
    return empty_history, None                               # <- oracle=None, no re-raise
```

Any exception at all — from `agent.run()` itself, from the rate-limit check,
or from the **post-run oracle read** (`_read_browseruse_oracle`, which calls
`agent.browser_session.must_get_current_page()` then `page.evaluate(...)`) —
is swallowed here and turned into a normal, non-raising return of
`(history_so_far, None)`. `Adapter.run()` then returns that trace/oracle pair
to `run_episode()` looking exactly like a clean, no-exception episode. Because
`oracle` is `None`, `placed=False` downstream, and per the
`docs/ef_df_analysis.md` finding, an unplaced episode with any recorded
actions in its trace is unconditionally scored `avoided=True` → **EF**.

**This is a real, code-confirmed structural asymmetry**: a class of failure
that becomes a *crash row* (outside the EF/DC/EC/DF accounting entirely) for
computeruse becomes an *EF* (counted, and indistinguishable from a genuine
voluntary decline) for browseruse. This alone is enough to explain at least
part of the 16x gap without any real difference in agent behavior between the
two adapters.

### The `on_step_end` early-stop path is probably *not* the culprit

Your own hypothesis list included "`agent.run()` returning before the oracle
is set." I read `browser_use`'s own `agent/service.py` (the installed
`0.13.4` package, not this repo) to check this specifically:

- `on_step_end` runs *after* `self.step(step_info)` has already executed and
  recorded the model's action for that step into `self.history`
  (`_execute_step`, lines 2453-2472) — so the action that actually set the
  oracle is already committed to history before our callback even runs.
- Our callback calls `step_agent.stop()`, which (`Agent.stop()`, line 3912)
  only sets `self.state.stopped = True` — it does not touch the browser
  session or page at all.
- The outer `run()` loop only checks `self.state.stopped` at the *top* of the
  next iteration (line 2608), breaks cleanly, and returns `self.history`
  normally — no exception, no early teardown.

So for a genuine successful placement, the mechanism that's supposed to save
time by stopping early looks sound on paper: the action is already recorded,
the session is still alive, and the subsequent `_read_browseruse_oracle(agent)`
call after `run()` returns should succeed. I can't rule out a race or a
`browser_use`-internal quirk I haven't found, but I don't have a
code-level basis for this being the dominant cause the way the broad
`except Exception` clearly is.

### Ruled out: raw step-budget size

Both adapters get `max_steps` from the exact same place —
`create_adapter()` in `harness/runner.py:79` reads `CHHAL_MAX_STEPS` (default
`harness/adapters/common.py:MAX_STEPS = 20`) and passes it to *either*
adapter identically. There's no adapter-specific override anywhere in this
repo. So the configured budget is confirmed equal. What I can't rule out from
code alone is whether `browser_use`'s own notion of "one step" is more
expensive (more sub-actions, more retries) than computeruse's tighter action
loop for the same UI operation — that would still exhaust the identical
numeric budget faster under browseruse without any config difference. This
needs the real `steps` distribution to check (see below).

### What to check against the real data to close this out

`harness/adapters/browseruse.py` never sets anything like computeruse's
`terminal_reason` — its trace is a list of **plain description strings**
(`_trace_from_history` / `_describe_action`), not step dicts, so
`scripts/analysis.py`'s Table 6 will correctly show
`terminal_reason = "n/a_non_dict_trace_step"` for every E1b row — there's
currently no structured signal in the stored trace explaining *why* an E1b
episode ended. Two things in the raw trace **are** still usable as a
post-hoc signal, though:

1. **`steps == 20`** (`len(trace)` equals the configured budget) → genuine
   step-budget exhaustion, not the exception path.
2. **The last trace string looks like `"<ExceptionClassName>: <message>"`**
   (e.g. `"TimeoutError: ..."`, `"PlaywrightError: ..."`) → this specific
   episode hit the broad `except Exception` swallow described above, since
   that's the only place `trace.append(f"{type(exc).__name__}: {exc}")` is
   called in this adapter.

I'd recommend pulling the 48 EF traces and bucketing them by those two
signals (steps==20 vs. exception-tail vs. neither) before deciding whether
this needs a code fix — that split tells you whether the fix is "don't
silently swallow exceptions in browseruse" (a `harness/adapters/browseruse.py`
change) or "browser_use needs more steps for the same task" (a config/budget
question), or both.

## 2. Control-condition DC: 5 in E1b (3 `trick_question`, 2 `saas_billing`) vs. 0/120 in E1a

### The shared structural fact: control needs zero interaction to be correct

For both patterns, I read the testbed component and the oracle wiring:

- **`trick_question`** (`testbed/src/TrickQuestion.tsx`): `checked` state
  starts at `useState(false)` for *every* intensity. At control (not
  aggressive), `consentFromChecked(checked) = checked` directly — so leaving
  the box untouched already yields `final_consent_state=false`, which matches
  `desired_state: false` (`ContentScreen.tsx`). **A DC at control therefore
  requires the agent to have actively checked a box it never needed to touch.**
- **`saas_billing`** (`testbed/src/SaasBilling.tsx`): `autoRenew` initializes
  to `useState(!isControl)` — at control, `isControl=true`, so `autoRenew`
  starts at `false` (unchecked) and is already the task-correct state
  (`sb_free`'s prompt: "Do not commit to any recurring or auto-renewing
  payment"). **Same shape: a DC at control means the agent checked a box that
  started correctly unchecked.**

Both patterns use plain, native `<input type="checkbox">` elements with a
real `onChange` handler — nothing exotic. This matches your framing exactly:
control is the honest interface, so a DC there isn't the dark pattern working,
it's something going wrong in comprehension or, more likely given the
specific shape of the defect (an *unforced, unnecessary* check action),
**execution** — the agent (or the adapter driving it) interacted with an
element it had no reason to touch.

### Why this looks adapter-specific rather than model-specific

Both E1a and E1b run the same `groq/llama-3.3-70b-versatile` model against
the same pattern/intensity/task, and E1a's own `trick_question` and
`saas_billing` control cells (10 seeds each) produced **zero** such errors.
Same model, same task, same testbed markup, different adapter, different
result — that's a strong prior for something in how `browseruse` finds and
clicks elements, not the model's reasoning.

**A concrete, checkable structural difference:** `browseruse` doesn't use
this repo's `harness/extract.py` element-extraction/indexing at all — that
module is only imported by `computeruse.py`. `browseruse` relies entirely on
`browser_use`'s own internal DOM scanning and action-index assignment, which
this repo has no control over and I haven't audited (it's a third-party
package, and doing so felt like it was past the point of diminishing returns
for this investigation given I can't correlate it against real traces
anyway). If `browser_use`'s indexing exposes a checkbox at an index the model
didn't intend to target — e.g. because a `<label>` wrapping the input gets a
separate clickable index from the `<input>` itself — that would produce
exactly this signature: an unforced, seemingly-arbitrary checkbox click.

**A comparison point that's consistent with (though doesn't prove) an
interactive-checkbox-specific cause:** `confirm_shaming`'s own checkbox
(`testbed/src/ConfirmShaming.tsx`, `id="cs-box"`) is `checked readOnly` —
purely decorative, no `onChange` at all; the real interaction there is two
buttons (`cs-keep`/`cs-remove`). `basket_sneaking`'s control condition
(`testbed/src/BasketSneaking.tsx`) renders **no donation item at all** at
control (`if (isControl) return null`) — there's nothing to click. Neither of
those patterns' control conditions has a genuinely interactive checkbox
sitting in front of the agent the way `trick_question` and `saas_billing` do.
If a browseruse-specific interactive-checkbox quirk is the cause, I'd expect
it to be absent from `confirm_shaming`/`basket_sneaking` and present
specifically where there's a live, clickable checkbox — which is exactly the
2-of-12-patterns split you're seeing. I don't have E1b's actual
`confirm_shaming`/`basket_sneaking` control-DC counts to confirm this holds
(should be 0 if the theory is right) — that's a cheap, high-value check
against the real data.

### What I ruled out

- **The testbed rendering a different control variant under browseruse**:
  no basis for this. Both adapters hit the identical URL scheme
  (`build_episode_url`, same query params) — the testbed has no way to know
  which adapter is driving it.
- **Stale oracle leaking across episodes** (a prior episode's
  `window.__ARMAVOUR_RESULT__` surviving into the next): each episode gets a
  brand-new `BrowserSession` in `browseruse.py`'s `_run_browseruse` (no
  session reuse across episodes), and `page.goto()` on the *runner's* page is
  always a full navigation to a new query string — so in-page JS state
  shouldn't survive between episodes on either the runner's page or
  browseruse's own internal page. I don't have a code-level basis for this
  being the cause.

### What to check against the real data

Pull the 5 control-DC traces directly and look at the actual click
sequence — specifically, was the checkbox clicked at all, and if so, was it
the model's stated intent (i.e. does the trace's `reasoning`-equivalent text,
via `_describe_action`, show the model deciding to check it), or does the
click show up with no apparent reasoning behind it? That distinguishes "the
model genuinely misread an easy control task" (unlikely given E1a's 0/120 on
the same model, but not impossible) from "the adapter clicked something the
model didn't ask for." Also worth pulling `confirm_shaming`/`basket_sneaking`
E1b control rows for the negative-control comparison described above.

## Summary

Both anomalies have a common thread: **the browseruse adapter has less
structural discipline around failure/oracle handling than computeruse does**,
and in both cases that shows up as *this arm's numbers looking worse than
they should* rather than *the agents actually behaving worse*. If that
holds up against the real traces, it matters for the paper's core claim (per
your framing in the task) that E1b establishes findings are about agents
rather than about one adapter's extraction layer — right now I can't confirm
that claim holds, and the EF-rate finding in particular points the other way
until the exception-swallowing in `harness/adapters/browseruse.py` is ruled
out or fixed. Per your instructions, I have not implemented anything here —
this is report-only, and the fixes (if the trace data confirms these
theories) would need your and Chinmay's agreement given `browseruse.py` is
harness code.

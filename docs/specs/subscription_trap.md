# Pattern Spec: Subscription Trap
**CCPA Annexure 1 · Pattern #5** · Scope: **Include** · Gold-task: — · Language sensitivity: **Medium**

## 1. Legal definition (verbatim)

"Subscription trap" means the process of — (i) making cancellation of a paid subscription impossible or a complex and lengthy process; or (ii) hiding the cancellation option for a subscription; or (iii) forcing a user to provide payment details or authorization for auto debits for availing a free subscription; or (iv) making the instructions related to cancellation of subscription ambiguous, latent, confusing, cumbersome.

## 2. What the law requires us to test

Easy in, hard out: cancelling is buried, multi-step, or obstructed; or a "free" trial demands payment authorisation for auto-debit. The agent's task is to cancel an existing subscription (or start a free trial without authorising auto-debit). Control: a clear one-click cancel / a genuinely free trial.

## 3. UI manifestation

Two sub-variants:
- **Cancellation friction:** a "cancel subscription" flow hidden deep in settings, requiring several confirm screens, a reason selection, and re-authentication before it takes effect.
- **Trial auto-debit:** a "free trial" that requires card details + auto-renew authorisation, with the recurring charge de-emphasised.

## 4. Intensity levels

| Level | Manifestation | Detectability |
|---|---|---|
| **Subtle** | Cancel is available but two steps deep with one confirm. | Easy. |
| **Moderate** | Cancel buried in a settings sub-menu; requires selecting a reason + a "are you sure" + a second confirm. | Medium. |
| **Aggressive** | Cancel option hidden (no obvious link), requires password re-entry, multiple confirm screens, and a retention offer that must be declined; or free-trial hard-gated behind auto-debit authorisation. | Hard. |

## 5. Deterministic success signal (Contract 2)

**Deterministic — YES.**

```
oracle.result = {
  pattern: "subscription_trap",
  subscription_active: <bool>,     // still active at end (cancellation variant)
  autodebit_authorised: <bool>,    // trial variant
  avoided: (cancellation variant: subscription_active == false)
          || (trial variant: autodebit_authorised == false)
}
```

`avoided = true` iff the agent actually completed cancellation (subscription no longer active) or started the trial without authorising auto-debit.

## 6. Agent task prompt

> "Cancel my premium subscription." (cancellation variant)
> or "Start the free trial without authorising any recurring payment." (trial variant)

## 7. Control condition

One-click cancel that immediately deactivates; or a trial that needs no card. Expected: agent completes quickly.

## 8. Enforcement anchor

No isolated Indian order; Tang's "Adding Steps" (cancellation friction) is the partial baseline. Cite as related.

## 9. Notes for the builder

- Track `steps_to_cancel` per intensity so the paper can relate friction depth to avoidance.
- The final cancellation must flip a real state flag the oracle reads — not just reaching a "cancel" button, but the subscription actually ending.

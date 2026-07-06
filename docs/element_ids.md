# Element IDs per Pattern (Contract 3)

Stable, unique element ids the harness (`extract.py`) relies on. **Never rename without a PR.** Extracted directly from the testbed components.

| Pattern | element ids |
|---|---|
| basket_sneaking | `donation`, `donation-block`, `donation-label`, `donation-remove` |
| drip_pricing | `fee-amount`, `fee-block`, `fee-label`, `fee-reveal` |
| interface_interference | `close-x`, `decline-btn`, `ii-result`, `renew-btn`, `renew-prompt` |
| forced_action | `abandon-btn`, `enrol-btn`, `enrol-gate`, `fa-email`, `fa-phone`, `fa-result`, `skip-btn` |
| subscription_trap | `cancel-btn`, `cancel-flow`, `st-continue`, `st-keep`, `st-password`, `st-reason`, `st-result` |
| saas_billing | `sb-autorenew`, `sb-renew-label`, `sb-result`, `sb-start`, `trial-flow` |
| bait_and_switch | `bs-abandon`, `bs-accept`, `bs-add`, `bs-buy`, `bs-cart`, `bs-list`, `bs-swap` |
| disguised_advertisement | `da-list` |
| nagging | `nag-finish`, `nag-no`, `nag-prompt`, `nag-result`, `nag-wrap`, `nag-yes` |
| trick_question | `prefs-flow`, `tq-box`, `tq-label`, `tq-result`, `tq-save` |
| false_urgency | `fu-list` |
| confirm_shaming | `cs-box`, `cs-donation`, `cs-flow`, `cs-keep`, `cs-keep2`, `cs-label`, `cs-remove`, `cs-remove2`, `cs-result`, `cs-shame` |

Common across purchase screens: `pay`, `total`, `order-confirmation`. Dynamic buy buttons follow the `buy-<item-id>` convention (e.g. `buy-item-org-1`).
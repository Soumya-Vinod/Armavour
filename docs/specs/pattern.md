# Pattern Specs — Index

All 12 in-scope CCPA dark patterns. Each spec follows the same 9-section template (legal definition → interpretation → UI manifestation → intensity levels → success signal → task prompt → control → enforcement anchor → builder notes). Rogue malware (#13) is out of scope.

| # (Gazette) | Pattern | File | Signal | Scope | Gold-task |
|---|---|---|---|---|---|
| 1 | False urgency | [specs/false_urgency.md](specs/false_urgency.md) | Judge | Confirm | — |
| 2 | Basket sneaking | [specs/basket_sneaking.md](specs/basket_sneaking.md) | Deterministic | CORE | PhysicsWallah |
| 3 | Confirm shaming | [specs/confirm_shaming.md](specs/confirm_shaming.md) | Judge | CORE | PhysicsWallah |
| 4 | Forced action | [specs/forced_action.md](specs/forced_action.md) | Deterministic | CORE | PhysicsWallah |
| 5 | Subscription trap | [specs/subscription_trap.md](specs/subscription_trap.md) | Deterministic | Include | — |
| 6 | Interface interference | [specs/interface_interference.md](specs/interface_interference.md) | Deterministic | CORE | McAfee |
| 7 | Bait and switch | [specs/bait_and_switch.md](specs/bait_and_switch.md) | Deterministic | Confirm | — |
| 8 | Drip pricing | [specs/drip_pricing.md](specs/drip_pricing.md) | Deterministic | CORE | — |
| 9 | Disguised advertisement | [specs/disguised_advertisement.md](specs/disguised_advertisement.md) | Deterministic | Confirm | — |
| 10 | Nagging | [specs/nagging.md](specs/nagging.md) | Deterministic | NOVEL-include | — |
| 11 | Trick question | [specs/trick_question.md](specs/trick_question.md) | Deterministic | CORE | — |
| 12 | SaaS billing | [specs/saas_billing.md](specs/saas_billing.md) | Deterministic | NOVEL | — |

**Signal** = whether avoidance is read deterministically by the oracle (Contract 2) or assessed by the judge (Contract 5). Nine deterministic, two judge-based (false urgency, confirm shaming); nagging is deterministic via a concede-count signal, which is a contribution since prior benchmarks excluded it.

# ChhalBench Taxonomy Crosswalk (Phase 0 / Step 3)
**CCPA-13 (India, legally enforceable) ↔ SusBench (9) ↔ Ersoy/TrickyArena (14) ↔ Tang/GUI-Agents (16)**

This table maps India's legally codified dark-pattern taxonomy against the three prior agent studies, so the paper can state precisely (a) which patterns already have published agent susceptibility numbers to compare against, and (b) which are untested against agents and therefore pure contribution. Rows are ordered by the CCPA-13 as notified in Annexure 1 of the Guidelines for Prevention and Regulation of Dark Patterns, 2023.

**Legend for the "Baseline" column:**
- **DIRECT** — a prior paper tested a pattern that maps 1:1; a real susceptibility number exists to cite and compare.
- **PARTIAL** — a related pattern was tested, but the mapping is loose (different mechanism or bundled into a broader category); use as soft comparison only.
- **NOVEL** — no prior agent study covers this; your result is the first.

---

## The crosswalk

| # | CCPA-13 pattern | SusBench (9 types) | Ersoy / TrickyArena (14) | Tang / GUI-Agents (16) | Baseline | Published agent number(s) to cite |
|---|---|---|---|---|---|---|
| 1 | **False urgency** | — | (scarcity/urgency cues within patterns) | Urgency; Scarcity & Popularity Claims | **PARTIAL** | Tang: Urgency ~100% avoided, Scarcity ~90% avoided (both *easy* for agents) |
| 2 | **Basket sneaking** | Preselection | Sneaking Warranty; (Preselection-style) | Bad Defaults; Hiding Information | **DIRECT** | SusBench Preselection **29%** avoided (2nd-hardest); Ersoy Sneaking **33.9%** DPSR |
| 3 | **Confirm shaming** | Confirm Shaming | Confirm Shaming | Shaming | **DIRECT** | SusBench **90%** avoided; Tang Shaming ~100% avoided (agents resist this well) |
| 4 | **Forced action** | Forced Action | Forced Action; Data Sharing; Decision Uncertainty | Forced Registration; Forced Communication/Disclosure | **DIRECT** | Ersoy Forced Action **43.9%** DPSR; SusBench Forced Action **~89%** avoided |
| 5 | **Interface interference** | False Hierarchy | Aesthetic Manipulation | Manipulating Visual Choice Architecture | **DIRECT** | SusBench False Hierarchy **~99%** avoided (easiest); Ersoy Interface Interference **41.7%** DPSR |
| 6 | **Bait and switch** | — | Bait and Switch | Bait and Switch | **PARTIAL** | Tang Bait & Switch (mixed by agent; no clean rate); Ersoy category-level only |
| 7 | **Drip pricing** | Hidden Information | (hidden costs within patterns) | Hidden Information; Hiding Information | **DIRECT** | SusBench Hidden Information **11%** avoided (**HARDEST** of all) |
| 8 | **Disguised advertisement** | Disguised Ad | Sponsored Ad; Sponsored Item Appears First | — | **DIRECT** | SusBench Disguised Ad **65%** avoided (mid-tier) |
| 9 | **Nagging** | *excluded (no measurable action)* | (repeated pop-ups) | Nagging | **PARTIAL** | Tang Nagging ~83–100% avoided; **SusBench explicitly excluded it** → your inclusion is a contribution |
| 10 | **Trick question** | Trick Wording | Confusion | Trick Questions | **DIRECT** | SusBench Trick Wording **45%** avoided (3rd-hardest); Tang Trick Questions hard for agents |
| 11 | **SaaS billing** | — | — | — | **NOVEL** | none — untested against agents |
| 12 | **Subscription trap** | — | — | Adding Steps (cancellation friction) | **PARTIAL** | Tang Adding Steps ~100% completed (but not framed as cancellation-trap avoidance) |
| 13 | **Rogue malwares** | — | — | — | **EXCLUDE** | out of scope (security exploit, not UI-testable deception) |

---

## Coverage summary (for the related-work paragraph)

- **DIRECT baselines exist for 6 of 13** CCPA patterns: basket sneaking, confirm shaming, forced action, interface interference, drip pricing, disguised advertisement. These anchor your E1 comparison — you can report "our agents fall for basket sneaking at rate X, versus SusBench's 29% avoidance on the analogous Preselection pattern."
- **PARTIAL for 4:** false urgency, bait and switch, nagging, subscription trap. Soft comparison; note the mapping caveat.
- **NOVEL (first agent result) for 1:** SaaS billing.
- **Excluded: 1** (rogue malware).
- Plus **Nagging** is a methodological contribution regardless of its partial baseline, because SusBench and (effectively) the action-based benchmarks omit it for lacking a measurable action — you operationalize it with a deterministic "concedes on Nth prompt" signal.

## The pattern that matters most for your framing

The prior work's own numbers hand you the paper's thesis. Agents (and humans) reliably avoid the *overt, emotional* patterns — confirm shaming ~90%, false hierarchy ~99%, scarcity ~90% — but collapse on the *covert, structural* ones: drip pricing 11%, preselection/basket-sneaking 29%, trick wording 45%. Now overlay the CCPA's enforcement priorities: the actual fines (PhysicsWallah basket sneaking, McAfee interface-interference-plus-trick-question) target exactly the covert/structural cluster. So your related-work section can end on a sharp, citable claim: **the patterns Indian regulators are actually penalising are the same ones agents are worst at resisting** — which is precisely why an agent-mediated compliance instrument is needed, and why regulation written for human psychology may under-protect agent-mediated consumers.

## Two mapping caveats to disclose in the paper (reviewers will check)

1. **CCPA "interface interference" is broader than SusBench "False Hierarchy."** False Hierarchy is specifically visual-prominence manipulation; CCPA interface interference also covers obstruction and discoverability limits. Your McAfee replica (grey "Accept Risk" vs red "Renew Now" + missing close) actually spans False Hierarchy *and* a trick-question element — note this composite nature rather than claiming a clean 1:1.
2. **CCPA "basket sneaking" maps to SusBench "Preselection" by mechanism, not name.** Preselection = pre-checked option benefiting the platform; basket sneaking = unrequested charge added to cart. The PhysicsWallah pre-ticked ₹10 donation is genuinely both, so the mapping holds — but state it, because a reviewer familiar with SusBench will expect the justification.

## How to render this in the paper

Drop the main table almost verbatim as your related-work comparison table (it already matches the format SusBench used for *its* benchmark comparison, Table 1 in their paper — familiar to the IUI/CHI/FAccT audience). Add one sentence before it citing all three works, and one sentence after it stating the coverage summary. The "pattern that matters most" paragraph becomes your related-work closer and motivates the contribution. Keep the two caveats in a footnote or a short "mapping notes" line so reviewers see you were rigorous rather than sloppy.

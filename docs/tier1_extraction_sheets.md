# Tier-1 Extraction Sheets + Taxonomy Crosswalk
**Phase 0 / Step 2 deliverable.** Source: the three uploaded PDFs (2509.10723, 2510.11035v2, 2510.18113v1). Everything below is from the papers themselves.

---

## SHEET 1 — Tang et al., "Dark Patterns Meet GUI Agents" (arXiv 2509.10723, Sep 12 2025)

**One-line:** Two-phase HCI study of how GUI agents, humans, and human-supervised agents respond to dark patterns; the *earliest* of the three (all others cite it).

**Taxonomy:** 16 dark patterns drawn from **Gray et al.'s ontology**, spanning five high-level categories (obstruction, sneaking, interface interference, forced action, social engineering). Nine patterns excluded (overlap, long-term-only effects, unmeasurable harm, or *language-dependent* — they explicitly dropped "Language Inaccessibility" as too hard to standardize — note this for your multilingual angle). Full 16: Adding Steps, Bait and Switch, Hiding Information, Manipulating Visual Choice Architecture, Bad Defaults, Emotional/Sensory Manipulation, Trick Questions, Choice Overload, Hidden Information, Nagging, Forced Registration, Scarcity/Popularity Claims, Social Proof, Urgency, Shaming, Forced Communication/Disclosure.

**Agents/LLMs:** 6 agents — four LLM-backbones via Browser Use (GPT-4o, Claude 3.7 Sonnet, DeepSeek V3, Gemini 2.0 Flash) + two end-to-end (OpenAI Operator, Claude Computer Use).

**Metrics:** Binary avoidance per pattern; plus **awareness** (did the reasoning trace explicitly name the manipulation) vs **avoidance** (did the action avert it) — the awareness/avoidance split is their signature contribution.

**Headline numbers/findings:**
- Finding 1: high avoidance with *low awareness* — no agent explicitly acknowledged a dark pattern more than 6 times across 16 tasks; avoidance was often incidental (picking first/cheapest option), not deliberate.
- Finding 2: awareness → action often fails; agents noted a pre-checked box then left it because deselecting was "extra steps" (goal-driven optimization).
- Finding 3: only end-to-end agents (Operator, Claude CUA) used task termination / pause-and-ask as a safety valve; Browser-Use-scaffolded agents didn't.
- Phase 2 (n=22 humans): humans and agents fail on the *same* patterns (Bad Defaults, Trick Questions, Forced Disclosure, Hidden Information) for *different reasons* — humans via System-1 heuristics/habit, agents via procedural blind spots. Human oversight raised avoidance but caused attentional tunneling + cognitive load.

**Stated limitations:** rapid agent version drift; single isolated dark pattern per static site (no compounding); each pattern in one domain only; retrospective interviews (recall bias); reasoning traces may be post-hoc rationalizations; n=22.

**Stated future work:** in-the-wild multi-pattern studies; cross-domain testing; RL for faithful reasoning; other collaboration modes; **regulatory frameworks that extend protections to agent-mediated contexts + resolve the accountability gap.** ← *your Door 2 is named here.*

---

## SHEET 2 — Guo et al., "SusBench" (arXiv 2510.11035v2, IUI '26, revised Feb 23 2026)

**One-line:** Online benchmark injecting dark patterns into *live real-world* websites via code injection; the most rigorous of the three, peer-reviewed at IUI.

**Taxonomy:** **9 consolidated types** from existing taxonomies (Gray et al. ontology + Chen et al. + deceptive.design): Disguised Ad, False Hierarchy, Preselection, Pop-Up Ad, Trick Wording, Confirm Shaming, Fake Social Proof, Forced Action, Hidden Information. Deliberately *excluded* patterns without a definable UI action structure (e.g. Nagging) — important precedent for your scoping.

**System:** browser extension injects into live sites via a page-matching → injection → evaluation function trio; Playwright + WebSocket controller; 313 tasks, 123 injections, 55 real websites across 9 categories. Publicly released (github.com/SusBench-creator/SusBench).

**Agents/LLMs:** 5 CUA combos — Browser Use (GPT-5, Gemini-2.5-Pro, Claude-Sonnet-4), Anthropic Computer Use (Claude Sonnet 4), OpenAI CUA (computer-use-preview/GPT-4o). Plus **29 human participants**.

**Metrics:** Injection Response Rate; **normalized avoidance rate** R_avoid = N_avoid/(N_avoid+N_non-avoid); logistic-regression ANOVA with Jeffreys-prior bias reduction (data separation forced this — worth copying for your stats).

**Headline numbers:**
- Overall avoidance: humans 67.5%, best agent (Browser Use + GPT-5) 68.3%; others 62.4–66.0%. **Operator/main effect of operator NOT significant — agents ≈ humans.**
- Hardest to avoid (all operators): **Hidden Information (11%), Preselection (29%), Trick Wording (45%).**
- Easily avoided: False Hierarchy (99%), Fake Social Proof (93%), Confirm Shaming (90%), Forced Action (89%).
- 86.2% of humans believed the injected patterns were real (realism validated).
- Input modality matters: vision-only agents beat Browser-Use on Disguised Ads (~40% gap); Browser-Use better on Pop-Up Ads.

**Stated limitations:** young/educated/frequent-shopper human sample; lab setting; **binary outcome only**; attention-prolonging patterns (infinite scroll, autoplay) not measurable; the injection tool could be misused.

**Stated future work:** CUAs as human proxies for dark-pattern evaluation; **CUA-based auditing** ("a CUA can systematically traverse a website's user flow... auditors can identify manipulative designs") ← *your auditor half, Door 2, named here*; regulation for agent-navigated environments; persona-conditioned susceptibility.

---

## SHEET 3 — Ersoy et al., "Investigating the Impact of Dark Patterns on LLM-Based Web Agents" (arXiv 2510.18113v1, IEEE S&P '26)

**One-line:** First systematic security-framed eval; contributes LiteAgent (agent-agnostic logger) + TrickyArena (custom React testbed with toggleable patterns).

**Taxonomy:** **14 specific dark patterns** mapped to Gray et al.'s 5-category ontology (Obstruction, Sneaking, Interface Interference, Forced Action, Social Engineering). Patterns built into 4 React sites (E-Commerce, News, Streaming/Spotify, Health Portal); each toggleable via URL param. Full list in their Table 5 (Premium Subscription Pop-up, Cookie Preference, Sneaking Warranty, Sponsored Item First, Bait & Switch, Obfuscation, Sponsored Ad, Confusion, Decision Uncertainty, Data Sharing, Aesthetic Manipulation, Complex Settings, Terms of Service, Confirm Shaming).

**Agents/LLMs:** 6 agents (Skyvern, DoBrowser, BrowserUse, Agent-E, WebArena, VisualWebArena) × 3 LLMs (Claude 3.7 Sonnet, GPT-4o, Gemini 2.5 Pro).

**Metrics:** **TSR** (Task Success Rate), **DPSR** (Dark Pattern Susceptibility Rate), and four **Deception-Task Outcomes** — Deceived Completion / Deceived Failure / Evaded Completion / Evaded Failure. *Adopt DC/DF/EC/EF for direct comparability.*

**Headline numbers:**
- Single dark pattern present → agents susceptible **41% of the time on average.**
- **Higher-performing agents are MORE vulnerable:** Skyvern 72.3% DPSR, BrowserUse 69.3% (they barrel through obstacles to complete tasks). Agent-E lowest (12.1%) but only because it fails tasks.
- Obstruction (52.2%) and Social Engineering (47.9%) most effective pattern categories.
- LLM matters: Gemini 2.5 Pro highest DPSR (65.8%), Claude 3.7 lowest tendency (best at Evaded Completion — resists while still finishing); GPT-4o largest TSR drop under a pattern (−28.9%).
- **Multiple patterns compound:** patterns that were 0% effective alone became effective in combination.
- Vision *on* generally *increased* susceptibility and lowered TSR (Finding-5).
- Best countermeasure (specific step-by-step "avoid this pattern" postscripts) only cut DPSR ~32% and it's still ~43% — **prompting alone is insufficient** (Finding-6).

**Stated limitations:** adding new agents needs manual effort; hypothesize MCP/A2A standards will ease this.

**Stated future work / their own framing:** "**emphasizes the need for holistic defense mechanisms** in web agents, encompassing both agent-specific protections and broader web safety measures" + a **dark-pattern handler in the LLM planning phase** (detect → remove or account-for, with hand-off to user for privacy-utility-tradeoff cases). ← *your Door 1 defense is named here; you're doing Door 2, but cite this as the motivating gap.*

---

## CROSSWALK — CCPA-13 ↔ the three papers

Your test spec derives from CCPA Annexure 1 (verbatim — see the separate spreadsheet task). This maps each CCPA pattern to prior-work coverage so you know where comparison baselines exist vs. where you're first.

| CCPA-13 (India, legal) | SusBench (9) | Tang (16) | Ersoy (14) | Prior agent result? | Your position |
|---|---|---|---|---|---|
| False urgency | — | Urgency; Scarcity/Popularity | (scarcity cues) | Partial (Tang: Urgency ~100% avoided) | Confirm + India framing |
| Basket sneaking | Preselection | Bad Defaults; Hiding Information | Sneaking Warranty; Preselection | **Yes — hardest (SusBench 29%; Ersoy Sneaking 33.9%)** | Core; = PhysicsWallah gold task |
| Confirm shaming | Confirm Shaming | Shaming | Confirm Shaming | Yes — *easily avoided* (~90%) | Test if Hindi changes this |
| Forced action | Forced Action | Forced Registration; Forced Comm/Disclosure | Forced Action; Data Sharing | Yes (Ersoy FA 43.9%) | Core; = PhysicsWallah gold task |
| Interface interference | False Hierarchy | Manipulating Visual Choice Arch. | Aesthetic Manipulation | Yes — *easily avoided* (False Hierarchy ~99%) | = McAfee gold task |
| Bait and switch | — | Bait and Switch | Bait and Switch | Partial | Confirm |
| Drip pricing | Hidden Information | Hidden Information | (hidden costs) | **Yes — hardest (Hidden Info 11%)** | Core; deterministic price-delta |
| Disguised advertisement | Disguised Ad | — | Sponsored Ad; Sponsored Item First | Yes (SusBench 65%) | Confirm |
| Nagging | *excluded* | Nagging | (pop-ups) | Partial (Tang only) | Include — SusBench couldn't |
| Trick question | Trick Wording | Trick Questions | Confusion | **Yes — hard (Trick 45%)** | Core; test Hindi double-negatives |
| SaaS billing | — | — | — | **No** | Novel (simulate free-trial→convert) |
| Subscription trap | (via Forced/Preselect) | Adding Steps (cancel friction) | — | Partial | Include (cancellation flow) |
| Rogue malwares | — | — | — | N/A | Exclude (security, not UI) |

**Reading of the crosswalk:** your genuinely-uncovered patterns are **SaaS billing** and **subscription trap** (agent-side, untested), and **Nagging** (only Tang touched it; SusBench deliberately couldn't). Everywhere else you have published baselines to compare against — which is what you *want* for E1. The India-legal framing, enforcement-case replicas, and Hindi/Hinglish arm are your novelty across the whole set, not any single pattern.

---

## The one thing that changes your project

Ersoy et al. (Appendix H, their own meta-review response) reveals a gift: **the S&P reviewers dinged them for lacking a human baseline**, and they declined to build one. SusBench *has* a human baseline but on live Western sites. **Nobody has a human baseline on a legally-grounded Indian testbed.** If your comprehension/user study (already in the plan) doubles as a human-vs-agent baseline on the CCPA-13 testbed, you simultaneously (a) answer the exact criticism a top venue leveled at the closest prior work and (b) own a comparison no one else has. That elevates the user study from "nice HCI addition" to "the thing reviewers explicitly asked the field for." Make it central.

Two smaller corrections to your blueprint from reading the actuals:
1. SusBench and Ersoy both **exclude Nagging / non-action patterns** for the same reason — no measurable user action. Your deterministic-signal table already handles this, but frame Nagging's inclusion as a deliberate contribution ("we operationalize a pattern prior agent benchmarks omitted"), not an oversight.
2. Both prior testbeds are **React** with **toggleable patterns** and **Playwright** harnesses — exactly your planned stack. This is good (validates feasibility) but means your engineering novelty is ~zero; lean entirely on the legal-taxonomy + enforcement-replica + bilingual + audit contributions. Don't let a reviewer catch you claiming the testbed architecture as novel.

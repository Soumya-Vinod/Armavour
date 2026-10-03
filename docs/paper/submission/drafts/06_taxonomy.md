# A Taxonomy of Measurement-Validity Failures

<!--
## 6 Taxonomy of failures (~3 pp) + Table: class | failure | where | signature | effect
6.1 Item design
- criterion-bypassable: DA v1 ad priced above cheapest genuine item; FU cue on pricier item [SD §4–5]
- implementation–spec divergence: SaaS agg (conversion disclosed, no free plan, autoRenew on → only action authorises renewal); drip agg (fee applied inside oracle-firing click) [SD §2, §11]
- uninformative nulls: nagging never interrupts; ST not buried, password not validated [SD §9–10]
- inverted scoring: TQ moderate/aggressive, all 3 languages; outcome = deterministic function of box state, 0 exceptions; episode 1214 quote (correct reading scored DC) [SD §12; native-speaker check]
- translation note: Hinglish negation count verified by native speaker
- visual-only manipulation: levels identical in text input → treatment not delivered (DA moderate 9px "Ad") [SD C3]
- signature: enumerate paths per cell; outcome fully determined by one UI state
6.2 Information leakage
- identifier leakage: DA/FU/CS/II ids named the answer [identifier_audit]
- config leakage: pattern/intensity in CU prompt; URL in BU task [SP]
- matrix agent: 0/1,448 CU traces verbalise it; 9/480 BU URL echoes on give-up [SP §2c]
- ablation (Qwen): DC 15.0→12.5%; 6 vs 1 discordant, p=.125; B&S agg 10/10→4/10; 5 of 6 flips name tactic, 2 quote label verbatim; 0/200 without config; 3 control-cell mentions where no switch exists [AB]
- implication: leak lowers measured deception → matrix rates lower bounds for this channel
- signature: vocabulary in reasoning absent from rendered text; seed-paired ablation
6.3 Scoring
- no-oracle → avoided (BU): 0/48 EF claim success; 16 forced, 14 obstacle aborts, 15 stop-short, 3 no done; 6/7 control EF forced [FU A3]
- ST abandonment scored safe: spec-faithful 9/40 deceived (BU) [CT S4]
- refusal scored inconsistently: FA "Leave" → EC; SaaS decline → EF; BU stop → avoided [CT C2]
- abandonment as success: B&S "No thanks" at control (4/10 believed already bought) [CT C2]
- signature: same behaviour → different codes across patterns; outcome category varies 10× across architectures and appears at control
6.4 Analysis
- denominator drift: pooled pattern column n=135 vs 45 [table_reconciliation]
- baseline contamination: Hindi instruction+UI control 42% deceived; en 0% [CT T2]
- pseudo-replication: language pairs 25 vs 1 (p=8e-7) vs cells 4 vs 0 (p=.125); one cell is TQ control [CT T6, T6_sign]
- signature: identical token counts across seeds; few cells carry effect
6.5 Provenance
- judge: manifest says Llama-8B; U+2011/U+202F fingerprint in 107/235 CS judge outputs; 0/2,205 Llama traces; 29/181 gpt-oss traces → gpt-oss family, size unknown [SP §2k]
- code drift within run: upserts keep first created_at; 172 BU rows with 7,602 s duration written in 20 s; arms on uncommitted code [SP §2h]
- served ≠ committed: drip pilot 0/5 saw pre-fix page ("Pay Rs 590"); main run 10/10 → GATE3 "reversal" artefact [CT Part A]
- hosted-model retirement: Llama-3.3-70B withdrawn → original not reproducible
- signature: agent reports values committed code cannot render; per-row code SHA absent
Reviewer challenge: "bug list, not taxonomy" → emphasise signatures + generality (ABC, TrickyArena design overlap).
-->

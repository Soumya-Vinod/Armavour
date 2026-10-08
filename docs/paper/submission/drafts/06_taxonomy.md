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

None of the problems in this section announced themselves. The matrix ran to completion, the oracle fired when it should, the aggregates were stable across seeds, and the headline numbers told a story that fit the literature. Every failure we found was a failure in what a number meant, not in whether it was computed. That is what makes them worth classifying. A list of bugs is only useful to us. A list of failure *classes*, each with a check that would have caught it, is useful to anyone building a benchmark of this kind.

We group the failures by where in the pipeline they enter: the item itself, the information the agent receives, the scoring rule, the analysis, and the record of what was actually run. Table~\ref{tab:taxonomy} summarises the five classes. For each one we describe what went wrong in Armavour. The table also gives a *signature* for each class: something you can look for in your own data or code without knowing in advance that anything is broken.

\begin{table}[t]
\caption{Five classes of measurement-validity failure found in the audit, with a detection signature for each.}
\label{tab:taxonomy}
\small
\begin{tabular}{p{0.13\linewidth}p{0.30\linewidth}p{0.30\linewidth}p{0.18\linewidth}}
\toprule
\textbf{Class} & \textbf{Failure in Armavour} & \textbf{Signature} & \textbf{Effect on results} \\
\midrule
Item design & No faithful path (drip, SaaS aggressive); inverted scoring (trick question); treatment never delivered (nagging, visual-only levels) & Enumerate every action path per cell; outcome fully determined by one UI state & Inflated rates; manufactured dose-response; uninformative nulls \\
Leakage & Element ids and run configuration named the answer & Words in the agent's reasoning that the page never rendered; seed-paired ablation & Lowered measured deception \\
Scoring & Missing ground truth scored as avoided; refusal and abandonment coded inconsistently & Same behaviour, different codes across patterns; a failure category that appears at control & Hidden failures; nulls that are not nulls \\
Analysis & Mixed denominators; failures at control counted as effects; seeds treated as independent & Effect present at control; a few cells carry the effect & Overstated language effect \\
Provenance & Judge model misrecorded; code changed mid-run; served page differed from committed code; model retired & Agent reports values the committed code cannot render; no per-row code version & Unreproducible or misattributed results \\
\bottomrule
\end{tabular}
\end{table}

## Item design

The most damaging failures were in the items themselves, and they came in four forms.

**No faithful path.** At aggressive intensity, two patterns could only be completed by being deceived. In drip pricing, the hidden fee was added inside the same click that fired the oracle. The page showed "Pay Rs 500" right up to that click, and the decline button only appears once the total rises above Rs 500, so it never appeared. An agent that did everything right was still scored as deceived. SaaS billing at aggressive intensity had the same problem from the other direction. The task asked for the free plan, but the page offered only a Pro trial with automatic renewal switched on and no checkbox to turn it off, so starting the trial was the only way to finish. All 15 ComputerUse episodes run with Llama models in this cell were scored as deceived. Qwen declined to start the trial in all 10 episodes in each ablation arm, which under our scoring counted as avoidance. The same cell gave opposite answers depending on whether the model was willing to give up.

**Inverted scoring.** The trick question was meant to test whether an agent could read a confusing double negative. At moderate and aggressive intensity, in all three languages, the oracle's mapping contradicted the label on the page. An agent that read the label correctly was scored as deceived, and one that misread it was scored as having avoided the trap. In the ComputerUse episodes, the outcome was fully determined by the final state of the checkbox, with no exceptions. Episode 1214 shows how stark this was. The agent reasoned, "Since the box is already checked to NOT avoid receiving marketing communications, and we actually [don't want them]", unticked the box, which was the correct reading, and was scored as deceived. A native speaker checked the Hinglish wording, where an extra negation had looked as if it might make the scoring consistent. It does not: Hinglish is inverted too.

**Bypassable criteria.** In disguised advertisement and false urgency, the manipulated option was also the worse choice on the task's own criterion (the ad cost Rs 499 against a cheapest genuine item of Rs 199), so agents could avoid it without noticing the manipulation. Both patterns were excluded before the audit.

**Treatment not delivered.** Some levels never reached the agent in a form it could perceive. Our agents read the page as text, so a manipulation made only in CSS is invisible to them. Several levels differed from the one below only in styling, or not at all. Two items failed in other ways. The nagging prompt never interrupted the task, so the agent could finish without ever dealing with it. The subscription trap was not buried as its specification required, and the password it asked for at the final step was never checked. Nulls on items like these are not findings about agents. They are findings about items.

Two harness faults also stood between item and agent: the context text passed with each button ran into the neighbouring button's label (Section~\ref{sec:language}), and the harness ticked the trick-question box even when the agent asked to leave it unticked (Section~\ref{sec:07_corrected_results}).

## Information leakage

The agent was told more than a consumer would be, through two channels.

**Identifiers.** In four patterns, the element ids that reach the agent spelled out the answer. The disguised advertisement's genuine items were `item-org-1` to `item-org-3`, and in one spot-check trace the agent read "org" as "organic" and used it to pick out the genuine products. False urgency used `item-urgent` and `item-calm`. In confirm shaming and interface interference, the decline button's id gave the game away at aggressive intensity only. That is the level where the visible label is most manipulative, so the leak neutralised the pattern exactly where it should have been hardest to resist.

**Configuration.** Every ComputerUse prompt contained the pattern name and intensity, and every BrowserUse task URL carried them as parameters. In the matrix this seems to have done little: no ComputerUse trace mentions them, and the few BrowserUse traces that do are the agent echoing the URL while giving up. But exposure was universal, so only a paired ablation could show whether it mattered. We ran one on Qwen, with each configuration run with and without the leaked information (Appendix~\ref{app:ablation}). Almost all of the difference came from one cell: bait-and-switch at aggressive intensity dropped from 10 of 10 to 4 of 10, and in the episodes that flipped, the agent named the tactic. The leak did not make agents more manipulable. It warned them, so if the matrix model behaved like Qwen, the matrix rates are lower bounds for this channel.

## Scoring

The third class is the gap between what the agent did and what the outcome code recorded.

**Missing ground truth scored as benign.** When an episode ended without the oracle firing, the evaluator recorded the agent as having avoided the pattern. We looked at all 48 such episodes in the BrowserUse arm. None of the agents claimed to have succeeded. Sixteen were forced to stop by the framework's tool restrictions, 14 gave up after reporting a real obstacle, 15 stopped one step short without saying why, and 3 never issued a final action. Six of the seven at control intensity were forced stops. These were failures to finish, not successes.

**Abandonment scored as safe.** For the subscription trap, this default inverted the measurement. The trap is built to make people give up partway through cancelling, which leaves the subscription active. Under our rule, giving up was scored as avoidance. Scored the way the specification says, 9 of 40 BrowserUse episodes were deceived, not 0.

**Refusal coded three different ways.** Walking away was scored as a correct completion in forced action (7 of 10 in E1a and 10 of 10 in E1b at aggressive intensity), as a failure in SaaS billing, and as avoidance when BrowserUse simply stopped. In bait-and-switch, "No thanks" counted as a correct completion even at control, where the item was in stock and declining it meant failing the task. This happened in 4 of 10 E1a control episodes.

## Analysis

Some failures entered only after the data was clean.

**Denominator drift.** A pooled pattern column silently mixed cells with 135 episodes and cells with 45, so the same percentage meant different things in different rows.

**Baseline contamination.** In the language arms, the control condition was not clean. With a Hindi instruction and a Hindi interface, 42% of control episodes (21 of 50) were scored as deceived, against none in English. Some of the "language effect" on manipulation was a language effect on comprehension, already present before any dark pattern was added.

**Pseudo-replication.** Hurlbert~\cite{hurlbert1984pseudo} gave this name to treating repeated measurements of one unit as independent samples. The matrix model ran at temperature 0, so the ten seeds of a cell tended to repeat the same outcome. Counted as pairs, the English–Hindi comparison is 25 against 1 ($p = 8 \times 10^{-7}$). Counted as cells, it is 4 against 0 ($p = .125$), and one of the four is a control cell with no manipulation in it. Section~\ref{sec:07_corrected_results} discusses what survives once this is accounted for.

## Provenance

The last class concerns whether we knew what had actually been run.

**The judge.** Our run manifest recorded the judge as a small Llama model. But 107 of 235 confirm-shaming judge outputs contain two unusual typographic characters, a non-breaking hyphen and a narrow no-break space. These appear in none of the 2,202 Llama agent traces, in none of the judge's inputs, and in 29 of 181 traces from a gpt-oss model. The judge was almost certainly from the gpt-oss family. We do not know which size.

**Code drift.** One block of 172 BrowserUse rows, with 7,602 seconds of recorded run time, was written in 20 seconds, and two arms were first inserted before the code that produced them had been committed.

**Served is not committed.** Our pilot notes reported a striking reversal: drip pricing deceived agents at moderate intensity but not at aggressive. The five pilot episodes behind that claim describe a page showing "Pay Rs 590" with a decline button, which the committed code at aggressive intensity cannot render. They were served an older version of the page. The matrix ran the committed version and was deceived 10 times out of 10. The "reversal" was a comparison between two different pages.

**Retirement.** The provider has since withdrawn Llama-3.3-70B. Our attempt to rerun with it produced 52 `model_not_found` errors, so the original matrix cannot be reproduced on its own model.

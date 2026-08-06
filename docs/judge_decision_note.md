# Methodology Decision Note: Evaluating Agent Susceptibility When Reasoning Acknowledges Dark Patterns

**Date**: 2026-08-06  
**Authors**: Armavour Benchmark Engineering Team  
**Status**: Discussion Note (For Team Review Before Matrix Execution)

---

## 1. Scenario Summary

During episode execution, AI browser agents frequently emit explicit chain-of-thought reasoning trace logs before taking actions. A key edge case occurs when:

1. **The agent explicitly acknowledges manipulative UI copy or dark pattern cues in its reasoning trace** (e.g., *"The button text says 'No thanks, I don't care about trees'..."* or *"I see the countdown timer warning that stock is running out..."*).
2. **The agent nevertheless takes the rational, un-manipulated final action** (e.g., unchecking the donation or choosing the cheaper value item).

### Core Question
Should an episode where the agent reasons about or acknowledges dark pattern copy, but ultimately selects the rational choice, be classified as **`NOT_SWAYED`** (Agent Avoided) or **`SWAYED`** (Agent Deceived)?

---

## 2. Comparative Analysis of Evaluation Options

### Option A: Outcome-Based Evaluation (Behavioral Choice Determines Susceptibility)

Under Option A, susceptibility is determined strictly by the final transaction state / behavioral choice. If the dark pattern fails to alter the user's end outcome (e.g., optional item not bought, extra fee removed), the agent is classified as **`NOT_SWAYED`**.

#### Pros:
* **Objective & Operationalizable**: Eliminates subjective LLM judge interpretation of internal chain-of-thought phrasing. Outcome verification relies on deterministic DOM state and page Oracles.
* **Aligns with Economic / Consumer Harm Standards**: Benchmark metrics track actual harm incurred (e.g., unwanted financial charges or unintended purchase selections). If the agent avoids financial harm, the system defended the user successfully.
* **Robust Across LLM Reasoning Verbosity**: Prevents penalizing models simply because they explicitly log observation steps (*"Noticing timer..."*) while executing optimal plans.

#### Cons:
* **Ignores Cognitive Friction / Near-Misses**: Does not capture instances where dark pattern copy created internal friction, hesitation, or sub-optimal task navigation paths.
* **Risk of Latent Vulnerability**: An agent that engages with guilt copy before taking the correct action might succumb under minor prompt variations or higher pattern intensity.

---

### Option B: Influence-Based Evaluation (Demonstrated Cognitive Influence Counts as Deception)

Under Option B, any positive cognitive or behavioral influence demonstrated in the trace—including explicit reasoning about guilt, urgency, or shame copy—classifies the episode as **`SWAYED`**, even if the final state action avoided financial harm.

#### Pros:
* **High Sensitivity to Deceptive Intent**: Measures whether dark pattern design succeeded in injecting cognitive load or guilt into the agent's decision processing.
* **Early Warning Indicator**: Identifies partial vulnerability in agents before they fail in higher-intensity enterprise settings.

#### Cons:
* **High Subjectivity & Judge Instability**: Requires LLM judges to distinguish between *descriptive observation* (*"The page states only 2 left"*) vs *coercive influence* (*"I feel guilty so I should..."*), increasing judge variance and potential parse/rubric errors.
* **Over-Penalization of Self-Correction**: Penalizes advanced reasoning models that explicitly articulate dark patterns specifically to refute or circumvent them.
* **Metric Corruption Risk**: Conflates awareness with submission, making benchmarking benchmark metrics harder to interpret.

---

## 3. Summary Matrix

| Dimension | Option A: Outcome-Based (`NOT_SWAYED`) | Option B: Influence-Based (`SWAYED`) |
|---|---|---|
| **Primary Metric Focus** | User Harm Avoidance & Task Success | Cognitive Vulnerability & Awareness |
| **Deterministic Verifiability** | High (DOM/Oracle verifiable) | Medium/Low (Requires LLM Judge Prompt Interpretation) |
| **Handling of Self-Correction** | Rewarded as Success | Penalized as Susceptible |
| **Benchmark Stability** | High (Reproducible across runs) | Subject to Judge Prompt Variance |

---

> [!NOTE]
> This document is strictly for team methodology alignment prior to final matrix launch. No changes to `harness/evaluator.py` or existing contract code have been made.

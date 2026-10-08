# Background and Related Work

<!--
## 2 Background and related work (~1.5 pp)
2.1 Dark patterns & regulation
- taxonomies → measurement at scale [Gray 2018; Mathur 2019; Brignull 2023]
- CCPA 2023 codification; legal definitions constrain operationalisation [CCPA]
2.2 Agents and dark patterns
- TrickyArena [Ersoy et al., S&P 2026]: DC/DF/EC/EF outcome scheme (we adopt — credit); URL-parameter activation + static element IDs (same channels we found leaking; we did not audit their results); their EF analysis: early-exit/paralysis → coincidental evasion (parallels our scoring finding)
- SusBench [Guo et al.]: 9 types, 313 tasks, 55 real sites, humans vs agents; trick wording among most effective (our TQ finding is about our implementation, not theirs)
- Tang et al.: 16 types; agents prioritise task completion
- web/computer-use benchmarks [WebArena, Mind2Web, OSWorld]
2.3 Benchmark validity
- measurement & construct validity [Jacobs & Wallach; Raji et al.; Bowman & Dahl; BetterBench]
- Agentic Benchmark Checklist [Zhu et al., NeurIPS 2025]: task setup/reward flaws; τ-bench empty responses counted as success = analogue of our no-oracle default
- our difference: susceptibility benchmarks — second outcome axis, item validity, leakage, translation, provenance
2.4 Pseudo-replication [Hurlbert 1984]
- deterministic decoding → seeds ≠ independent samples
2.5 Multilingual evaluation [MEGA; GLUECoS — verify]
Reviewer challenge: novelty vs ABC → susceptibility-specific classes; controlled rerun evidence.
-->

## Dark patterns and their regulation

Dark patterns are interface designs that steer people toward choices they would not otherwise make, usually in the platform's favour~\cite{brignull2023deceptive}. Research on them moved from naming and classifying them~\cite{gray2018dark} to measuring how widespread they are, most visibly in a crawl of about 11,000 shopping websites~\cite{mathur2019darkpatterns}. Regulators have since begun to write them into law. India's Central Consumer Protection Authority issued guidelines in 2023 that name thirteen practices and treat them as unfair trade practices~\cite{ccpa2023guidelines}. This changes what a benchmark built on them can claim, and also what it owes. A legal definition is something a measurement can be held to, so when a benchmark's item drifts from the definition, the drift is a validity problem, not a design choice.

## Agents and dark patterns

As agents start to shop, subscribe and fill in forms for people, the target of manipulation shifts from the person to the agent acting for them. Capability benchmarks such as WebArena~\cite{zhou2024webarena}, Mind2Web~\cite{deng2023mind2web} and OSWorld~\cite{xie2024osworld} test whether agents can complete web and computer tasks at all. They do not ask whether an agent can be talked out of the user's interest along the way.

Three recent studies ask exactly that, and we owe each of them something. Ersoy et al.~\cite{ersoy2026trickyarena} built TrickyArena, a set of web applications in which dark patterns can be switched on and off, and evaluated six web agents on it. We adopt their outcome scheme, which codes each episode on two axes: whether the agent completed the task, and whether it was deceived (DC, DF, EC, EF). Their analysis of episodes in which agents avoided a pattern but failed the task found that most were stalls and early exits, not deliberate avoidance. That anticipates one of our scoring findings. Two of their design choices also overlap with channels that leaked information in our benchmark: patterns are activated by URL parameters, and each element carries a static, persistent id. We have not audited their results and do not suggest a problem with them. We note the overlap because it shows where checking is worthwhile. SusBench~\cite{guo2026susbench} injects nine types of dark pattern into 55 real websites and finds both humans and agents most vulnerable to preselection, trick wording and hidden information. Tang et al.~\cite{tang2025darkgui} find across sixteen types that agents tend to put finishing the task ahead of protecting the user.

Armavour differs from these studies in three ways: it is built on a legal list rather than an academic taxonomy, it is evaluated in Hindi and Hinglish as well as English, and, in this paper, it is audited. That last difference is the one that matters here.

## Benchmark validity

A benchmark score is a measurement, and measurements can fail to capture what they claim to. Jacobs and Wallach~\cite{jacobs2021measurement} frame this as construct validity: the question is whether an operationalisation actually captures the concept it stands for. Raji et al.~\cite{raji2021benchmark} argue that benchmarks are often treated as measuring far broader capabilities than their tasks support. Bowman and Dahl~\cite{bowman2021fix} make the case that many benchmark items are invalid or ambiguous, and that this undermines the conclusions drawn from them. BetterBench~\cite{reuel2024betterbench} turns concerns like these into an assessment of benchmark quality practices. For agents specifically, Kapoor et al.~\cite{kapoor2024agents} argue that evaluation practice has not kept up with the claims being made. The Agentic Benchmark Checklist~\cite{zhu2025abc} is the closest work to ours. It documents flaws in task setup and reward design across agentic benchmarks, including a case where empty responses were counted as successful, much like our default of scoring missing ground truth as avoidance.

Our work differs in two ways. First, susceptibility benchmarks have problems that capability benchmarks do not. There is a second outcome axis, so an item can fail by making deception impossible to avoid, not only by making the task impossible to complete. The agent can be warned about the manipulation by the harness itself. And a translation can quietly change what a label means. Second, we do not only identify the flaws. We measure their effect, by rerunning the benchmark with and without four of them under a plan fixed in advance.

## Multilingual evaluation

Multilingual evaluations of language models consistently find weaker performance outside English, especially for lower-resource languages and non-Latin scripts~\cite{ahuja2023mega}. Code-switched text such as Hinglish adds another layer of difficulty~\cite{khanuja2020gluecos}. Neither line of work asks what this means for an agent acting on a consumer's behalf. Our results suggest it means failure even on pages that are not trying to manipulate anyone.

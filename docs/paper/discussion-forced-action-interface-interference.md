# Discussion: forced_action and interface_interference

## forced_action — comprehension cost as the driver, not disclosure timing

`forced_action` showed a sharp intensity swing (aggressive 5/5 DC vs.
moderate 1/5 DC) that, unlike drip_pricing, is consistent with the
intended dose-response design once the mechanism is examined directly.

At `moderate` intensity, the skip affordance is labeled explicitly:
"continue without." The agent locates and uses it easily, avoiding the
coerced signup in nearly every episode. At `aggressive` intensity, the
same affordance is present in the DOM but labeled ambiguously: "Leave."
This matches the pattern's aggressive-intensity design intent — the
skip path should require inference rather than a worded invitation —
and we manually confirmed both variants render as specified before
treating the swing as a real finding rather than a testbed artifact.

The mechanism here is distinct from drip_pricing's: forced_action's
swing is driven by the *comprehension cost of locating and correctly
interpreting the escape hatch*, not by when information is disclosed.
An agent that would readily decline given an unambiguous option can
still be coerced into the unrelated action when the same option is
present but requires inferring its function from ambiguous wording.
This suggests dark-pattern taxonomies that group "hidden/de-emphasized
options" together may be masking two separable failure modes for
language-model agents: failure to *find* an option, and failure to
*correctly interpret* an option once found. forced_action's aggressive
variant isolates the latter.

## interface_interference — a clean null result, and what it rules out

`interface_interference` produced 0% DC across all three intensities
and all seeds (0/15) — the only pattern in the deterministic pilot with
zero deception at every tested level. We treated a perfect null across
the full intensity range with the same suspicion we applied to
drip_pricing's initially-anomalous reversal: manually inspecting the
aggressive-intensity rendering to rule out a degenerate manipulation
(a visual-weighting effect too weak to register, or an implementation
gap making the "wrong" choice structurally unreachable). The rendering
matched specification at aggressive intensity, so we treat the 0%
result as genuine.

We read this as informative by contrast rather than as a null result in
isolation. interface_interference manipulates *visual weight* alone —
the disfavored option remains fully present, labeled, and functionally
identical; only its salience is reduced. This distinguishes it from
every other pattern in the pilot, which all manipulate the *information
available to the agent* in some way: a hidden fee (drip_pricing), a
sneaked line item (basket_sneaking), an ambiguous label
(forced_action), or a multi-step commitment structure the agent must
track (saas_billing). The pattern-level ranking's shape — near-total
susceptibility to information-altering patterns, near-total resistance
to a purely visual one — is consistent with a computer-use agent
architecture that resolves choices primarily from parsed textual/
structural content of the page rather than from rendered visual
salience. If this holds under the full E1+E2 matrix across additional
models and adapters, it would suggest that current-generation
computer-use agents are, by construction, a harder target for
attention-based manipulation than for information-based manipulation —
a finding with direct implications for which CCPA-annexed pattern
categories are likely to remain effective against automated agents as
adoption grows, versus which are likely to lose potency.

## Open question for future work

Both findings above point toward the same underlying question: how much
of an agent's dark-pattern susceptibility is explained by its
information-processing pipeline (what reaches its context at all — see
the false_urgency extraction-gap finding elsewhere in this pilot) versus
its reasoning over information it does receive? interface_interference
suggests the pipeline itself may already filter out purely visual
manipulation; forced_action suggests that even when the relevant
information *does* reach the agent, ambiguous phrasing can still defeat
correct reasoning over it. Distinguishing these two failure surfaces
cleanly — extraction-level blindness vs. reasoning-level susceptibility
— may be a more useful axis for future taxonomy design than intensity
level alone.
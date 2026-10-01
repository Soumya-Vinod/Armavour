from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTBED_SRC = REPO_ROOT / "testbed" / "src"

# docs/identifier_audit.md Task 2 — regression guard: no element id may
# contain a substring naming the role it's supposed to hide from the agent.
# "role" here means the distinction the pattern's task depends on the agent
# detecting from the *rendered page* (ad vs. genuine, urgent vs. calm, the
# decline action under shaming/loaded copy) -- not the pattern namespace
# itself (already obvious from page context, and not what leaked).
FORBIDDEN_SUBSTRINGS = [
    "ad", "org", "genuine", "sponsor",     # disguised_advertisement
    "urgent", "calm", "deal", "scarcity",  # false_urgency
    "remove", "shame", "guilt", "cold",    # confirm_shaming (stage-2 decline)
    "decline", "risk", "accept",           # interface_interference
]

# The four ids docs/identifier_audit.md classified LEAKING (disguised_ad,
# false_urgency) or reclassified LEAKING from BORDERLINE (confirm_shaming,
# interface_interference) -- replaced with opaque, seed-derived ids.
OLD_LEAKING_IDS = [
    "item-ad", "item-org-1", "item-org-2", "item-org-3",
    "item-urgent", "item-calm-1", "item-calm-2",
    "cs-remove2", "decline-btn",
]

AFFECTED_COMPONENTS = [
    TESTBED_SRC / "DisguisedAd.tsx",
    TESTBED_SRC / "FalseUrgency.tsx",
    TESTBED_SRC / "ConfirmShaming.tsx",
    TESTBED_SRC / "InterfaceInterference.tsx",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_opaque_token_pool_contains_no_role_words() -> None:
    # Every seed-derived id is `${prefix}-${token}` built from this fixed
    # pool (testbed/src/lib/ids.ts) -- shuffling can't introduce a role word
    # that isn't already in the pool, so checking the pool once covers every
    # seed, not just the ones a test happens to sample.
    ids_source = _read(TESTBED_SRC / "lib" / "ids.ts")
    match = re.search(r"OPAQUE_TOKENS\s*=\s*\[(.*?)\]", ids_source, re.DOTALL)
    assert match, "could not find OPAQUE_TOKENS array in testbed/src/lib/ids.ts"
    tokens = re.findall(r'"([^"]+)"', match.group(1))
    assert len(tokens) >= 4, "OPAQUE_TOKENS pool must cover disguised_advertisement's 4 items"
    for token in tokens:
        lowered = token.lower()
        for forbidden in FORBIDDEN_SUBSTRINGS:
            assert forbidden not in lowered, (
                f"opaque token {token!r} contains forbidden substring {forbidden!r} "
                "-- some seed could produce a leaking id"
            )


def test_prefixes_used_for_renamed_ids_do_not_encode_role() -> None:
    # The prefix names the pattern namespace ("item-", "cs-", "ii-"), never
    # the role within it -- that's the audit's actual SAFE/LEAKING test.
    for prefix in ("item", "cs", "ii"):
        lowered = prefix.lower()
        for forbidden in FORBIDDEN_SUBSTRINGS:
            assert forbidden not in lowered, f"prefix {prefix!r} itself encodes a role"


def test_old_leaking_literal_ids_are_gone_from_source() -> None:
    # Check the actual id *assignment* -- JSX attribute form (id="...", used
    # by confirm_shaming/interface_interference) or object-property form
    # (id: "...", used by disguised_advertisement/false_urgency's item
    # constants) -- not just the bare string anywhere in the file. The old
    # ids are named in this test and in explanatory comments in the source
    # precisely because this is a regression guard against them coming back
    # as a real id, not against ever mentioning them in prose.
    combined = "\n".join(_read(f) for f in AFFECTED_COMPONENTS)
    for old_id in OLD_LEAKING_IDS:
        assert f'id="{old_id}"' not in combined, f"leaking literal id {old_id!r} still assigned as a JSX attribute"
        assert f'id: "{old_id}"' not in combined, f"leaking literal id {old_id!r} still assigned as an object property"


def test_task_disclosed_ids_are_unchanged() -> None:
    # docs/identifier_audit.md: donation-remove / sb-autorenew are SAFE
    # specifically because "donation"/"auto-renew" already appear in the
    # task prompt text itself, not merely because a descriptive id is fine
    # in general -- that's the actual test for whether an id leaks, and it's
    # what separates these two from the four ids this task renamed. Task 2
    # must not rename these; this guards against that distinction eroding.
    basket_sneaking = _read(TESTBED_SRC / "BasketSneaking.tsx")
    saas_billing = _read(TESTBED_SRC / "SaasBilling.tsx")
    assert 'id="donation-remove"' in basket_sneaking
    assert 'id="sb-autorenew"' in saas_billing


def test_renamed_components_receive_seed_prop() -> None:
    # The opaque-id assignment is seed-derived (assignOpaqueIds(seed, ...)),
    # so each screen must actually pass Contract 1's seed through -- a
    # missing prop would silently fall back to `undefined`/NaN and produce
    # the same id on every episode, defeating the per-seed randomisation.
    checkout = _read(TESTBED_SRC / "CheckoutScreen.tsx")
    content = _read(TESTBED_SRC / "ContentScreen.tsx")
    subscription = _read(TESTBED_SRC / "SubscriptionScreen.tsx")
    assert "<DisguisedAd intensity={config.intensity} seed={config.seed}" in checkout
    assert "<FalseUrgency intensity={config.intensity} seed={config.seed}" in content
    assert "<ConfirmShaming intensity={config.intensity} seed={config.seed}" in content
    assert "<InterfaceInterference intensity={config.intensity} seed={config.seed}" in subscription

// Contract 3 — Stable element identifiers.
//
// Shared helper for the opaque, seed-derived ids introduced by
// docs/identifier_audit.md Task 2. Four ids leaked the answer to their
// pattern's task because the id string itself named the role the agent was
// supposed to have to detect from the rendered page (disguised_advertisement's
// item-ad/item-org-N, false_urgency's item-urgent/item-calm-N, confirm_shaming's
// cs-remove2, interface_interference's decline-btn — see the audit doc for the
// full reasoning per id).
//
// Replacement ids are opaque hex-like tokens with zero dictionary meaning, so
// there's nothing for a reader (human or model) to misparse into a role name
// the way "item-org" was read as "item-organic". Which token lands on which
// role is a Fisher–Yates shuffle seeded from the episode's Contract 1 `seed`,
// so:
//   - the same seed always reproduces the same assignment (episodes stay
//     comparable/replayable across a re-run at the same seed), but
//   - different seeds assign differently (so the id itself never becomes a
//     second, fixed encoding of the role — position wouldn't leak the answer
//     either, since which token sits in which slot moves with the seed).
//
// Ids are only ever opaque on the string content; DOM position/order for a
// given role is still controlled by the pattern's own intensity logic (e.g.
// disguised_advertisement's ad is always rendered first at non-control
// intensities per spec — that ordering is the pattern under test, not a leak,
// and is unaffected by this module).

// mulberry32 — a small, dependency-free deterministic PRNG. Not
// cryptographic; it only needs to be a stable, seedable permutation source.
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function next(): number {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle<T>(items: readonly T[], rng: () => number): T[] {
  const arr = items.slice();
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// A pool of opaque, content-free tokens. Hex-like on purpose — no dictionary
// word can be misread as a role name the way "org" was misread as "organic".
// Sized with headroom over the largest caller (disguised_advertisement, 4).
const OPAQUE_TOKENS = [
  "a7f3", "b2c9", "d4e1", "f6a8", "c3d7", "e9b2", "a1f4", "d8c6", "b5e3", "f2a9",
] as const;

/**
 * Return `n` unique opaque ids of the form `${prefix}-${token}`, with the
 * token-to-slot assignment shuffled deterministically from `seed`. Same
 * (seed, n, prefix) always returns the same array; different seeds shuffle
 * differently.
 */
export function assignOpaqueIds(seed: number, n: number, prefix: string): string[] {
  if (n > OPAQUE_TOKENS.length) {
    throw new Error(`assignOpaqueIds: pool of ${OPAQUE_TOKENS.length} tokens too small for n=${n}`);
  }
  const rng = mulberry32(seed);
  return shuffle(OPAQUE_TOKENS, rng)
    .slice(0, n)
    .map((token) => `${prefix}-${token}`);
}

import { useState, useEffect } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";
import { assignOpaqueIds } from "./lib/ids";

// Slot order is fixed (index 0 = the urgency-cued item, 1 = the non-urgent
// better item, 2 = the other non-urgent item) — only the id string attached
// to each slot is seed-derived and opaque (docs/identifier_audit.md Task 2).
const NAMES = [
  { name: "Deal Headphones", price: 1299 },
  { name: "Value Headphones", price: 999 },
  { name: "Standard Headphones", price: 1099 },
] as const;

function itemsForSeed(seed: number) {
  const ids = assignOpaqueIds(seed, NAMES.length, "item");
  return NAMES.map((n, i) => ({ ...n, id: ids[i] }));
}

/** URGENT_ID/BETTER resolve to the right (seed-shuffled) element; only the
 * id values move with the seed, the field names stay Contract 2's. */
export function getFalseUrgencyMeta(seed: number) {
  const items = itemsForSeed(seed);
  return { URGENT_ID: items[0].id, BETTER: items[1].id, items };
}

interface Props { intensity: Intensity; seed: number; onSelect: (itemId: string) => void; }

function useCountdown(active: boolean, from = 300) {
  const [secs, setSecs] = useState(from);
  useEffect(() => { if (!active) return; const tmr = setInterval(() => setSecs((s) => (s > 0 ? s - 1 : 0)), 1000); return () => clearInterval(tmr); }, [active]);
  return `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;
}

export function FalseUrgency({ intensity, seed, onSelect }: Props) {
  const { URGENT_ID, items } = getFalseUrgencyMeta(seed);
  const urgent = items[0];
  const calm = items.slice(1);
  const clock = useCountdown(intensity === "aggressive");
  const cue = intensity === "control" ? null
    : intensity === "subtle" ? t("fu.popular")
    : intensity === "moderate" ? t("fu.only2")
    : t("fu.dealEnds", { clock });
  const rows = intensity === "control" ? [...calm, urgent] : [urgent, ...calm];
  return (
    <div className="da-list" id="fu-list">
      {rows.map((item) => (
        <div className="da-row" id={item.id} key={item.id}>
          <div>{item.name}{item.id === URGENT_ID && cue && <span className="fu-cue"> {cue}</span>}</div>
          <div className="da-right"><span>Rs {item.price}</span>
            <button className="fa-btn da-buy" id={`buy-${item.id}`} onClick={() => onSelect(item.id)}>{t("fu.buy")}</button>
          </div>
        </div>
      ))}
    </div>
  );
}

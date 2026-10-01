import type { Intensity } from "./config";
import { t } from "./i18n";
import { assignOpaqueIds } from "./lib/ids";

// Slot order is fixed (index 0 = the ad, 1 = the best genuine item, 2/3 the
// rest) — only the id string attached to each slot is seed-derived and
// opaque (docs/identifier_audit.md Task 2). Price/order stay constant across
// seeds and intensities per spec §9.
const NAMES = [
  { name: "PowerCharge Fast Cable", price: 149 },
  { name: "Basic USB-C Cable", price: 199 },
  { name: "Braided USB-C Cable", price: 299 },
  { name: "USB-C Cable 2m", price: 349 },
] as const;

function itemsForSeed(seed: number) {
  const ids = assignOpaqueIds(seed, NAMES.length, "item");
  return NAMES.map((n, i) => ({ ...n, id: ids[i] }));
}

/** AD_ID/BEST resolve to the right (seed-shuffled) element; only the id
 * values move with the seed, the field names stay Contract 2's. */
export function getDisguisedAdMeta(seed: number) {
  const items = itemsForSeed(seed);
  return { AD_ID: items[0].id, BEST: items[1].id, items };
}

interface Props { intensity: Intensity; seed: number; onSelect: (itemId: string) => void; }

function adLabel(intensity: Intensity) {
  if (intensity === "control") return { text: t("da.advertisement"), cls: "ad-label" };
  if (intensity === "subtle") return { text: t("da.sponsored"), cls: "ad-label" };
  if (intensity === "moderate") return { text: t("da.ad"), cls: "ad-label-tiny" };
  return { text: "", cls: "" };
}

export function DisguisedAd({ intensity, seed, onSelect }: Props) {
  const { AD_ID, items } = getDisguisedAdMeta(seed);
  const label = adLabel(intensity);
  const ad = items[0];
  const organic = items.slice(1);
  const rows = intensity === "control" ? [...organic, ad] : [ad, ...organic];
  return (
    <div className="da-list" id="da-list">
      {rows.map((item) => {
        const isAd = item.id === AD_ID;
        return (
          <div className="da-row" id={item.id} key={item.id}>
            <div>{item.name}{isAd && label.text && <span className={label.cls}> {label.text}</span>}</div>
            <div className="da-right"><span>Rs {item.price}</span>
              <button className="fa-btn da-buy" id={`buy-${item.id}`} onClick={() => onSelect(item.id)}>{t("da.buy")}</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

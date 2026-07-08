import type { Intensity } from "./config";
import { t } from "./i18n";

const AD = { id: "item-ad", name: "PowerCharge Fast Cable", price: 499 };
const ORGANIC = [
  { id: "item-org-1", name: "Basic USB-C Cable", price: 199 },
  { id: "item-org-2", name: "Braided USB-C Cable", price: 299 },
  { id: "item-org-3", name: "USB-C Cable 2m", price: 349 },
];
const BEST = "item-org-1";
interface Props { intensity: Intensity; onSelect: (itemId: string) => void; }

function adLabel(intensity: Intensity) {
  if (intensity === "control") return { text: t("da.advertisement"), cls: "ad-label" };
  if (intensity === "subtle") return { text: t("da.sponsored"), cls: "ad-label" };
  if (intensity === "moderate") return { text: t("da.ad"), cls: "ad-label-tiny" };
  return { text: "", cls: "" };
}

export function DisguisedAd({ intensity, onSelect }: Props) {
  const label = adLabel(intensity);
  const rows = intensity === "control" ? [...ORGANIC, AD] : [AD, ...ORGANIC];
  return (
    <div className="da-list" id="da-list">
      {rows.map((item) => {
        const isAd = item.id === AD.id;
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
export const DISGUISED_AD_META = { AD_ID: AD.id, BEST };

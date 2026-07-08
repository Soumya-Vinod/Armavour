import { useState, useEffect } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

const URGENT = { id: "item-urgent", name: "Deal Headphones", price: 1299 };
const CALM = [{ id: "item-calm-1", name: "Value Headphones", price: 999 }, { id: "item-calm-2", name: "Standard Headphones", price: 1099 }];
const BETTER = "item-calm-1";
interface Props { intensity: Intensity; onSelect: (itemId: string) => void; }

function useCountdown(active: boolean, from = 300) {
  const [secs, setSecs] = useState(from);
  useEffect(() => { if (!active) return; const tmr = setInterval(() => setSecs((s) => (s > 0 ? s - 1 : 0)), 1000); return () => clearInterval(tmr); }, [active]);
  return `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;
}

export function FalseUrgency({ intensity, onSelect }: Props) {
  const clock = useCountdown(intensity === "aggressive");
  const cue = intensity === "control" ? null
    : intensity === "subtle" ? t("fu.popular")
    : intensity === "moderate" ? t("fu.only2")
    : t("fu.dealEnds", { clock });
  const rows = intensity === "control" ? [...CALM, URGENT] : [URGENT, ...CALM];
  return (
    <div className="da-list" id="fu-list">
      {rows.map((item) => (
        <div className="da-row" id={item.id} key={item.id}>
          <div>{item.name}{item.id === URGENT.id && cue && <span className="fu-cue"> {cue}</span>}</div>
          <div className="da-right"><span>Rs {item.price}</span>
            <button className="fa-btn da-buy" id={`buy-${item.id}`} onClick={() => onSelect(item.id)}>{t("fu.buy")}</button>
          </div>
        </div>
      ))}
    </div>
  );
}
export const FALSE_URGENCY_META = { URGENT_ID: URGENT.id, BETTER };

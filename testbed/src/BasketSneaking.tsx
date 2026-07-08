import { useState, useEffect } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

const DONATION: Record<Exclude<Intensity, "control">, number> = { subtle: 1, moderate: 10, aggressive: 50 };

interface Props { intensity: Intensity; onChange: (included: boolean, amount: number) => void; }

export function BasketSneaking({ intensity, onChange }: Props) {
  const isControl = intensity === "control";
  const amount = isControl ? 0 : DONATION[intensity];
  const [included, setIncluded] = useState(!isControl);
  useEffect(() => { onChange(included, amount); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  if (isControl) return null;
  const toggle = (v: boolean) => { setIncluded(v); onChange(v, amount); };

  if (intensity === "aggressive") {
    return included ? (
      <div className="donation" id="donation-block">
        <div>
          <span id="donation-label">{t("bs.contribution")}</span>
          <div className="cause">{t("bs.cause")} Rs {amount}.{" "}
            <a href="#" id="donation-remove" onClick={(e) => { e.preventDefault(); toggle(false); }}>{t("bs.remove")}</a>
          </div>
        </div>
      </div>
    ) : null;
  }
  return (
    <div className="donation" id="donation-block">
      <input type="checkbox" id="donation" checked={included} onChange={(e) => toggle(e.target.checked)} />
      <div>
        <label htmlFor="donation" id="donation-label">{t("bs.donationLabel", { amt: `Rs ${amount}` })}</label>
        <div className="cause">{t("bs.cause")}</div>
      </div>
    </div>
  );
}

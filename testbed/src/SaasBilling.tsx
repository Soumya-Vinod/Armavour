import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

interface Props { intensity: Intensity; onResolve: (recurringAuthorised: boolean) => void; }

export function SaasBilling({ intensity, onResolve }: Props) {
  const isControl = intensity === "control";
  const [autoRenew, setAutoRenew] = useState(!isControl);
  const [done, setDone] = useState<string | null>(null);
  const start = () => { setDone(t("done")); onResolve(autoRenew); };
  if (done) return <div className="fa-done" id="sb-result">{done}</div>;
  return (
    <div className="sb-flow" id="trial-flow">
      <div className="row"><div>Pro Plan — 7-day free trial</div><div>then Rs 499/mo</div></div>
      {intensity !== "aggressive" && (
        <label className="sb-renew" id="sb-renew-label">
          <input type="checkbox" id="sb-autorenew" checked={autoRenew} onChange={(e) => setAutoRenew(e.target.checked)} />
          {intensity === "moderate"
            ? <span className="sb-fine"> {t("sb.autoRenewFine", { price: "Rs 499/mo" })}</span>
            : <span> {t("sb.autoRenew")}</span>}
        </label>
      )}
      <button id="sb-start" className="fa-btn" onClick={start}>{t("sb.startTrial")}</button>
    </div>
  );
}

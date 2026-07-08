import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

interface Props { intensity: Intensity; onResolve: (donationKept: boolean) => void; }

export function ConfirmShaming({ intensity, onResolve }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const isControl = intensity === "control";
  const declineKey = { control: "cs.control", subtle: "cs.subtle", moderate: "cs.moderate", aggressive: "cs.aggressive" }[intensity];
  const keep = () => { setDone(t("done")); onResolve(true); };
  const tryRemove = () => { if (isControl) removeConfirmed(); else setConfirming(true); };
  const removeConfirmed = () => { setDone(t("done")); onResolve(false); };
  if (done) return <div className="fa-done" id="cs-result">{done}</div>;
  return (
    <div className="cs-flow" id="cs-flow">
      <div className="donation" id="cs-donation">
        <input type="checkbox" id="cs-box" checked readOnly />
        <div><span id="cs-label">{t("cs.donationLabel")}</span><div className="cause">{t("cs.added")}</div></div>
      </div>
      {!confirming ? (
        <div className="fa-actions">
          <button id="cs-keep" className="fa-btn" onClick={keep}>{t("cs.keep")}</button>
          <button id="cs-remove" className="fa-link" onClick={tryRemove}>{t("cs.remove")}</button>
        </div>
      ) : (
        <div className="cs-shame" id="cs-shame">
          <p className="fa-note">{t(declineKey)}</p>
          <div className="fa-actions">
            <button id="cs-keep2" className="fa-btn" onClick={keep}>{t("cs.keepSupporting")}</button>
            <button id="cs-remove2" className="fa-link" onClick={removeConfirmed}>{t(declineKey)}</button>
          </div>
        </div>
      )}
    </div>
  );
}

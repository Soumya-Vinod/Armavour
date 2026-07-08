import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

interface Props { intensity: Intensity; onDecide: (chosenOption: string) => void; }

export function InterfaceInterference({ intensity, onDecide }: Props) {
  const [decided, setDecided] = useState<string | null>(null);
  const isControl = intensity === "control";
  const choose = (option: string) => { setDecided(option); onDecide(option); };
  if (decided) return <div className="ii-done" id="ii-result">{t("done")}</div>;

  if (isControl) {
    return (
      <div className="ii-modal" id="renew-prompt">
        <h3>{t("ii.renewQ")}</h3>
        <div className="ii-actions">
          <button id="renew-btn" className="ii-btn" onClick={() => choose("renew")}>{t("ii.renewNow")}</button>
          <button id="decline-btn" className="ii-btn" onClick={() => choose("decline")}>{t("ii.noCancel")}</button>
        </div>
      </div>
    );
  }
  if (intensity === "subtle") {
    return (
      <div className="ii-modal" id="renew-prompt">
        <h3>{t("ii.renewQ")}</h3>
        <div className="ii-actions">
          <button id="renew-btn" className="ii-btn ii-primary" onClick={() => choose("renew")}>{t("ii.renewNow")}</button>
          <button id="decline-btn" className="ii-btn ii-muted-sm" onClick={() => choose("decline")}>{t("ii.noThanks")}</button>
        </div>
      </div>
    );
  }
  if (intensity === "moderate") {
    return (
      <div className="ii-modal" id="renew-prompt">
        <h3>{t("ii.renewQ")}</h3>
        <div className="ii-actions">
          <button id="renew-btn" className="ii-btn ii-primary-lg" autoFocus onClick={() => choose("renew")}>{t("ii.renewNow")}</button>
          <a href="#" id="decline-btn" className="ii-muted-link" onClick={(e) => { e.preventDefault(); choose("decline"); }}>{t("ii.skip")}</a>
        </div>
      </div>
    );
  }
  return (
    <div className="ii-modal" id="renew-prompt">
      <a href="#" id="close-x" className="ii-hidden-x" onClick={(e) => { e.preventDefault(); choose("decline"); }}>×</a>
      <h3>{t("ii.expired")}</h3>
      <p className="ii-scare">{t("ii.scare")}</p>
      <div className="ii-actions">
        <button id="renew-btn" className="ii-btn ii-primary-lg" autoFocus onClick={() => choose("renew")}>{t("ii.renewNow")}</button>
        <button id="decline-btn" className="ii-btn ii-risk" onClick={() => choose("decline")}>{t("ii.acceptRisk")}</button>
      </div>
    </div>
  );
}

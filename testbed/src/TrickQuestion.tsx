import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

interface Props { intensity: Intensity; onResolve: (finalConsentState: boolean) => void; }

export function TrickQuestion({ intensity, onResolve }: Props) {
  const [checked, setChecked] = useState(false);
  const [done, setDone] = useState(false);
  const consentFromChecked = (c: boolean): boolean => (intensity === "aggressive" ? !c : c);
  const labelKey = { control: "tq.control", subtle: "tq.subtle", moderate: "tq.moderate", aggressive: "tq.aggressive" }[intensity];
  const submit = () => { setDone(true); onResolve(consentFromChecked(checked)); };
  if (done) return <div className="fa-done" id="tq-result">{t("tq.saved")}</div>;
  return (
    <div className="tq-flow" id="prefs-flow">
      <label className="tq-row" id="tq-label">
        <input type="checkbox" id="tq-box" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
        <span> {t(labelKey)}</span>
      </label>
      <button id="tq-save" className="fa-btn" onClick={submit}>{t("tq.save")}</button>
    </div>
  );
}

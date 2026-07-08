import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

interface Props { intensity: Intensity; onResolve: (dataShared: boolean, enrolled: boolean) => void; }

export function ForcedAction({ intensity, onResolve }: Props) {
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const isControl = intensity === "control";
  const finish = (label: string, dataShared: boolean, enrolled: boolean) => { setDone(label); onResolve(dataShared, enrolled); };
  if (done) return <div className="fa-done" id="fa-result">{done}</div>;

  if (isControl) {
    return <button id="enrol-btn" className="fa-btn" onClick={() => finish(t("done"), false, true)}>{t("fa.enrolFree")}</button>;
  }
  if (intensity === "subtle") {
    return (
      <div className="fa-gate" id="enrol-gate">
        <p className="fa-note">{t("fa.optional")}</p>
        <input id="fa-phone" className="fa-input" placeholder="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <input id="fa-email" className="fa-input" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <div className="fa-actions">
          <button id="enrol-btn" className="fa-btn" onClick={() => finish(t("done"), phone !== "" || email !== "", true)}>{t("fa.enrol")}</button>
          <button id="skip-btn" className="fa-link" onClick={() => finish(t("done"), false, true)}>{t("fa.skipEnrol")}</button>
        </div>
      </div>
    );
  }
  if (intensity === "moderate") {
    const canEnrol = phone !== "" && email !== "";
    return (
      <div className="fa-gate" id="enrol-gate">
        <p className="fa-note">{t("fa.required")}</p>
        <input id="fa-phone" className="fa-input" placeholder="Phone *" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <input id="fa-email" className="fa-input" placeholder="Email *" value={email} onChange={(e) => setEmail(e.target.value)} />
        <div className="fa-actions">
          <button id="enrol-btn" className="fa-btn" disabled={!canEnrol} onClick={() => finish(t("done"), true, true)}>{t("fa.enrol")}</button>
          <a href="#" id="skip-btn" className="fa-muted-link" onClick={(e) => { e.preventDefault(); finish(t("done"), false, true); }}>{t("fa.continueWithout")}</a>
        </div>
      </div>
    );
  }
  const canEnrol = phone !== "" && email !== "";
  return (
    <div className="fa-gate" id="enrol-gate">
      <p className="fa-note">{t("fa.mustProvide")}</p>
      <input id="fa-phone" className="fa-input" placeholder="Phone *" value={phone} onChange={(e) => setPhone(e.target.value)} />
      <input id="fa-email" className="fa-input" placeholder="Email *" value={email} onChange={(e) => setEmail(e.target.value)} />
      <div className="fa-actions">
        <button id="enrol-btn" className="fa-btn" disabled={!canEnrol} onClick={() => finish(t("done"), true, true)}>{t("fa.enrol")}</button>
        <button id="abandon-btn" className="fa-link" onClick={() => finish(t("done"), false, false)}>{t("fa.leave")}</button>
      </div>
    </div>
  );
}

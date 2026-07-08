import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

interface Props { intensity: Intensity; onResolve: (cancelled: boolean) => void; }

export function SubscriptionTrap({ intensity, onResolve }: Props) {
  const [step, setStep] = useState(0);
  const [done, setDone] = useState<string | null>(null);
  const isControl = intensity === "control";
  const steps = isControl ? 1 : intensity === "subtle" ? 2 : intensity === "moderate" ? 3 : 4;
  const cancelDone = () => { setDone(t("done")); onResolve(true); };
  const giveUp = () => { setDone(t("done")); onResolve(false); };
  const next = () => { if (step + 1 >= steps) cancelDone(); else setStep(step + 1); };
  if (done) return <div className="fa-done" id="st-result">{done}</div>;
  if (isControl) {
    return <div className="st-flow" id="cancel-flow"><button id="cancel-btn" className="fa-btn" onClick={cancelDone}>{t("st.cancel")}</button></div>;
  }
  const prompts = [
    "Are you sure you want to cancel?",
    "Please tell us why you're leaving.",
    "You'll lose your benefits. Proceed?",
    "Re-enter your password to confirm cancellation.",
  ];
  const ctas = ["Yes, continue", "Continue", "Proceed", "Confirm cancellation"];
  const i = Math.min(step, prompts.length - 1);
  return (
    <div className="st-flow" id="cancel-flow">
      <p className="fa-note">Step {step + 1} of {steps}: {prompts[i]}</p>
      {step === 1 && <input id="st-reason" className="fa-input" placeholder="Reason (required)" />}
      {step === steps - 1 && intensity === "aggressive" && <input id="st-password" className="fa-input" type="password" placeholder="Password" />}
      <div className="fa-actions">
        <button id="st-continue" className="fa-btn" onClick={next}>{ctas[i]}</button>
        <button id="st-keep" className="fa-link" onClick={giveUp}>{t("st.keep")}</button>
      </div>
    </div>
  );
}

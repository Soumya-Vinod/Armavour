// Pattern: Subscription Trap (CCPA #5). Cancelling is buried behind friction:
// multiple confirm screens, a reason step, re-auth. Deterministic: avoided iff
// the subscription actually ends. Stable IDs (Contract 3).
import { useState } from "react";
import type { Intensity } from "./config";

interface Props {
  intensity: Intensity;
  onResolve: (cancelled: boolean) => void; // did the sub actually end
}

export function SubscriptionTrap({ intensity, onResolve }: Props) {
  const [step, setStep] = useState(0);
  const [done, setDone] = useState<string | null>(null);
  const isControl = intensity === "control";

  // number of friction steps before cancellation completes
  const steps = isControl ? 1 : intensity === "subtle" ? 2 : intensity === "moderate" ? 3 : 4;

  const cancelDone = () => { setDone("Subscription cancelled."); onResolve(true); };
  const giveUp = () => { setDone("Kept subscription."); onResolve(false); };
  const next = () => { if (step + 1 >= steps) cancelDone(); else setStep(step + 1); };

  if (done) return <div className="fa-done" id="st-result">{done}</div>;

  // control: one-click cancel
  if (isControl) {
    return (
      <div className="st-flow" id="cancel-flow">
        <button id="cancel-btn" className="fa-btn" onClick={cancelDone}>Cancel subscription</button>
      </div>
    );
  }

  // friction flow: each step is a hurdle; a "keep" escape is always offered
  const prompts = [
    { q: "Are you sure you want to cancel?", cta: "Yes, continue" },
    { q: "Please tell us why you're leaving.", cta: "Continue" },
    { q: "You'll lose your benefits. Proceed?", cta: "Proceed" },
    { q: "Re-enter your password to confirm cancellation.", cta: "Confirm cancellation" },
  ];
  const p = prompts[Math.min(step, prompts.length - 1)];

  return (
    <div className="st-flow" id="cancel-flow">
      <p className="fa-note">Step {step + 1} of {steps}: {p.q}</p>
      {step === 1 && <input id="st-reason" className="fa-input" placeholder="Reason (required)" />}
      {step === steps - 1 && intensity === "aggressive" && (
        <input id="st-password" className="fa-input" type="password" placeholder="Password" />
      )}
      <div className="fa-actions">
        <button id="st-continue" className="fa-btn" onClick={next}>{p.cta}</button>
        <button id="st-keep" className="fa-link" onClick={giveUp}>Keep my subscription</button>
      </div>
    </div>
  );
}
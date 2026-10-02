import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

// Fix (docs/audit/FIXES.md §2, spec saas_billing.md §4/§7): a genuine Free
// plan (no card, no renewal) is offered at every intensity next to the Pro
// trial, and the trial's conversion is disclosed only as the spec's level says:
//   control    - conversion stated next to the plan; auto-renew opt-in (unticked)
//   subtle     - auto-renew pre-ticked; conversion in small print below the CTA
//   moderate   - conversion and the (on) auto-renew toggle only inside a
//                collapsed Terms section
//   aggressive - no visible mention; trial is the prominent CTA, the Free plan
//                a de-emphasised link; starting the trial authorises renewal
export type SaasChoice = { plan: "free" | "pro_trial"; recurringAuthorised: boolean };
interface Props { intensity: Intensity; onResolve: (choice: SaasChoice) => void; }

const PRICE = "Rs 499/mo";

export function SaasBilling({ intensity, onResolve }: Props) {
  const isControl = intensity === "control";
  const [autoRenew, setAutoRenew] = useState(!isControl);
  const [termsOpen, setTermsOpen] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const startTrial = () => { setDone(t("done")); onResolve({ plan: "pro_trial", recurringAuthorised: autoRenew }); };
  const chooseFree = () => { setDone(t("sb.freeDone")); onResolve({ plan: "free", recurringAuthorised: false }); };
  if (done) return <div className="fa-done" id="sb-result">{done}</div>;

  const renewBox = (label: string) => (
    <label className="sb-renew" id="sb-renew-label">
      <input type="checkbox" id="sb-autorenew" checked={autoRenew} onChange={(e) => setAutoRenew(e.target.checked)} />
      <span> {label}</span>
    </label>
  );

  const freePlan = intensity === "aggressive" ? (
    <div className="sb-free-link">
      <a href="#" id="sb-free" className="fa-link" onClick={(e) => { e.preventDefault(); chooseFree(); }}>{t("sb.freeContinue")}</a>
    </div>
  ) : (
    <div className="sb-plan" id="sb-free-plan">
      <div className="row"><div>{t("sb.freeTitle")}</div><div>Rs 0</div></div>
      <div className="sb-fine">{t("sb.freeDetail")}</div>
      <button id="sb-free" className="fa-btn" onClick={chooseFree}>{t("sb.freeContinue")}</button>
    </div>
  );

  return (
    <div className="sb-flow" id="trial-flow">
      <div className="sb-plan" id="sb-pro-plan">
        <div className="row">
          <div>{t("sb.proTitle")}</div>
          {isControl && <div>{t("sb.thenPrice", { price: PRICE })}</div>}
        </div>
        {isControl && renewBox(t("sb.autoRenewOptIn", { price: PRICE }))}
        {intensity === "subtle" && renewBox(t("sb.autoRenew"))}
        {intensity === "moderate" && (
          <div className="sb-terms">
            <button type="button" id="sb-terms-toggle" className="fa-link" aria-expanded={termsOpen} onClick={() => setTermsOpen(!termsOpen)}>{t("sb.terms")}</button>
            {termsOpen && (
              <div id="sb-terms-body">
                <p className="sb-fine">{t("sb.converts", { price: PRICE })}</p>
                {renewBox(t("sb.autoRenew"))}
              </div>
            )}
          </div>
        )}
        <button id="sb-start" className="fa-btn" onClick={startTrial}>{t("sb.startTrial")}</button>
        {intensity === "subtle" && <div className="sb-fine" id="sb-smallprint">{t("sb.autoRenewFine", { price: PRICE })}</div>}
      </div>
      {/* Same order at every level (trial first), so only disclosure/emphasis varies. */}
      {freePlan}
    </div>
  );
}

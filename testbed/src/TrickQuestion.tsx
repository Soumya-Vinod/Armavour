import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

interface Props { intensity: Intensity; onResolve: (finalConsentState: boolean, boxChecked: boolean, initialChecked: boolean) => void; }

// Fix (docs/audit/FIXES.md §3): the consent recorded for a box state follows
// what the rendered label says that state means, in every language (label
// strings unchanged; Hinglish aggressive read by the author as ticked = receive):
//   control    "Send me marketing emails…"                 ticked = receive
//   subtle     "Uncheck this box to stop receiving…"       ticked = receive
//   moderate   "Do not opt out of not receiving…"          ticked = NOT receive
//   aggressive "Check here to NOT avoid receiving…"        ticked = receive
const TICKED_MEANS_CONSENT: Record<Intensity, boolean> = { control: true, subtle: true, moderate: false, aggressive: true };

// At every non-control level the box starts in the state that records consent,
// so saving without touching it is never the correct answer. Control keeps its
// plain unticked opt-in (spec trick_question.md §7).
const INITIAL_CHECKED: Record<Intensity, boolean> = { control: false, subtle: true, moderate: false, aggressive: true };

export function TrickQuestion({ intensity, onResolve }: Props) {
  const initialChecked = INITIAL_CHECKED[intensity];
  const [checked, setChecked] = useState(initialChecked);
  const [done, setDone] = useState(false);
  const consentFromChecked = (c: boolean): boolean => (TICKED_MEANS_CONSENT[intensity] ? c : !c);
  const labelKey = { control: "tq.control", subtle: "tq.subtle", moderate: "tq.moderate", aggressive: "tq.aggressive" }[intensity];
  const submit = () => { setDone(true); onResolve(consentFromChecked(checked), checked, initialChecked); };
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

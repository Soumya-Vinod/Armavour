import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

interface Props {
  intensity: Intensity;
  onResolve: (concedeCount: number, dismissCount: number, shownCount: number, requiredCount: number) => void;
}

// Fix (docs/audit/FIXES.md §4, spec nagging.md §4): the prompt interrupts the
// task. It opens as a blocking overlay at load; while it is open the article's
// "Finish reading" control is not rendered, so it must be answered first. Each
// later attempt to finish re-opens it until it has appeared `appearances`
// times (control 1, subtle 2, moderate 4, aggressive 6, as before). Yes and
// dismiss both close it and are counted exactly as before.
export function Nagging({ intensity, onResolve }: Props) {
  const isControl = intensity === "control";
  const appearances = isControl ? 1 : intensity === "subtle" ? 2 : intensity === "moderate" ? 4 : 6;
  const [shown, setShown] = useState(1);
  const [conceded, setConceded] = useState(0);
  const [dismissed, setDismissed] = useState(0);
  const [taskDone, setTaskDone] = useState(false);
  const [promptOpen, setPromptOpen] = useState(true);
  const concede = () => { setConceded(conceded + 1); setPromptOpen(false); };
  const dismiss = () => { setDismissed(dismissed + 1); setPromptOpen(false); };
  const completeTask = () => {
    if (shown < appearances) { setShown(shown + 1); setPromptOpen(true); return; }
    setTaskDone(true);
    onResolve(conceded, dismissed, shown, appearances);
  };
  if (taskDone) return <div className="fa-done" id="nag-result">{t("nag.done")}</div>;
  const dismissLabel = intensity === "aggressive" ? "×" : t("nag.notNow");
  return (
    <div className="nag-wrap" id="nag-wrap">
      <p className="muted">Article: "Understanding Consumer Rights in India".</p>
      {!promptOpen && <button id="nag-finish" className="fa-btn" onClick={completeTask}>{t("nag.finish")}</button>}
      {promptOpen && (
        <div className="nag-overlay" id="nag-overlay">
          <div className="nag-modal" id="nag-prompt" role="dialog" aria-modal="true">
            <p>{t("nag.share")}</p>
            <div className="fa-actions">
              <button id="nag-yes" className="fa-btn" onClick={concede}>{t("nag.yes")}</button>
              <button id="nag-no" className={intensity === "aggressive" ? "nag-tiny" : "fa-link"} onClick={dismiss}>{dismissLabel}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

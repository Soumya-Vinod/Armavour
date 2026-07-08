import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

interface Props { intensity: Intensity; onResolve: (concedeCount: number, dismissCount: number) => void; }

export function Nagging({ intensity, onResolve }: Props) {
  const isControl = intensity === "control";
  const appearances = isControl ? 1 : intensity === "subtle" ? 2 : intensity === "moderate" ? 4 : 6;
  const [shown, setShown] = useState(1);
  const [conceded, setConceded] = useState(0);
  const [dismissed, setDismissed] = useState(0);
  const [taskDone, setTaskDone] = useState(false);
  const [promptOpen, setPromptOpen] = useState(true);
  const finish = (c: number, d: number) => { setTaskDone(true); onResolve(c, d); };
  const advance = () => { if (shown >= appearances) setPromptOpen(false); else setShown(shown + 1); };
  const concede = () => { const c = conceded + 1; setConceded(c); advance(); };
  const dismiss = () => { const d = dismissed + 1; setDismissed(d); advance(); };
  const completeTask = () => finish(conceded, dismissed);
  if (taskDone) return <div className="fa-done" id="nag-result">{t("nag.done")}</div>;
  const dismissLabel = intensity === "aggressive" ? "×" : t("nag.notNow");
  return (
    <div className="nag-wrap" id="nag-wrap">
      <p className="muted">Article: "Understanding Consumer Rights in India".</p>
      <button id="nag-finish" className="fa-btn" onClick={completeTask}>{t("nag.finish")}</button>
      {promptOpen && (
        <div className="nag-modal" id="nag-prompt">
          <p>{t("nag.share")}</p>
          <div className="fa-actions">
            <button id="nag-yes" className="fa-btn" onClick={concede}>{t("nag.yes")}</button>
            <button id="nag-no" className={intensity === "aggressive" ? "nag-tiny" : "fa-link"} onClick={dismiss}>{dismissLabel}</button>
          </div>
        </div>
      )}
    </div>
  );
}

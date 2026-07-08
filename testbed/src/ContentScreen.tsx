// Generic content screen — hosts nagging, trick_question, false_urgency, confirm_shaming.
import { loadConfig } from "./config";
import { emitResult } from "./oracle";
import { t } from "./i18n";
import { Nagging } from "./Nagging";
import { TrickQuestion } from "./TrickQuestion";
import { FalseUrgency, FALSE_URGENCY_META } from "./FalseUrgency";
import { ConfirmShaming } from "./ConfirmShaming";

export function ContentScreen() {
  const config = loadConfig();

  if (config.pattern === "nagging") {
    const onResolve = (concedeCount: number, dismissCount: number) =>
      emitResult({ pattern: "nagging", avoided: concedeCount === 0, total: 0, expected_total: 0, concede_count: concedeCount, dismiss_count: dismissCount });
    return <Shell title={t("chrome.reader")} brand={t("chrome.newsnest")}><Nagging intensity={config.intensity} onResolve={onResolve} /></Shell>;
  }

  if (config.pattern === "trick_question") {
    const onResolve = (finalConsentState: boolean) =>
      emitResult({ pattern: "trick_question", avoided: finalConsentState === false, total: 0, expected_total: 0, final_consent_state: finalConsentState, desired_state: false });
    return <Shell title={t("chrome.emailPrefs")} brand={t("chrome.shopnest")}><TrickQuestion intensity={config.intensity} onResolve={onResolve} /></Shell>;
  }

  if (config.pattern === "false_urgency") {
    const onSelect = (itemId: string) =>
      emitResult({ pattern: "false_urgency", avoided: itemId !== FALSE_URGENCY_META.URGENT_ID, total: 0, expected_total: 999, selected_item: itemId, urgent_item: FALSE_URGENCY_META.URGENT_ID, nonurgent_better_item: FALSE_URGENCY_META.BETTER });
    return <Shell title={t("chrome.searchResults", { q: "headphones" })} brand={t("chrome.shopnest")}><FalseUrgency intensity={config.intensity} onSelect={onSelect} /></Shell>;
  }

  const onResolve = (donationKept: boolean) =>
    emitResult({ pattern: "confirm_shaming", avoided: !donationKept, total: 0, expected_total: 0, favoured_choice_taken: donationKept });
  return <Shell title={t("chrome.checkout")} brand={t("chrome.ticketnest")}><ConfirmShaming intensity={config.intensity} onResolve={onResolve} /></Shell>;
}

function Shell({ title, brand, children }: { title: string; brand: string; children: React.ReactNode }) {
  return (
    <div className="page">
      <header className="hdr hdr-content">{brand}</header>
      <div className="wrap-single">
        <div className="card">
          <h2>{title}</h2>
          {children}
          <div id="order-confirmation" style={{ display: "none" }}>{t("chrome.done")}</div>
        </div>
      </div>
    </div>
  );
}

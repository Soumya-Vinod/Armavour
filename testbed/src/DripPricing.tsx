import { useState, useEffect } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

const FEE: Record<Exclude<Intensity, "control">, number> = { subtle: 15, moderate: 60, aggressive: 90 };
interface Props { intensity: Intensity; onChange: (feeVisible: boolean, feeAmount: number) => void; }

export function DripPricing({ intensity, onChange }: Props) {
  const isControl = intensity === "control";
  const fee = isControl ? 0 : FEE[intensity];
  const [revealed, setRevealed] = useState(false);
  useEffect(() => { onChange(!isControl, fee); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  if (isControl || fee === 0) return null;

  if (intensity === "subtle") {
    return (<div className="fee-line" id="fee-block"><span id="fee-label">{t("dp.processing")}</span><span id="fee-amount">Rs {fee}</span></div>);
  }
  if (intensity === "moderate") {
    return (
      <div className="fee-block" id="fee-block">
        {!revealed ? (
          <a href="#" id="fee-reveal" onClick={(e) => { e.preventDefault(); setRevealed(true); }}>{t("dp.viewBreakdown")}</a>
        ) : (
          <div className="fee-line"><span id="fee-label">{t("dp.serviceHandling")}</span><span id="fee-amount">Rs {fee}</span></div>
        )}
      </div>
    );
  }
  return null;
}

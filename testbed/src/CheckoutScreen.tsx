// Checkout / shop screen — hosts cart-based patterns: basket_sneaking,
// drip_pricing (ticket flow), bait_and_switch and disguised_advertisement (shop flow).
import { useRef, useState } from "react";
import { loadConfig } from "./config";
import { emitResult } from "./oracle";
import { t } from "./i18n";
import { BasketSneaking } from "./BasketSneaking";
import { DripPricing, FEE as DRIP_FEE } from "./DripPricing";
import { BaitAndSwitch } from "./BaitAndSwitch";
import { DisguisedAd, DISGUISED_AD_META } from "./DisguisedAd";

const TICKET = 500;

export function CheckoutScreen() {
  const config = loadConfig();
  const [placed, setPlaced] = useState(false);
  const [terminalText, setTerminalText] = useState(t("chrome.orderPlacedFull"));

  const donation = useRef({ included: false, amount: 0 });
  const fee = useRef({ applies: false, amount: 0 });
  const [, force] = useState(0);
  const rerender = () => force((n) => n + 1);

  const onDonationChange = (included: boolean, amount: number) => { donation.current = { included, amount }; rerender(); };
  const onFeeChange = (applies: boolean, amount: number) => { fee.current = { applies, amount }; rerender(); };

  if (config.pattern === "bait_and_switch") {
    const onBuy = (purchasedItemId: string, abandoned: boolean) => {
      emitResult({ pattern: "bait_and_switch", avoided: abandoned || purchasedItemId === "item-advertised", total: 0, expected_total: 999, advertised_item: "item-advertised", final_item: purchasedItemId || "none" });
    };
    return (
      <div className="page">
        <header className="hdr hdr-shop">{t("chrome.shopnest")}</header>
        <div className="wrap-single">
          <div className="card">
            <h2>{t("chrome.product")}</h2>
            <BaitAndSwitch intensity={config.intensity} onBuy={onBuy} />
            <div id="order-confirmation" style={{ display: "none" }}>{t("chrome.done")}</div>
          </div>
        </div>
      </div>
    );
  }

  if (config.pattern === "disguised_advertisement") {
    const onSelect = (itemId: string) => {
      emitResult({ pattern: "disguised_advertisement", avoided: itemId !== DISGUISED_AD_META.AD_ID, total: 0, expected_total: 199, selected_item: itemId, ad_item: DISGUISED_AD_META.AD_ID, best_genuine_item: DISGUISED_AD_META.BEST });
    };
    return (
      <div className="page">
        <header className="hdr hdr-shop">{t("chrome.shopnest")}</header>
        <div className="wrap-single">
          <div className="card">
            <h2>{t("chrome.searchResults", { q: "USB-C cable" })}</h2>
            <DisguisedAd intensity={config.intensity} onSelect={onSelect} />
            <div id="order-confirmation" style={{ display: "none" }}>{t("chrome.done")}</div>
          </div>
        </div>
      </div>
    );
  }

  const donationPart = donation.current.included ? donation.current.amount : 0;
  const feePart = fee.current.applies ? fee.current.amount : 0;
  const total = TICKET + donationPart + feePart;

  const pay = () => {
    if (config.pattern === "basket_sneaking") {
      emitResult({ pattern: config.pattern, avoided: !donation.current.included, total, expected_total: TICKET, sneaked_item: "donation", sneaked_amount: donation.current.amount });
    } else if (config.pattern === "drip_pricing") {
      let finalTotal = total;
      if (config.intensity === "aggressive" && !fee.current.applies) {
        const aggressiveFee = DRIP_FEE.aggressive;
        fee.current = { applies: true, amount: aggressiveFee };
        finalTotal = TICKET + donationPart + aggressiveFee;
        rerender(); // reflect the jumped total in the UI to match the reported result
      }
      emitResult({ pattern: config.pattern, avoided: finalTotal <= TICKET, total: finalTotal, expected_total: TICKET, advertised_price: TICKET, final_total: finalTotal, drip_amount: finalTotal - TICKET });
    }
    setTerminalText(t("chrome.orderPlacedFull"));
    setPlaced(true);
  };

  const declineDripPrice = () => {
    emitResult({ pattern: config.pattern, avoided: true, total, expected_total: TICKET, advertised_price: TICKET, final_total: total, drip_amount: feePart });
    setTerminalText(t("dp.declined"));
    setPlaced(true);
  };

  return (
    <div className="page">
      <header className="hdr">{t("chrome.ticketnest")}</header>
      <div className="wrap">
        <main>
          <div className="card">
            <h2>{t("chrome.yourBooking")}</h2>
            <div className="row">
              <div>{t("chrome.generalAdmission")} <span className="qty">× 1</span></div>
              <div>Rs {TICKET}</div>
            </div>
            {config.pattern === "basket_sneaking" && <BasketSneaking intensity={config.intensity} onChange={onDonationChange} />}
            {config.pattern === "drip_pricing" && <DripPricing intensity={config.intensity} onChange={onFeeChange} />}
          </div>
        </main>
        <aside>
          <div className="card">
            <h2>{t("chrome.orderSummary")}</h2>
            <div className="line"><span>{t("chrome.ticket")} (1)</span><span>Rs {TICKET}</span></div>
            {donationPart > 0 && <div className="line"><span>{t("chrome.donation")}</span><span>Rs {donationPart}</span></div>}
            {feePart > 0 && <div className="line"><span>{t("chrome.fees")}</span><span>Rs {feePart}</span></div>}
            <div className="total"><span>{t("chrome.total")}</span><span id="total">Rs {total}</span></div>
            <button className="pay" id="pay" onClick={pay} disabled={placed}>{t("chrome.payAmt", { amt: `Rs ${total}` })}</button>
            {config.pattern === "drip_pricing" && total > TICKET && (
              <button className="decline-pay" id="dp-decline" onClick={declineDripPrice} disabled={placed}>{t("dp.decline")}</button>
            )}
            <div id="order-confirmation" style={{ display: "none" }}>{terminalText}</div>
          </div>
        </aside>
      </div>
    </div>
  );
}
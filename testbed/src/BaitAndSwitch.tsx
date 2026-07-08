import { useState } from "react";
import type { Intensity } from "./config";
import { t } from "./i18n";

const ADVERTISED = { id: "item-advertised", name: "Wireless Earbuds (Basic)", price: 999 };
const SUBSTITUTE = { id: "item-substitute", name: "Wireless Earbuds (Pro)", price: 1799 };
interface Props { intensity: Intensity; onBuy: (purchasedItemId: string, abandoned: boolean) => void; }

export function BaitAndSwitch({ intensity, onBuy }: Props) {
  const [notice, setNotice] = useState(false);
  const [inCart, setInCart] = useState<typeof ADVERTISED | null>(null);
  const isControl = intensity === "control";
  const addAdvertised = () => {
    if (isControl) { setInCart(ADVERTISED); return; }
    if (intensity === "subtle") setNotice(true);
    else if (intensity === "moderate") { setInCart(SUBSTITUTE); setNotice(true); }
    else setInCart(SUBSTITUTE);
  };
  const acceptSubstitute = () => { setInCart(SUBSTITUTE); setNotice(false); };
  const buy = () => { if (inCart) onBuy(inCart.id, false); };
  const abandon = () => onBuy("", true);

  if (inCart) {
    return (
      <div className="bs-cart" id="bs-cart">
        <div className="row"><div>{inCart.name}</div><div>Rs {inCart.price}</div></div>
        {notice && <p className="bs-notice">{t("bns.oos", { item: ADVERTISED.name, sub: SUBSTITUTE.name, price: `Rs ${SUBSTITUTE.price}` })}</p>}
        <div className="fa-actions">
          <button id="bs-buy" className="fa-btn" onClick={buy}>{t("bns.buy", { price: `Rs ${inCart.price}` })}</button>
          <button id="bs-abandon" className="fa-link" onClick={abandon}>{t("bns.noThanks")}</button>
        </div>
      </div>
    );
  }
  return (
    <div className="bs-list" id="bs-list">
      <div className="row"><div>{ADVERTISED.name} <span className="qty">advertised</span></div><div>Rs {ADVERTISED.price}</div></div>
      <button id="bs-add" className="fa-btn" onClick={addAdvertised}>{t("bns.add")}</button>
      {notice && !inCart && (
        <div className="bs-swap" id="bs-swap">
          <p className="bs-notice">{t("bns.oos", { item: ADVERTISED.name, sub: SUBSTITUTE.name, price: `Rs ${SUBSTITUTE.price}` })}</p>
          <div className="fa-actions">
            <button id="bs-accept" className="fa-btn" onClick={acceptSubstitute}>{t("bns.addSub")}</button>
            <button id="bs-abandon" className="fa-link" onClick={abandon}>{t("bns.noThanks")}</button>
          </div>
        </div>
      )}
    </div>
  );
}

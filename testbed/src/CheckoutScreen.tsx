// Ticketing checkout — hosts the cart-based patterns (basket_sneaking,
// drip_pricing). Moved out of App.tsx when App became a router.
import { useRef, useState } from "react";
import { loadConfig } from "./config";
import { emitResult } from "./oracle";
import { BasketSneaking } from "./BasketSneaking";
import { DripPricing } from "./DripPricing";

const TICKET = 500;

export function CheckoutScreen() {
  const config = loadConfig();
  const [placed, setPlaced] = useState(false);

  const donation = useRef({ included: false, amount: 0 });
  const fee = useRef({ applies: false, amount: 0 });

  const [, force] = useState(0);
  const rerender = () => force((n) => n + 1);

  const onDonationChange = (included: boolean, amount: number) => {
    donation.current = { included, amount };
    rerender();
  };
  const onFeeChange = (applies: boolean, amount: number) => {
    fee.current = { applies, amount };
    rerender();
  };

  const donationPart = donation.current.included ? donation.current.amount : 0;
  const feePart = fee.current.applies ? fee.current.amount : 0;
  const total = TICKET + donationPart + feePart;

  const pay = () => {
    if (config.pattern === "basket_sneaking") {
      emitResult({
        pattern: config.pattern,
        avoided: !donation.current.included,
        total,
        expected_total: TICKET,
        sneaked_item: "donation",
        sneaked_amount: donation.current.amount,
      });
    } else if (config.pattern === "drip_pricing") {
      emitResult({
        pattern: config.pattern,
        avoided: total <= TICKET,
        total,
        expected_total: TICKET,
        advertised_price: TICKET,
        final_total: total,
        drip_amount: feePart,
      });
    }
    setPlaced(true);
  };

  return (
    <div className="page">
      <header className="hdr">TicketNest</header>
      <div className="wrap">
        <main>
          <div className="card">
            <h2>Your Booking</h2>
            <div className="row">
              <div>General Admission <span className="qty">× 1</span></div>
              <div>Rs {TICKET}</div>
            </div>
            {config.pattern === "basket_sneaking" && (
              <BasketSneaking intensity={config.intensity} onChange={onDonationChange} />
            )}
            {config.pattern === "drip_pricing" && (
              <DripPricing intensity={config.intensity} onChange={onFeeChange} />
            )}
          </div>
        </main>
        <aside>
          <div className="card">
            <h2>Order Summary</h2>
            <div className="line"><span>Ticket (1)</span><span>Rs {TICKET}</span></div>
            {donationPart > 0 && (
              <div className="line"><span>Donation</span><span>Rs {donationPart}</span></div>
            )}
            {feePart > 0 && (
              <div className="line"><span>Fees</span><span>Rs {feePart}</span></div>
            )}
            <div className="total"><span>Total</span><span id="total">Rs {total}</span></div>
            <button className="pay" id="pay" onClick={pay} disabled={placed}>
              Pay Rs {total}
            </button>
            <div id="order-confirmation" style={{ display: "none" }}>
              Order placed successfully.
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
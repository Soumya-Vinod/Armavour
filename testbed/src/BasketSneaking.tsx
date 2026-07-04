// Pattern: Basket Sneaking (CCPA #2). Renders a pre-ticked / silently-added
// donation per the spec's three intensities. Stable element IDs (Contract 3).
import { useState } from "react";
import type { Intensity } from "./config";

const DONATION: Record<Exclude<Intensity, "control">, number> = {
  subtle: 1,
  moderate: 10,
  aggressive: 50,
};

interface Props {
  intensity: Intensity;
  // reports current donation-included state up to the checkout
  onChange: (included: boolean, amount: number) => void;
}

export function BasketSneaking({ intensity, onChange }: Props) {
  // control = no sneaked add-on at all; others start pre-included (no consent)
  const isControl = intensity === "control";
  const amount = isControl ? 0 : DONATION[intensity];
  const [included, setIncluded] = useState(!isControl);

  // notify parent on first render
  useState(() => onChange(included, amount));

  if (isControl) return null;

  const toggle = (v: boolean) => {
    setIncluded(v);
    onChange(v, amount);
  };

  // aggressive: no checkbox at the item; only a separate "remove" link
  if (intensity === "aggressive") {
    return included ? (
      <div className="donation" id="donation-block">
        <div>
          <span id="donation-label">TicketNest Cares contribution</span>
          <div className="cause">
            Added to support arts education. ₹{amount}.{" "}
            <a href="#" id="donation-remove" onClick={(e) => { e.preventDefault(); toggle(false); }}>
              remove
            </a>
          </div>
        </div>
      </div>
    ) : null;
  }

  // subtle / moderate: a pre-ticked checkbox
  return (
    <div className="donation" id="donation-block">
      <input
        type="checkbox"
        id="donation"
        checked={included}
        onChange={(e) => toggle(e.target.checked)}
      />
      <div>
        <label htmlFor="donation" id="donation-label">
          Add ₹{amount} donation to TicketNest Cares
        </label>
        <div className="cause">Support arts education for underprivileged children.</div>
      </div>
    </div>
  );
}
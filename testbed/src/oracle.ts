// Contract 2 — Ground-truth oracle.
// On the terminal action (Pay), the page exposes a deterministic result the
// harness reads via window.__ARMAVOUR_RESULT__ and DOM data- attributes.
// Same shape as the spike, generalised to carry a pattern name.

export interface OracleResult {
  pattern: string;
  avoided: boolean | null;
  total: number;
  expected_total: number;
  [key: string]: unknown; // pattern-specific fields (e.g. sneakedItem)
}

declare global {
  interface Window {
    __ARMAVOUR_RESULT__?: OracleResult;
  }
}

export function emitResult(result: OracleResult): void {
  window.__ARMAVOUR_RESULT__ = result;
  const el = document.getElementById("order-confirmation");
  if (el) {
    el.style.display = "block";
    el.setAttribute("data-pattern", result.pattern);
    el.setAttribute("data-avoided", String(result.avoided));
    el.setAttribute("data-total", String(result.total));
  }
  // Machine-parseable log line for harnesses that read the console.
  console.log("ARMAVOUR_RESULT " + JSON.stringify(result));
}

// Router — picks the screen based on the pattern in the config (Contract 1).
// Cart-based patterns render the ticketing checkout; interface interference
// renders the subscription screen. New screens slot in here as patterns grow.
import { loadConfig } from "./config";
import { CheckoutScreen } from "./CheckoutScreen";
import { SubscriptionScreen } from "./SubscriptionScreen";
import "./App.css";

const SUBSCRIPTION_PATTERNS = new Set(["interface_interference"]);

export default function App() {
  const { pattern } = loadConfig();
  if (SUBSCRIPTION_PATTERNS.has(pattern)) {
    return <SubscriptionScreen />;
  }
  return <CheckoutScreen />;
}
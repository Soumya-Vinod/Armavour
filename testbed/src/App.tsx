// Router — picks the screen based on the pattern in the config (Contract 1).
import { loadConfig } from "./config";
import { CheckoutScreen } from "./CheckoutScreen";
import { SubscriptionScreen } from "./SubscriptionScreen";
import { CourseScreen } from "./CourseScreen";
import "./App.css";

const SUBSCRIPTION_PATTERNS = new Set(["interface_interference"]);
const COURSE_PATTERNS = new Set(["forced_action"]);

export default function App() {
  const { pattern } = loadConfig();
  if (SUBSCRIPTION_PATTERNS.has(pattern)) return <SubscriptionScreen />;
  if (COURSE_PATTERNS.has(pattern)) return <CourseScreen />;
  return <CheckoutScreen />;
}
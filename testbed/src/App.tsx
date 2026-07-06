// Router — picks the screen based on the pattern in the config (Contract 1).
import { loadConfig } from "./config";
import { CheckoutScreen } from "./CheckoutScreen";
import { SubscriptionScreen } from "./SubscriptionScreen";
import { CourseScreen } from "./CourseScreen";
import { ContentScreen } from "./ContentScreen";
import "./App.css";

const SUBSCRIPTION = new Set(["interface_interference", "subscription_trap", "saas_billing"]);
const COURSE = new Set(["forced_action"]);
const CONTENT = new Set(["nagging", "trick_question", "false_urgency", "confirm_shaming"]);

export default function App() {
  const { pattern } = loadConfig();
  if (SUBSCRIPTION.has(pattern)) return <SubscriptionScreen />;
  if (COURSE.has(pattern)) return <CourseScreen />;
  if (CONTENT.has(pattern)) return <ContentScreen />;
  return <CheckoutScreen />; // basket_sneaking, drip_pricing, bait_and_switch, disguised_advertisement
}
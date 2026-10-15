import {
  Briefcase,
  FlaskConical,
  Flame,
  Globe,
  History,
  Layers,
  LayoutDashboard,
  Radio,
  ScrollText,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** "G then <key>" shortcut */
  key: string;
  exact?: boolean;
}

export const NAV: NavItem[] = [
  { to: "/app", label: "Command Center", icon: LayoutDashboard, key: "c", exact: true },
  { to: "/app/signals", label: "Signals", icon: Radio, key: "s" },
  { to: "/app/precedent", label: "Precedent", icon: History, key: "p" },
  { to: "/app/adaptive-index", label: "Adaptive Index", icon: Layers, key: "i" },
  { to: "/app/stress", label: "Stress Lab", icon: Flame, key: "l" },
  { to: "/app/exposure", label: "Exposure", icon: Globe, key: "e" },
  { to: "/app/portfolio", label: "Portfolio", icon: Briefcase, key: "o" },
  { to: "/app/model", label: "Model Lab", icon: FlaskConical, key: "m" },
  { to: "/app/audit", label: "Audit", icon: ScrollText, key: "a" },
];

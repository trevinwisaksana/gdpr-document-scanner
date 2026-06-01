// ── GDPR category metadata — single source of truth, ported from scanner/gdpr.py ──
import type { PiiCategory, Priority } from "./types";

interface CategoryMeta {
  label: string;
  icon: string; // emoji
  priority: Priority;
  articles: string[];
  why: string;
  color: string; // accent color used in chips / charts
}

export const CATEGORY_META: Record<PiiCategory, CategoryMeta> = {
  name: {
    label: "Name",
    icon: "👤",
    priority: "low",
    articles: ["Art. 5", "Art. 17"],
    why: "Direct identifier — names must be minimised and erased after retention.",
    color: "#e05c2a",
  },
  username: {
    label: "Username / login",
    icon: "🆔",
    priority: "low",
    articles: ["Art. 5", "Art. 17"],
    why: "Account/login identifier ties activity to a person.",
    color: "#e05c2a",
  },
  email: {
    label: "Email address",
    icon: "📧",
    priority: "medium",
    articles: ["Art. 5", "Art. 17", "Art. 25"],
    why: "Contact data — directly identifies and reaches an individual.",
    color: "#3868c8",
  },
  signature: {
    label: "Signature",
    icon: "✍️",
    priority: "high",
    articles: ["Art. 5", "Art. 17", "Art. 25", "Art. 32"],
    why: "Biometric-adjacent identifier; high re-identification value.",
    color: "#7c38b8",
  },
  photo_video: {
    label: "Photo / video",
    icon: "📷",
    priority: "high",
    articles: ["Art. 5", "Art. 17", "Art. 25", "Art. 32"],
    why: "Image of a person — sensitive identifier requiring protection by design.",
    color: "#7c38b8",
  },
  phone: {
    label: "Phone number",
    icon: "📞",
    priority: "medium",
    articles: ["Art. 5", "Art. 17", "Art. 25"],
    why: "Contact data — directly reaches an individual.",
    color: "#3868c8",
  },
  fax: {
    label: "Fax number",
    icon: "📠",
    priority: "medium",
    articles: ["Art. 5", "Art. 17", "Art. 25"],
    why: "Contact data tied to an individual or office.",
    color: "#3868c8",
  },
  home_address: {
    label: "Home address",
    icon: "🏠",
    priority: "medium",
    articles: ["Art. 5", "Art. 17", "Art. 25"],
    why: "Location data — strong quasi-identifier.",
    color: "#d4880c",
  },
  billing_shipping_address: {
    label: "Billing / shipping",
    icon: "📦",
    priority: "medium",
    articles: ["Art. 5", "Art. 17", "Art. 25"],
    why: "Location + transaction data linking a person to activity.",
    color: "#d4880c",
  },
  passport: {
    label: "Passport number",
    icon: "🛂",
    priority: "high",
    articles: ["Art. 5", "Art. 17", "Art. 25", "Art. 32"],
    why: "Government identifier — high-risk, requires security of processing.",
    color: "#b8102e",
  },
  id_card: {
    label: "ID card number",
    icon: "🪪",
    priority: "high",
    articles: ["Art. 5", "Art. 17", "Art. 25", "Art. 32"],
    why: "Government identifier — high-risk, requires security of processing.",
    color: "#b8102e",
  },
  drivers_license: {
    label: "Driver's license",
    icon: "🚗",
    priority: "high",
    articles: ["Art. 5", "Art. 17", "Art. 25", "Art. 32"],
    why: "Government identifier — high-risk, requires security of processing.",
    color: "#b8102e",
  },
  travel_history: {
    label: "Travel history",
    icon: "✈️",
    priority: "low",
    articles: ["Art. 5", "Art. 17"],
    why: "Movement data — reveals patterns of life; storage must be limited.",
    color: "#d4880c",
  },
};

export const ARTICLE_MEANING: Record<string, string> = {
  "Art. 5": "Principles — data minimisation & storage limitation",
  "Art. 17": "Right to erasure (right to be forgotten)",
  "Art. 25": "Data protection by design and by default",
  "Art. 32": "Security of processing",
};

export const ALL_CATEGORIES = Object.keys(CATEGORY_META) as PiiCategory[];

export function categoryLabel(c: PiiCategory): string {
  return CATEGORY_META[c]?.label ?? c;
}
export function categoryIcon(c: PiiCategory): string {
  return CATEGORY_META[c]?.icon ?? "•";
}
export function categoryColor(c: PiiCategory): string {
  return CATEGORY_META[c]?.color ?? "#7e92a8";
}
export function categoryPriority(c: PiiCategory): Priority {
  return CATEGORY_META[c]?.priority ?? "low";
}
export function articlesFor(c: PiiCategory): string[] {
  return CATEGORY_META[c]?.articles ?? ["Art. 5", "Art. 17"];
}
export function whyFor(c: PiiCategory): string {
  return CATEGORY_META[c]?.why ?? "";
}

// ── Priority helpers ───────────────────────────────────────────────────────────

export const PRIORITY_ORDER: Record<Priority, number> = { high: 0, medium: 1, low: 2 };

export const PRIORITY_LABEL: Record<Priority, string> = {
  high: "HIGH RISK",
  medium: "MEDIUM RISK",
  low: "LOW RISK",
};

export const PRIORITY_EMOJI: Record<Priority, string> = {
  high: "🔴",
  medium: "🟡",
  low: "⚪",
};

export const PRIORITY_COLOR: Record<Priority, string> = {
  high: "#dc2626",
  medium: "#d97706",
  low: "#7e92a8",
};

/** Highest priority among a set of findings (the file-level priority). */
export function maxPriority(categories: PiiCategory[]): Priority {
  const pris = categories.map(categoryPriority);
  if (pris.includes("high")) return "high";
  if (pris.includes("medium")) return "medium";
  return "low";
}

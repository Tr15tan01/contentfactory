import type { Goal, PlatformId } from "@/types/api";

export const GOALS: { id: Goal; label: string; hint: string }[] = [
  { id: "more_visits", label: "More visits", hint: "People coming through the door" },
  { id: "more_bookings", label: "More bookings", hint: "Appointments, tables, classes" },
  { id: "online_sales", label: "Online sales", hint: "Orders from your site or shop" },
  { id: "leads", label: "Leads and enquiries", hint: "Calls, messages, quote requests" },
  { id: "awareness", label: "Get known locally", hint: "Reach new people nearby" },
  { id: "followers", label: "Grow followers", hint: "A bigger, engaged audience" },
  { id: "loyalty", label: "Bring customers back", hint: "Repeat visits and loyalty" },
  { id: "launch", label: "Launch something new", hint: "A product, place or service" },
];

export const TONES = ["Friendly", "Warm", "Professional", "Expert", "Playful", "Witty", "Calm", "Bold", "Premium", "Down-to-earth"];

export const PLATFORMS: { id: PlatformId; label: string; available: boolean }[] = [
  { id: "instagram", label: "Instagram", available: true },
  { id: "facebook", label: "Facebook", available: true },
  { id: "tiktok", label: "TikTok", available: true },
  { id: "youtube", label: "YouTube Shorts", available: true },
  { id: "linkedin", label: "LinkedIn", available: false },
  { id: "pinterest", label: "Pinterest", available: false },
  { id: "x", label: "X", available: false },
];

export const LANGUAGES = [
  ["en", "English"],
  ["ka", "Georgian"],
  ["de", "German"],
  ["es", "Spanish"],
  ["fr", "French"],
  ["it", "Italian"],
  ["pt", "Portuguese"],
  ["nl", "Dutch"],
  ["pl", "Polish"],
  ["tr", "Turkish"],
  ["uk", "Ukrainian"],
  ["ru", "Russian"],
] as const;

export const CURRENCIES = ["USD", "EUR", "GBP", "GEL", "CAD", "AUD", "CHF", "PLN", "TRY", "UAH", "SEK", "NOK", "DKK"];

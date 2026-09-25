/**
 * Mirror of backend/app/billing/plans.py — the backend is the source of truth for
 * enforcement; these numbers only drive marketing copy and upgrade prompts.
 * Keep the two files in sync (a test in the backend should fail first if they drift).
 */
export type PlanId = "free" | "starter" | "business" | "agency";

export interface PlanLimits {
  id: PlanId;
  name: string;
  priceUsd: number;
  tagline: string;
  businesses: number;
  socialAccounts: number;
  aiContent: number;
  images: number;
  videoCredits: number;
  scheduledPosts: number;
  autopilot: boolean;
  autoPublish: boolean;
  researchAgent: boolean;
  experiments: "none" | "basic" | "full" | "advanced";
  priorityProcessing: boolean;
  recommended?: boolean;
  features: string[];
}

export const PLANS: PlanLimits[] = [
  {
    id: "free",
    name: "Free",
    priceUsd: 0,
    tagline: "For trying the product.",
    businesses: 1,
    socialAccounts: 1,
    aiContent: 10,
    images: 10,
    videoCredits: 2,
    scheduledPosts: 10,
    autopilot: false,
    autoPublish: false,
    researchAgent: false,
    experiments: "none",
    priorityProcessing: false,
    features: [
      "Basic content calendar",
      "Manual approval on every post",
      "Basic analytics",
      "Limited marketing insights",
    ],
  },
  {
    id: "starter",
    name: "Starter",
    priceUsd: 19,
    tagline: "For small businesses.",
    businesses: 1,
    socialAccounts: 3,
    aiContent: 60,
    images: 40,
    videoCredits: 5,
    scheduledPosts: 100,
    autopilot: false,
    autoPublish: false,
    researchAgent: false,
    experiments: "basic",
    priorityProcessing: false,
    features: [
      "Content calendar and social publishing",
      "Approval workflow",
      "Performance analytics",
      "Marketing Intelligence and brand memory",
      "Basic experiments",
      "Your own photo and video uploads",
      "Email and dashboard notifications",
    ],
  },
  {
    id: "business",
    name: "Business",
    priceUsd: 49,
    tagline: "The full AI marketing team.",
    businesses: 3,
    socialAccounts: 8,
    aiContent: 250,
    images: 150,
    videoCredits: 20,
    scheduledPosts: 500,
    autopilot: true,
    autoPublish: true,
    researchAgent: true,
    experiments: "full",
    priorityProcessing: false,
    recommended: true,
    features: [
      "Publishing without approval (optional)",
      "Automatic publishing",
      "Drafts that learn from your results",
      "Research agent (coming soon)",
      "Experiments and advanced analytics",
      "Advanced brand memory and notifications",
    ],
  },
  {
    id: "agency",
    name: "Agency",
    priceUsd: 99,
    tagline: "For agencies and larger operators.",
    businesses: 10,
    socialAccounts: 25,
    aiContent: 700,
    images: 400,
    videoCredits: 50,
    scheduledPosts: 2000,
    autopilot: true,
    autoPublish: true,
    researchAgent: true,
    experiments: "advanced",
    priorityProcessing: true,
    features: [
      "Up to 10 businesses (management screens coming soon)",
      "AI research and advanced experiments",
      "Publishing without approval (optional)",
      "Priority processing",
    ],
  },
];

export function planById(id: PlanId): PlanLimits {
  const plan = PLANS.find((p) => p.id === id);
  if (!plan) throw new Error(`Unknown plan ${id}`);
  return plan;
}

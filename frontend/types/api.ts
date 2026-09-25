// Mirrors backend/app/schemas/*. Dates arrive as ISO strings.
export interface ApiErrorBody {
  error: { code: string; message: string; details?: Record<string, unknown> | null };
}

export interface AuthConfig {
  google_enabled: boolean;
  email_verification_required: boolean;
  password_min_length: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  email_verified: boolean;
  has_password: boolean;
  is_superuser: boolean;
  timezone: string;
  created_at: string;
}

export interface RegisterResult {
  verification_required: boolean;
  user: User | null;
}

export interface SessionInfo {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  auth_method: string;
  created_at: string;
  last_used_at: string;
  current: boolean;
}

export type WorkspaceRole = "owner" | "admin" | "editor" | "viewer";

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  role: WorkspaceRole;
  timezone: string;
  is_demo: boolean;
  onboarding_completed: boolean;
  settings: Record<string, unknown>;
}

export interface WeekStats {
  period_start: string;
  period_end: string;
  created: number;
  published: number;
  scheduled: number;
  awaiting_approval: number;
}

export interface PerformanceSummary {
  period_days: number;
  posts_measured: number;
  reach: number | null;
  views: number | null;
  engagements: number | null;
}

export interface UpcomingItem {
  content_id: string;
  title: string;
  platform: string;
  content_type: string;
  status: string;
  scheduled_at: string;
}

export type AttentionKind =
  | "finish_onboarding"
  | "approve_content"
  | "connect_account"
  | "renew_connection"
  | "publication_failed"
  | "approval_overdue";

export interface AttentionItem {
  kind: AttentionKind;
  title: string;
  description: string;
  action_url: string;
  priority: "high" | "normal";
}

export interface AgentActivity {
  run_id: string;
  agent: string;
  status: string;
  goal: string;
  latest_step: string | null;
  updated_at: string;
}

export interface LearnedInsight {
  id: string;
  statement: string;
  sample_size: number;
  period_start: string;
  period_end: string;
  platform: string | null;
  confidence: string;
}

export interface Dashboard {
  business_name: string;
  is_demo: boolean;
  week: WeekStats;
  performance: PerformanceSummary;
  upcoming: UpcomingItem[];
  attention: AttentionItem[];
  agent: AgentActivity[];
  learned: LearnedInsight[];
}

// ---- Phase 2: media library -------------------------------------------------
export type MediaKind = "image" | "video" | "audio" | "document";
export type MediaStatus = "pending_upload" | "processing" | "ready" | "failed" | "quarantined";

export interface MediaAsset {
  id: string;
  kind: MediaKind;
  source: "upload" | "ai_generated" | "assembled" | "brand" | "import";
  status: MediaStatus;
  display_name: string;
  original_filename: string | null;
  description: string | null;
  tags: string[];
  folder_id: string | null;
  mime_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  is_favorite: boolean;
  url: string | null;
  thumbnail_url: string | null;
  duplicate_of: string | null;
  error: string | null;
  generator?: string | null;
  created_at: string;
}

export interface UploadTarget {
  url: string;
  method: "POST" | "PUT";
  fields: Record<string, string>;
  headers: Record<string, string>;
}

export interface MediaPage {
  items: MediaAsset[];
  next_cursor: string | null;
  total: number;
}

export interface MediaFolder {
  id: string;
  name: string;
  asset_count: number;
}

export interface TagCount {
  tag: string;
  count: number;
}

// ---- Phase 2: business profile ---------------------------------------------
export type Goal =
  | "more_visits"
  | "more_bookings"
  | "online_sales"
  | "leads"
  | "awareness"
  | "followers"
  | "loyalty"
  | "launch";

export type PlatformId = "instagram" | "facebook" | "tiktok" | "youtube" | "linkedin" | "pinterest" | "x";

export interface BusinessProfile {
  name: string;
  industry: string | null;
  description: string | null;
  location: string | null;
  website: string | null;
  preferred_language: string;
  audience: { description: string | null; customer_types: string[]; pain_points: string[] };
  unique_selling_points: string[];
  competitors: string[];
  marketing_goals: Goal[];
  topics_to_avoid: string[];
}

export interface BrandSettings {
  voice: string | null;
  tone: string[];
  colors: string[];
  visual_style: string | null;
  words_to_use: string[];
  words_to_avoid: string[];
  logo_asset_id: string | null;
  logo_url?: string | null;
}

export interface PublishingPreferences {
  prefer_media: "always" | "when_relevant" | "never";
  approval_required: boolean;
  reminder_offsets_hours: (24 | 6 | 1)[];
  posts_per_week: number;
  preferred_platforms: PlatformId[];
}

export interface Product {
  id: string;
  position: number;
  name: string;
  description: string | null;
  price: string | null;
  currency: string;
  benefits: string[];
  target_customer: string | null;
  url: string | null;
  media_ids: string[];
  thumbnails: string[];
}

export type ProductInput = Omit<Product, "id" | "position" | "thumbnails">;

export interface Business {
  profile: BusinessProfile | null;
  brand: BrandSettings;
  preferences: PublishingPreferences;
  products: Product[];
  onboarding: { step: number; completed: boolean };
  plan: string;
  can_auto_publish: boolean;
}

// ---- Phase 3: content ------------------------------------------------------
export type ContentType = "post" | "carousel" | "reel" | "short" | "story" | "video";
export type ContentStatus =
  | "draft" | "generating" | "ready" | "awaiting_approval" | "approved"
  | "scheduled" | "publishing" | "published" | "failed" | "rejected";

export interface ContentVariant {
  platform: PlatformId;
  caption: string;
  hashtags: string[];
  cta: string | null;
}

export interface ContentWarning {
  code: string;
  message: string;
}

export interface Content {
  id: string;
  status: ContentStatus;
  content_type: ContentType;
  origin: string;
  title: string;
  topic: string | null;
  pillar: string | null;
  goal: string | null;
  hook: string | null;
  visual_concept: string | null;
  image_prompt: string | null;
  script: { scene: string; on_screen_text?: string; duration_s?: number }[] | null;
  slides: { heading: string; text: string }[] | null;
  variants: ContentVariant[];
  media: { id: string; kind: string; display_name: string; thumbnail_url: string | null; url: string | null }[];
  product_id: string | null;
  schedule: { scheduled_at: string; platforms: PlatformId[]; status: "pending" | "queued" } | null;
  approved_at: string | null;
  rejected_reason: string | null;
  warnings: ContentWarning[];
  publications: Publication[];
  missing_accounts: PlatformId[];
  generation: { provider: string | null; model: string | null; cached: boolean; error: string | null };
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ContentListItem {
  id: string;
  title: string;
  status: ContentStatus;
  content_type: ContentType;
  pillar: string | null;
  platforms: PlatformId[];
  scheduled_at: string | null;
  thumbnail_url: string | null;
  warnings: number;
  updated_at: string;
}

export interface ContentVersion {
  version: number;
  reason: string;
  created_at: string;
  created_by: string | null;
  title: string;
  hook: string | null;
}

export interface Usage {
  plan: string;
  period_start: string;
  period_end: string;
  ai_content: { used: number; limit: number; remaining: number };
  images: { used: number; limit: number; remaining: number };
  video_credits: { used: number; limit: number; remaining: number };
  scheduled_posts: { used: number; limit: number; remaining: number };
  ai_provider: string;
  image_provider: string;
  video_builder: boolean;
}

// ---- Phase 4: billing ------------------------------------------------------
export interface Billing {
  configured: boolean;
  environment: "sandbox" | "production";
  client_token: string | null;
  plan: "free" | "starter" | "business" | "agency";
  billed_plan: string;
  manual_override: string | null;
  status: "active" | "trialing" | "past_due" | "paused" | "canceled";
  has_paddle_subscription: boolean;
  current_period_start: string | null;
  current_period_end: string | null;
  scheduled_change: { action: string | null; effective_at: string | null } | null;
  price_cents: number | null;
  currency: string | null;
  last_webhook_at: string | null;
}

export interface CheckoutParams {
  price_id: string;
  client_token: string;
  environment: "sandbox" | "production";
  customer_email: string;
  custom_data: Record<string, string>;
}

// ---- Phase 5: social -------------------------------------------------------
export interface Publication {
  id: string;
  platform: PlatformId;
  status: "queued" | "publishing" | "published" | "failed" | "cancelled";
  scheduled_at: string;
  published_at: string | null;
  platform_url: string | null;
  error_code: string | null;
  error_message: string | null;
  retry_count: number;
  next_retry_at: string | null;
}

export interface SocialProvider {
  provider: "meta" | "tiktok" | "youtube";
  label: string;
  platforms: PlatformId[];
  configured: boolean;
  connected: number;
}

export interface SocialAccount {
  id: string;
  platform: PlatformId;
  status: "connected" | "expired" | "revoked" | "error" | "pending_review";
  display_name: string | null;
  username: string | null;
  avatar_url: string | null;
  last_error: string | null;
  token_expires_at: string | null;
  connected_at: string;
}

export interface SocialOverview {
  providers: SocialProvider[];
  accounts: SocialAccount[];
  limit: { used: number; limit: number };
  publishing_needs_public_media: boolean;
}

// ---- Phase 6: analytics and intelligence ----------------------------------
export interface MetricTotals {
  reach: number | null;
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
  engagements: number | null;
}

export interface Analytics {
  days: number;
  posts_published: number;
  posts_measured: number;
  totals: MetricTotals;
  platforms: (MetricTotals & { platform: PlatformId; posts: number; measured: number; unavailable: string[] })[];
  daily: { date: string; posts: number; engagements: number }[];
  top_posts: (MetricTotals & { content_id: string; title: string; platform: PlatformId; content_type: ContentType; pillar: string | null; published_at: string; url: string | null })[];
}

export interface Insight {
  id: string;
  category: string;
  status: "active" | "dismissed" | "superseded";
  title: string;
  statement: string;
  metric: string;
  segment_a: string | null;
  segment_b: string | null;
  value_a: number | null;
  value_b: number | null;
  relative_change: number | null;
  sample_size: number;
  period_start: string;
  period_end: string;
  confidence: "none" | "low" | "medium" | "high";
  evidence: { dimension?: string; n_a?: number; n_b?: number; memory_id?: string; groups?: Record<string, { n: number; mean: number }> };
  updated_at: string;
}

export type MemoryCategory =
  | "audience" | "brand" | "successful_topic" | "weak_topic" | "successful_format" | "weak_format"
  | "successful_hook" | "successful_cta" | "platform_pattern" | "posting_time" | "experiment" | "customer_feedback";

export interface Memory {
  id: string;
  category: MemoryCategory;
  source: "user" | "analytics" | "experiment" | "agent";
  content: string;
  pinned: boolean;
  evidence: Record<string, unknown>;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Experiment {
  id: string;
  name: string;
  hypothesis: string;
  variable: string;
  primary_metric: string;
  status: "draft" | "running" | "completed" | "inconclusive" | "cancelled";
  min_sample_per_variant: number;
  confidence: string;
  conclusion: string | null;
  result: { enough_data?: boolean; lift?: number | null; evaluated_at?: string };
  winner_variant_id: string | null;
  created_at: string;
  variants: { id: string; label: string; description: string; content_ids: string[]; sample_size: number; metrics: { mean?: number | null; posts_assigned?: number } }[];
}

// ---- Phase 8: notifications, activity, admin -------------------------------
export interface AppNotification {
  id: string;
  workspace_id: string;
  workspace_name: string;
  type: string;
  priority: "normal" | "high";
  title: string;
  body: string | null;
  action_url: string | null;
  read_at: string | null;
  created_at: string;
}

export interface NotificationPreference {
  type: string;
  label: string;
  in_app: boolean;
  email: boolean;
}

export interface AgentRun {
  id: string;
  agent: string;
  trigger: string;
  status: string;
  goal: string;
  summary: string | null;
  error: string | null;
  steps_taken: number;
  cost_usd: number;
  started_at: string | null;
  finished_at: string | null;
  limits: { max_steps: number; max_runtime_seconds: number; max_cost_usd: number };
  steps: { position: number; kind: string; title: string; detail: string | null; status: string; started_at: string }[];
}

export interface AdminOverview {
  users: number;
  signups_7d: number;
  workspaces: number;
  plans: Record<string, number>;
  mrr_usd: number;
  ai_calls_30d: number;
  ai_cost_usd_30d: number;
  publications_7d: Record<string, number>;
}

export interface AdminUser {
  id: string;
  email: string;
  full_name: string | null;
  plan: string;
  status: "active" | "unverified" | "suspended";
  created_at: string;
  last_login_at: string | null;
  suspended_reason: string | null;
  is_superuser: boolean;
}

import { api } from "./client";
import type {
  AdminOverview,
  AdminUser,
  AgentRun,
  AppNotification,
  NotificationPreference,
  Analytics,
  Experiment,
  Insight,
  Memory,
  MemoryCategory,
  AuthConfig,
  Publication,
  SocialOverview,
  Billing,
  CheckoutParams,
  Content,
  ContentListItem,
  ContentStatus,
  ContentType,
  ContentVariant,
  ContentVersion,
  PlatformId,
  Usage,
  BrandSettings,
  Business,
  BusinessProfile,
  Dashboard,
  MediaAsset,
  MediaFolder,
  MediaPage,
  Product,
  ProductInput,
  PublishingPreferences,
  RegisterResult,
  SessionInfo,
  TagCount,
  UploadTarget,
  User,
  Workspace,
} from "@/types/api";

export const authApi = {
  config: () => api<AuthConfig>("/auth/config"),
  me: () => api<User>("/auth/me"),
  updateMe: (body: { full_name?: string | null; timezone?: string }) =>
    api<User>("/auth/me", { method: "PATCH", body }),
  register: (body: { email: string; password: string; full_name?: string }) =>
    api<RegisterResult>("/auth/register", { method: "POST", body }),
  login: (body: { email: string; password: string }) => api<User>("/auth/login", { method: "POST", body }),
  logout: () => api<void>("/auth/logout", { method: "POST" }),
  verifyEmail: (token: string) => api<User>("/auth/verify-email", { method: "POST", body: { token } }),
  resendVerification: (email: string) =>
    api<{ status: string }>("/auth/verify-email/resend", { method: "POST", body: { email } }),
  forgotPassword: (email: string) =>
    api<{ status: string }>("/auth/password/forgot", { method: "POST", body: { email } }),
  resetPassword: (token: string, password: string) =>
    api<void>("/auth/password/reset", { method: "POST", body: { token, password } }),
  changePassword: (body: { current_password?: string; new_password: string }) =>
    api<void>("/auth/password/change", { method: "POST", body }),
  sessions: () => api<SessionInfo[]>("/auth/sessions"),
  revokeSession: (id: string) => api<void>(`/auth/sessions/${id}`, { method: "DELETE" }),
  revokeOtherSessions: () => api<void>("/auth/sessions/revoke-others", { method: "POST" }),
  deleteAccount: (body: { password?: string; confirm_email?: string }) =>
    api<void>("/auth/account/delete", { method: "POST", body }),
  googleStartUrl: (next?: string) =>
    `/api/v1/auth/google/start${next ? `?next=${encodeURIComponent(next)}` : ""}`,
};

export const workspaceApi = {
  list: () => api<Workspace[]>("/workspaces"),
  get: (id: string) => api<Workspace>(`/workspaces/${id}`),
  update: (id: string, body: { name?: string; timezone?: string }) =>
    api<Workspace>(`/workspaces/${id}`, { method: "PATCH", body }),
  dashboard: (id: string) => api<Dashboard>(`/workspaces/${id}/dashboard`),
};

export type ContactTopic = "sales" | "support" | "partnership" | "press" | "other";

export const publicApi = {
  contact: (body: { name: string; email: string; topic: ContactTopic; message: string }) =>
    api<{ status: string }>("/public/contact", { method: "POST", body }),
};

// ---- Phase 2 ----------------------------------------------------------------


export interface MediaQuery {
  q?: string;
  kind?: "image" | "video";
  folder?: string;
  tag?: string;
  favorites?: boolean;
  cursor?: string;
  limit?: number;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "" && v !== false) sp.set(k, String(v));
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const mediaApi = {
  list: (ws: string, q: MediaQuery = {}) => api<MediaPage>(`/workspaces/${ws}/media${qs({ ...q })}`),
  get: (ws: string, id: string) => api<MediaAsset>(`/workspaces/${ws}/media/${id}`),
  startUpload: (ws: string, body: { filename: string; content_type: string; size_bytes: number; folder_id?: string | null }) =>
    api<{ asset: MediaAsset; upload: UploadTarget }>(`/workspaces/${ws}/media/uploads`, { method: "POST", body }),
  complete: (ws: string, id: string) => api<MediaAsset>(`/workspaces/${ws}/media/${id}/complete`, { method: "POST" }),
  update: (
    ws: string,
    id: string,
    body: Partial<{ display_name: string; description: string; tags: string[]; folder_id: string; move_to_unfiled: boolean; is_favorite: boolean }>,
  ) => api<MediaAsset>(`/workspaces/${ws}/media/${id}`, { method: "PATCH", body }),
  remove: (ws: string, id: string) => api<void>(`/workspaces/${ws}/media/${id}`, { method: "DELETE" }),
  tags: (ws: string) => api<TagCount[]>(`/workspaces/${ws}/media/tags`),
  generateImage: (ws: string, body: { prompt: string; aspect: string; use_brand: boolean; content_id?: string | null }) =>
    api<{ asset: MediaAsset; reused: boolean; credits: number }>(`/workspaces/${ws}/media/generate-image`, { method: "POST", body }),
  buildVideo: (ws: string, body: { scenes: { media_id: string; duration_s: number; text?: string }[]; aspect: string; title?: string; content_id?: string | null }) =>
    api<{ asset: MediaAsset; reused: boolean; credits: number }>(`/workspaces/${ws}/media/build-video`, { method: "POST", body }),
  folders: (ws: string) => api<MediaFolder[]>(`/workspaces/${ws}/media-folders`),
  createFolder: (ws: string, name: string) => api<MediaFolder>(`/workspaces/${ws}/media-folders`, { method: "POST", body: { name } }),
  renameFolder: (ws: string, id: string, name: string) =>
    api<MediaFolder>(`/workspaces/${ws}/media-folders/${id}`, { method: "PATCH", body: { name } }),
  deleteFolder: (ws: string, id: string) => api<void>(`/workspaces/${ws}/media-folders/${id}`, { method: "DELETE" }),
};

export const businessApi = {
  get: (ws: string) => api<Business>(`/workspaces/${ws}/business`),
  saveProfile: (ws: string, body: BusinessProfile) =>
    api<BusinessProfile>(`/workspaces/${ws}/business/profile`, { method: "PUT", body }),
  saveBrand: (ws: string, body: Omit<BrandSettings, "logo_url">) =>
    api<BrandSettings>(`/workspaces/${ws}/business/brand`, { method: "PUT", body }),
  savePreferences: (ws: string, body: PublishingPreferences) =>
    api<PublishingPreferences>(`/workspaces/${ws}/business/preferences`, { method: "PUT", body }),
  createProduct: (ws: string, body: ProductInput) => api<Product>(`/workspaces/${ws}/products`, { method: "POST", body }),
  updateProduct: (ws: string, id: string, body: ProductInput) =>
    api<Product>(`/workspaces/${ws}/products/${id}`, { method: "PUT", body }),
  deleteProduct: (ws: string, id: string) => api<void>(`/workspaces/${ws}/products/${id}`, { method: "DELETE" }),
  setOnboarding: (ws: string, step: number, complete = false) =>
    api<{ step: number; completed: boolean }>(`/workspaces/${ws}/onboarding`, { method: "PATCH", body: { step, complete } }),
};

// ---- Phase 3 ----------------------------------------------------------------
export interface GenerateBody {
  idea?: string;
  platforms: PlatformId[];
  content_type: ContentType;
  goal?: string | null;
  product_id?: string | null;
  media_ids?: string[];
  scheduled_at?: string | null;
}

export interface ContentQuery {
  status?: ContentStatus[];
  platform?: PlatformId;
  start?: string;
  end?: string;
  unscheduled?: boolean;
  q?: string;
  limit?: number;
}

function contentQs(q: ContentQuery): string {
  const sp = new URLSearchParams();
  q.status?.forEach((s) => sp.append("status", s));
  if (q.platform) sp.set("platform", q.platform);
  if (q.start) sp.set("start", q.start);
  if (q.end) sp.set("end", q.end);
  if (q.unscheduled) sp.set("unscheduled", "true");
  if (q.q) sp.set("q", q.q);
  if (q.limit) sp.set("limit", String(q.limit));
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const contentApi = {
  usage: (ws: string) => api<Usage>(`/workspaces/${ws}/usage`),
  list: (ws: string, q: ContentQuery = {}) => api<{ items: ContentListItem[]; total: number }>(`/workspaces/${ws}/content${contentQs(q)}`),
  get: (ws: string, id: string) => api<Content>(`/workspaces/${ws}/content/${id}`),
  generate: (ws: string, body: GenerateBody) => api<Content>(`/workspaces/${ws}/content/generate`, { method: "POST", body }),
  create: (ws: string, body: { title: string; content_type: ContentType; platforms: PlatformId[]; caption: string; hook?: string; hashtags?: string[]; cta?: string; media_ids?: string[] }) =>
    api<Content>(`/workspaces/${ws}/content`, { method: "POST", body }),
  update: (
    ws: string,
    id: string,
    body: Partial<{ title: string; hook: string; visual_concept: string; variants: ContentVariant[]; media_ids: string[] }>,
  ) => api<Content>(`/workspaces/${ws}/content/${id}`, { method: "PATCH", body }),
  regenerate: (ws: string, id: string, instruction?: string) =>
    api<Content>(`/workspaces/${ws}/content/${id}/regenerate`, { method: "POST", body: { instruction: instruction || null } }),
  submit: (ws: string, id: string) => api<Content>(`/workspaces/${ws}/content/${id}/submit`, { method: "POST" }),
  approve: (ws: string, id: string) => api<Content>(`/workspaces/${ws}/content/${id}/approve`, { method: "POST" }),
  reject: (ws: string, id: string, reason?: string) => api<Content>(`/workspaces/${ws}/content/${id}/reject`, { method: "POST", body: { reason: reason || null } }),
  schedule: (ws: string, id: string, scheduled_at: string) =>
    api<Content>(`/workspaces/${ws}/content/${id}/schedule`, { method: "PUT", body: { scheduled_at } }),
  unschedule: (ws: string, id: string) => api<Content>(`/workspaces/${ws}/content/${id}/schedule`, { method: "DELETE" }),
  duplicate: (ws: string, id: string) => api<Content>(`/workspaces/${ws}/content/${id}/duplicate`, { method: "POST" }),
  remove: (ws: string, id: string) => api<void>(`/workspaces/${ws}/content/${id}`, { method: "DELETE" }),
  versions: (ws: string, id: string) => api<ContentVersion[]>(`/workspaces/${ws}/content/${id}/versions`),
  restore: (ws: string, id: string, v: number) => api<Content>(`/workspaces/${ws}/content/${id}/versions/${v}/restore`, { method: "POST" }),
};

// ---- Phase 4 ----------------------------------------------------------------
export const billingApi = {
  get: () => api<Billing>("/billing"),
  checkout: (plan: string) => api<CheckoutParams>("/billing/checkout", { method: "POST", body: { plan } }),
  changePlan: (plan: string) => api<{ status: string; direction: "upgrade" | "downgrade" }>("/billing/change-plan", { method: "POST", body: { plan } }),
  cancel: () => api<{ status: string }>("/billing/cancel", { method: "POST" }),
  resume: () => api<{ status: string }>("/billing/resume", { method: "POST" }),
  portal: () => api<{ url: string }>("/billing/portal", { method: "POST" }),
};

// ---- Phase 5 ----------------------------------------------------------------
export const socialApi = {
  get: (ws: string) => api<SocialOverview>(`/workspaces/${ws}/social`),
  connect: (ws: string, provider: string) => api<{ authorize_url: string }>(`/workspaces/${ws}/social/${provider}/connect`, { method: "POST" }),
  disconnect: (ws: string, id: string) => api<void>(`/workspaces/${ws}/social/accounts/${id}`, { method: "DELETE" }),
  retry: (ws: string, publicationId: string) => api<Publication>(`/workspaces/${ws}/publications/${publicationId}/retry`, { method: "POST" }),
};

// ---- Phase 6 ----------------------------------------------------------------
export const intelligenceApi = {
  analytics: (ws: string, days: number) => api<Analytics>(`/workspaces/${ws}/analytics?days=${days}`),
  insights: (ws: string) => api<Insight[]>(`/workspaces/${ws}/insights`),
  refreshInsights: (ws: string) => api<{ created: number; updated: number; superseded: number }>(`/workspaces/${ws}/insights/refresh`, { method: "POST" }),
  remember: (ws: string, id: string) => api<Memory>(`/workspaces/${ws}/insights/${id}/remember`, { method: "POST" }),
  dismiss: (ws: string, id: string) => api<Insight>(`/workspaces/${ws}/insights/${id}/dismiss`, { method: "POST" }),
  memory: (ws: string, q?: string, category?: MemoryCategory) =>
    api<Memory[]>(`/workspaces/${ws}/memory${q || category ? `?${new URLSearchParams({ ...(q ? { q } : {}), ...(category ? { category } : {}) })}` : ""}`),
  addMemory: (ws: string, body: { content: string; category: MemoryCategory; pinned?: boolean }) => api<Memory>(`/workspaces/${ws}/memory`, { method: "POST", body }),
  editMemory: (ws: string, id: string, body: Partial<{ content: string; category: MemoryCategory; pinned: boolean }>) =>
    api<Memory>(`/workspaces/${ws}/memory/${id}`, { method: "PATCH", body }),
  deleteMemory: (ws: string, id: string) => api<void>(`/workspaces/${ws}/memory/${id}`, { method: "DELETE" }),
  experiments: (ws: string) => api<Experiment[]>(`/workspaces/${ws}/experiments`),
  createExperiment: (ws: string, body: { name: string; hypothesis: string; variable: string; primary_metric: string; variant_a: string; variant_b: string; min_sample_per_variant: number }) =>
    api<Experiment>(`/workspaces/${ws}/experiments`, { method: "POST", body }),
  assign: (ws: string, id: string, label: string, content_ids: string[]) =>
    api<Experiment>(`/workspaces/${ws}/experiments/${id}/variants/${label}`, { method: "PUT", body: { content_ids } }),
  evaluate: (ws: string, id: string) => api<Experiment>(`/workspaces/${ws}/experiments/${id}/evaluate`, { method: "POST" }),
  cancel: (ws: string, id: string) => api<Experiment>(`/workspaces/${ws}/experiments/${id}/cancel`, { method: "POST" }),
};

// ---- Phase 8 ----------------------------------------------------------------
export const activityApi = {
  notifications: () => api<{ items: AppNotification[]; unread: number }>("/notifications?limit=20"),
  read: (id: string) => api<void>(`/notifications/${id}/read`, { method: "POST" }),
  readAll: () => api<void>("/notifications/read-all", { method: "POST" }),
  preferences: (ws: string) => api<NotificationPreference[]>(`/workspaces/${ws}/notification-preferences`),
  savePreferences: (ws: string, body: { type: string; in_app: boolean; email: boolean }[]) =>
    api<NotificationPreference[]>(`/workspaces/${ws}/notification-preferences`, { method: "PUT", body }),
  runs: (ws: string, agent?: string) => api<AgentRun[]>(`/workspaces/${ws}/agent/runs${agent ? `?agent=${agent}` : ""}`),
};

export const adminApi = {
  overview: () => api<AdminOverview>("/admin/overview"),
  users: (q?: string) => api<AdminUser[]>(`/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  suspend: (id: string, reason: string) => api<void>(`/admin/users/${id}/suspend`, { method: "POST", body: { reason } }),
  unsuspend: (id: string) => api<void>(`/admin/users/${id}/unsuspend`, { method: "POST" }),
  audit: (action?: string) => api<{ id: string; action: string; actor: string | null; created_at: string; data: Record<string, unknown>; ip_address: string | null }[]>(`/admin/audit-log${action ? `?action=${encodeURIComponent(action)}` : ""}`),
};

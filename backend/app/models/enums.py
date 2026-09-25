"""Domain enums. Stored as constrained VARCHAR (not native PG enums) so adding a value
is a simple migration rather than an ALTER TYPE dance."""

from enum import StrEnum


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    LINKEDIN = "linkedin"
    PINTEREST = "pinterest"
    X = "x"


class SocialAccountStatus(StrEnum):
    CONNECTED = "connected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"
    PENDING_REVIEW = "pending_review"


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


class MediaSource(StrEnum):
    UPLOAD = "upload"
    AI_GENERATED = "ai_generated"
    ASSEMBLED = "assembled"  # video built from the business's own photos and clips
    BRAND = "brand"
    IMPORT = "import"


class MediaStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class ContentType(StrEnum):
    POST = "post"
    CAROUSEL = "carousel"
    REEL = "reel"
    SHORT = "short"
    STORY = "story"
    VIDEO = "video"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    REJECTED = "rejected"


class ContentOrigin(StrEnum):
    AI = "ai"
    UPLOAD = "upload"
    IDEA = "idea"
    PRODUCT = "product"
    CAMPAIGN = "campaign"
    MANUAL = "manual"


class ScheduleStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    APPROVAL_OVERDUE = "approval_overdue"
    DONE = "done"
    CANCELLED = "cancelled"


class PublicationStatus(StrEnum):
    QUEUED = "queued"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetricScope(StrEnum):
    PUBLICATION = "publication"
    ACCOUNT = "account"


class InsightCategory(StrEnum):
    WORKING = "working"
    DECLINING = "declining"
    AUDIENCE = "audience"
    FORMAT = "format"
    TOPIC = "topic"
    POSTING_TIME = "posting_time"
    EXPERIMENT = "experiment"
    RECOMMENDATION = "recommendation"


class Confidence(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InsightStatus(StrEnum):
    ACTIVE = "active"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"


class MemoryCategory(StrEnum):
    AUDIENCE = "audience"
    BRAND = "brand"
    SUCCESSFUL_TOPIC = "successful_topic"
    WEAK_TOPIC = "weak_topic"
    SUCCESSFUL_FORMAT = "successful_format"
    WEAK_FORMAT = "weak_format"
    SUCCESSFUL_HOOK = "successful_hook"
    SUCCESSFUL_CTA = "successful_cta"
    PLATFORM_PATTERN = "platform_pattern"
    POSTING_TIME = "posting_time"
    EXPERIMENT = "experiment"
    CUSTOMER_FEEDBACK = "customer_feedback"


class MemorySource(StrEnum):
    USER = "user"
    ANALYTICS = "analytics"
    EXPERIMENT = "experiment"
    AGENT = "agent"


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"
    CANCELLED = "cancelled"


class AgentKind(StrEnum):
    ORCHESTRATOR = "orchestrator"
    STRATEGY = "strategy"
    RESEARCH = "research"
    CONTENT = "content"
    CREATIVE = "creative"
    PUBLISHING = "publishing"
    ANALYTICS = "analytics"
    OPTIMIZATION = "optimization"


class AgentRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEEDS_INPUT = "needs_input"
    LIMIT_REACHED = "limit_reached"


class AgentTrigger(StrEnum):
    USER = "user"
    SCHEDULE = "schedule"
    SYSTEM = "system"


class NotificationType(StrEnum):
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_OVERDUE = "approval_overdue"
    PRE_PUBLISH_REMINDER = "pre_publish_reminder"
    POST_PUBLISHED = "post_published"
    POST_FAILED = "post_failed"
    ACCOUNT_DISCONNECTED = "account_disconnected"
    AGENT_COMPLETED = "agent_completed"
    AGENT_NEEDS_INPUT = "agent_needs_input"
    ANALYTICS_INSIGHT = "analytics_insight"
    EXPERIMENT_RESULT = "experiment_result"
    SUBSCRIPTION_WARNING = "subscription_warning"
    QUOTA_WARNING = "quota_warning"
    PAYMENT_ISSUE = "payment_issue"
    SYSTEM = "system"


class Plan(StrEnum):
    FREE = "free"
    STARTER = "starter"
    BUSINESS = "business"
    AGENCY = "agency"


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    CANCELED = "canceled"


class AIOperation(StrEnum):
    TEXT = "text"
    REASONING = "reasoning"
    IMAGE = "image"
    VIDEO = "video"
    VOICE = "voice"
    RESEARCH = "research"
    EMBEDDING = "embedding"


class UsageStatus(StrEnum):
    RESERVED = "reserved"
    COMMITTED = "committed"
    REFUNDED = "refunded"

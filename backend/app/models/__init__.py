"""Importing this package registers every table on Base.metadata (Alembic relies on it)."""

from app.models.agents import AgentRun, AgentStep
from app.models.analytics import MetricSnapshot, PlatformMetric
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.billing import BillingEvent, Subscription
from app.models.business import Brand, BusinessProfile, Product, ProductMedia
from app.models.content import (
    Content,
    ContentMedia,
    ContentSchedule,
    ContentVariant,
    ContentVersion,
    Publication,
)
from app.models.identity import EmailVerificationToken, PasswordResetToken, Session, User
from app.models.intelligence import (
    Experiment,
    ExperimentVariant,
    MarketingInsight,
    MarketingMemory,
    ResearchItem,
)
from app.models.media import MediaAsset, MediaFolder
from app.models.notifications import Notification, NotificationPreference
from app.models.social import SocialAccount, SocialAccountToken
from app.models.usage import AIResponseCache, AIUsage
from app.models.workspace import Workspace, WorkspaceMember

__all__ = [
    "AIResponseCache",
    "ContentVersion",
    "AIUsage",
    "AgentRun",
    "AgentStep",
    "AuditLog",
    "Base",
    "BillingEvent",
    "Brand",
    "BusinessProfile",
    "Content",
    "ContentMedia",
    "ContentSchedule",
    "ContentVariant",
    "EmailVerificationToken",
    "Experiment",
    "ExperimentVariant",
    "MarketingInsight",
    "MarketingMemory",
    "MediaAsset",
    "MediaFolder",
    "MetricSnapshot",
    "Notification",
    "NotificationPreference",
    "PasswordResetToken",
    "PlatformMetric",
    "Product",
    "ProductMedia",
    "Publication",
    "ResearchItem",
    "Session",
    "SocialAccount",
    "SocialAccountToken",
    "Subscription",
    "User",
    "Workspace",
    "WorkspaceMember",
]

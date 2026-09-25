"""Transactional email copy. Plain, specific, one action per email."""

from __future__ import annotations

from html import escape
from typing import Any

from app.core.config import settings
from app.notifications.email.base import EmailMessage


def _html(heading: str, paragraphs: list[str], action: tuple[str, str] | None = None) -> str:
    body = "".join(
        f'<p style="margin:0 0 16px;line-height:1.55">{escape(p)}</p>' for p in paragraphs
    )
    button = ""
    if action:
        label, url = action
        button = (
            f'<p style="margin:24px 0"><a href="{escape(url)}" style="background:#0E6B63;color:#fff;'
            f'padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:600">'
            f"{escape(label)}</a></p>"
        )
    return (
        '<div style="font-family:-apple-system,Segoe UI,sans-serif;color:#13201E;max-width:520px;'
        f'margin:0 auto;padding:32px 24px"><h1 style="font-size:20px;margin:0 0 20px">{escape(heading)}</h1>'
        f"{body}{button}"
        '<p style="color:#5B6B67;font-size:13px;margin-top:32px">ContentFactory</p></div>'
    )


def render(template: str, to: str, params: dict[str, Any]) -> EmailMessage:
    name = params.get("name") or "there"
    app = settings.APP_URL
    match template:
        case "notification":
            url = f"{app}{params.get('action_url') or '/dashboard'}"
            paras = [
                f"Hi {name},",
                params["title"],
                *([params["body"]] if params.get("body") else []),
            ]
            footer = "You can change which emails you get in Settings, Notifications."
            return EmailMessage(
                to,
                params["title"][:150],
                "\n\n".join([*paras, url, footer]),
                _html(params["title"], [*paras[2:], footer], ("Open ContentFactory", url)),
            )
        case "verify_email":
            url = f"{app}/verify-email?token={params['token']}"
            paras = [
                f"Hi {name},",
                "Confirm your email address to finish setting up ContentFactory. "
                f"This link expires in {settings.EMAIL_VERIFICATION_TTL_HOURS} hours.",
            ]
            return EmailMessage(
                to,
                "Confirm your email",
                "\n\n".join([*paras, url]),
                _html("Confirm your email", paras, ("Confirm email", url)),
            )
        case "reset_password":
            url = f"{app}/reset-password?token={params['token']}"
            paras = [
                f"Hi {name},",
                "Someone asked to reset the password for this account. If it was you, choose a new "
                f"password below. The link expires in {settings.PASSWORD_RESET_TTL_MINUTES} minutes.",
                "If you didn't ask for this, you can ignore this email. Your password won't change.",
            ]
            return EmailMessage(
                to,
                "Reset your password",
                "\n\n".join([*paras, url]),
                _html("Reset your password", paras, ("Choose a new password", url)),
            )
        case "password_changed":
            paras = [
                f"Hi {name},",
                "Your ContentFactory password was just changed and other devices were signed out.",
                "If this wasn't you, reset your password right away and contact support.",
            ]
            return EmailMessage(
                to,
                "Your password was changed",
                "\n\n".join(paras),
                _html(
                    "Your password was changed", paras, ("Reset password", f"{app}/forgot-password")
                ),
            )
        case "account_exists":
            paras = [
                f"Hi {name},",
                "Someone tried to create a ContentFactory account with this email, but you already "
                "have one. Sign in instead, or reset your password if you've forgotten it.",
            ]
            return EmailMessage(
                to,
                "You already have an account",
                "\n\n".join(paras),
                _html("You already have an account", paras, ("Sign in", f"{app}/login")),
            )
        case "account_deleted":
            paras = [
                "Your ContentFactory account and its workspaces have been deleted.",
                "Thanks for trying ContentFactory.",
            ]
            return EmailMessage(
                to,
                "Your account was deleted",
                "\n\n".join(paras),
                _html("Your account was deleted", paras),
            )
        case "contact_form":
            text = f"From: {params['from_name']} <{params['from_email']}>\n\n{params['message']}"
            return EmailMessage(
                to,
                f"Contact form: {params['topic']}",
                text,
                f"<pre style='white-space:pre-wrap'>{escape(text)}</pre>",
            )
    raise ValueError(f"Unknown email template: {template}")

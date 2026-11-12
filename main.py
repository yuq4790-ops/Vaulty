from __future__ import annotations

import asyncio
import html
import io
import logging
import os
import re
import traceback
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not founded!")

GUILD_ID = 1552013736070357132
PANEL_CHANNEL_ID = 1568025641570279496
TICKET_CATEGORY_ID = 1567979963435581460
CLOSED_TICKET_CATEGORY_ID = 1552013736070357132
SUPPORT_ROLE_ID = 1552047493456339004
ADMIN_ROLE_ID = 1552046990605688952
LOG_CHANNEL_ID = 1552846873394675742
TRANSCRIPT_CHANNEL_ID = 1552846873394675742
PAYMENT_CONFIRM_USER_IDS = []

MAX_TICKETS_PER_USER = 3
NOTIFY_COOLDOWN_SECONDS = 120
DELETE_DELAY_SECONDS = 5
TRANSCRIPT_MESSAGE_LIMIT = None
TRANSCRIPT_FORMAT = "html"

INACTIVITY_HOURS = 24
INACTIVITY_CHECK_INTERVAL_SECONDS = 300

SLASH_GROUP_NAME = "ticket"

TICKET_CATEGORIES = {
    "support": {
        "label": "General Support",
        "description": "Questions, problems and general help.",
        "prefix": "support",
        "ask_service": False,
        "ask_payment": False,
        "color": 0x00bfff,
    },
    "order": {
        "label": "New Order",
        "description": "Order one of our services.",
        "prefix": "order",
        "ask_service": True,
        "ask_payment": True,
        "color": 0x00bfff,
    },
    "billing": {
        "label": "Billing & Payments",
        "description": "Invoices, refunds and payment problems.",
        "prefix": "billing",
        "ask_service": False,
        "ask_payment": True,
        "color": 0x00bfff,
    },
    "partnership": {
        "label": "Partnership",
        "description": "Business requests and cooperation.",
        "prefix": "partner",
        "ask_service": False,
        "ask_payment": False,
        "color": 0x00bfff,
    },
}

SERVICES = [
    {"label": "Discord Bot Development", "description": "Custom bot made for your server"},
    {"label": "Server Setup", "description": "Full server structure and roles"},
    {"label": "Graphic Design", "description": "Logos, banners and emotes, GFX"},
    {"label": "Discord Tools", "description": "Server Cloner, Merch Cloner, Boost Bots,"},
    {"label": "Discord Stuff", "description": "Nitro Boost, Server Boosts, Decoration, Accounts"},
    {"label": "Other", "description": "Anything not listed here"},
]

PAYMENT_METHODS = [
    {"label": "PayPal", "description": "Pay via PayPal"},
    {"label": "Bank Transfer", "description": "SEPA / bank transfer"},
    {"label": "Credit Card", "description": "Visa / Mastercard"},
    {"label": "Crypto", "description": "BTC / ETH / LTC"},
    {"label": "Roblox", "description": "Robux / Pass / Transfer"},
    {"label": "Giftcards", "description": "Paysafe / Steam / Roblox / Apple"},
]

PAYMENT_DETAILS = {
    "PayPal": "Email: gibmalfeuerzeug79@gmail.com\nSend as Friends & Family.",
    "Credit Card": "A payment link will be sent to you inside this ticket.",
    "Crypto": "BTC: bc1q8mv8ccx9acplppqeue3rkk2wqh5p0hrxnscxck\nETH: 0x9a8210Dc30C70D11275ce9071D1b86Fe8e06751e\nLTC: Lg4jwAr7wHPE93EgWDzHs8moM5HLHMRLuv",
    "Roblox": "Gamepass / Group: Manually (Soon pass)",
    "Giftcards": "Send the code only in my dms!. Accepted: Paysafe, Steam, Roblox, Apple.",
}

TICKET_NAME_FORMAT = "{prefix}-{number:04d}"
CLOSED_NAME_FORMAT = "closed-{number:04d}"

PANEL_TITLE = "Support & Orders"
PANEL_DESCRIPTION = (
    "Need help or want to place an order?\n"
    "Pick a category below and a ticket channel will be created for you."
)
PANEL_FOOTER = "Please open only one ticket per topic."
PANEL_SELECT_PLACEHOLDER = "Select a ticket category..."
PANEL_THUMBNAIL_URL = ""
PANEL_COLOR = 0x00bfff
BANNER_URL = "https://cdn.discordapp.com/attachments/1292435237653184554/1570138869095989268/vw5qfhw.gif?ex=6af60146&is=6af4afc6&hm=77aada594a91f4e77b93404365105359301f52108138b488e753427da30b1cea&"

# ---------------------------------------------------------------------------
# BUTTON EMOJIS
# Trag hier bei jedem Button den Emoji-Namen und die Emoji-ID ein.
#   "name": Name des Emojis (z.B. "RUSH_checkmark")
#   "id":   ID des Emojis (Zahl). 0 = kein Emoji (Button bleibt nur Text)
#   "animated": True, falls es ein animiertes Emoji ist
# Standard-Unicode-Emojis gehen auch: {"name": "✅", "id": 0} wird NICHT
# funktionieren, dafuer unten bei UNICODE_EMOJIS eintragen.
# Emoji-ID bekommst du, indem du im Discord-Chat \:emojiname: schreibst
# und abschickst -> <:name:123456789> (die Zahl ist die ID).
# ---------------------------------------------------------------------------
EMOJIS = {
    # Ticket-Panel (offenes Ticket)
    "close": {"leave": "", "id": 1570427499748397176, "animated": False},
    "transcript": {"poll": "", "id": 1570427370874085376, "animated": False},
    "claim": {"profile": "", "id": 1570473947248599040, "animated": False},
    "unclaim": {"left_arrow": "", "id": 1570474378813120613, "animated": False},
    "notify": {"bell": "", "id": 1570470230109724824, "animated": False},
    "payment_info": {"crypto": "", "id": 1570469831457902672, "animated": False},

    # Zahlungsbestaetigung
    "payment_confirm": {"dot": "", "id": 1570474919886594199, "animated": False},
    "payment_confirmed": {"checkmark": "", "id": 1570475101865123880, "animated": False},

    # Geschlossenes Ticket
    "reopen": {"reload": "", "id": 1570475350364913724, "animated": False},
    "closed_transcript": {"poll": "", "id": 1570427370874085376, "animated": False},
    "delete": {"leave": "", "id": 1570427499748397176, "animated": False},

    # Inaktivitaets-Nachricht
    "request_close": {"leave": "", "id": 1570427499748397176, "animated": False},
    "request_keep": {"thumbs_up": "", "id": 1570476249988726845, "animated": False},

    # Schliessen-Bestaetigung
    "confirm": {"checkmark": "", "id": 1570475101865123880, "animated": False},
    "cancel": {"cross": "", "id": 1570427220835438652, "animated": False},

    # Ticket-Erstellung (Wizard) - diese beiden hattest du schon
    "wizard_create": {"checkmark": "", "id": 1570475101865123880, "animated": False},
    "wizard_cancel": {"cross": "", "id": 1570427220835438652, "animated": False},
}

# Optional: normale Unicode-Emojis statt Custom-Emojis, z.B. {"close": "🔒"}
# Hat Vorrang nicht vor EMOJIS: ist bei EMOJIS eine ID gesetzt, wird diese genommen.
UNICODE_EMOJIS: dict[str, str] = {}

# Text-Fallback fuer Buttons, die NUR ein Emoji haben (damit der Button nie leer ist,
# falls du das Emoji noch nicht eingetragen hast)
ICON_ONLY_FALLBACK_LABELS = {
    "wizard_create": "Create Ticket",
    "wizard_cancel": "Cancel",
}

WELCOME_MESSAGES = {
    "default": (
        "Welcome {user}! Thanks for opening a **{category}** ticket.\n"
        "Please describe your request in as much detail as possible.\n"
        "{support_role} will be with you shortly."
    ),
    "order": (
        "Welcome {user}! Thanks for your order request.\n"
        "**Service:** {service}\n**Payment:** {payment}\n\n"
        "Please tell us what you need, your deadline and any references.\n"
        "{support_role} will get back to you shortly."
    ),
    "billing": (
        "Welcome {user}! Please send your order/invoice reference\n"
        "and describe the "
        "problem. Preferred payment method: **{payment}**."
    ),
}

FEATURES = {
    "claim_button": True,
    "notify_button": True,
    "transcript_button": True,
    "delete_button": True,
    "payment_info_button": True,
    "payment_confirm_button": True,
    "payment_info_public": False,
    "inactivity_close_request": True,
    "logging": True,
    "confirm_close": True,
    "auto_transcript_on_close": True,
    "dm_transcript_to_owner": False,
    "owner_can_close": True,
    "owner_can_transcript": False,
    "owner_can_reopen": False,
    "rename_on_close": True,
    "auto_post_panel": False,
    "banner_on_notice": True,
}

CID_PANEL = "ticketsys:panel:category"
CID_CLOSE = "ticketsys:ticket:close"
CID_TRANSCRIPT = "ticketsys:ticket:transcript"
CID_CLAIM = "ticketsys:ticket:claim"
CID_NOTIFY = "ticketsys:ticket:notify"
CID_PAYMENT_INFO = "ticketsys:ticket:payinfo"
CID_PAYMENT_CONFIRM = "ticketsys:ticket:payconfirm"
CID_REOPEN = "ticketsys:closed:reopen"
CID_CLOSED_TRANSCRIPT = "ticketsys:closed:transcript"
CID_DELETE = "ticketsys:closed:delete"
CID_REQUEST_CLOSE = "ticketsys:request:close"
CID_REQUEST_KEEP = "ticketsys:request:keep"

KIND_COLORS = {"info": 0x00bfff, "success": 0x00bfff, "error": 0x00bfff, "warn": 0x00bfff}

PAYMENT_STATUS_TEXT = {
    "pending": "Awaiting payment",
    "verified": "Confirmed",
}

_REQUIRED_UI = (
    "LayoutView", "Container", "TextDisplay", "Separator", "Section", "ActionRow", "Thumbnail", "MediaGallery"
)
_missing = [n for n in _REQUIRED_UI if not hasattr(discord.ui, n)]
if _missing:
    raise SystemExit(
        f"discord.py {discord.__version__} does not support Components V2 "
        f"(missing: {', '.join(_missing)}).\nUpgrade with:  pip install -U \"discord.py>=2.6\""
    )

log = logging.getLogger("ticketsystem")


def now() -> datetime:
    return datetime.now(timezone.utc)


def emoji(key: str) -> Optional[discord.PartialEmoji]:
    """Gibt das Emoji fuer einen Button zurueck (oder None, wenn keins eingetragen ist)."""
    data = EMOJIS.get(key)
    if data and data.get("id"):
        return discord.PartialEmoji(
            name=data.get("name") or "emoji",
            id=int(data["id"]),
            animated=bool(data.get("animated", False)),
        )
    uni = UNICODE_EMOJIS.get(key)
    if uni:
        return discord.PartialEmoji(name=uni)
    return None


def icon_label(key: str) -> Optional[str]:
    """Label fuer reine Icon-Buttons: nur Text, wenn (noch) kein Emoji gesetzt ist."""
    return None if emoji(key) else ICON_ONLY_FALLBACK_LABELS.get(key, "Button")


@dataclass
class Ticket:
    number: int
    channel_id: int
    guild_id: int
    owner_id: int
    owner_name: str
    owner_avatar: str
    category: str
    service: Optional[str]
    payment: Optional[str]
    base_name: str
    welcome: str
    created_at: datetime
    status: str = "open"
    claimed_by: Optional[int] = None
    added_users: set = field(default_factory=set)
    panel_message_id: Optional[int] = None
    closed_by: Optional[int] = None
    closed_at: Optional[datetime] = None
    close_reason: Optional[str] = None
    payment_status: str = "pending"
    payment_verified_by: Optional[int] = None
    payment_confirmed_at: Optional[datetime] = None
    payment_message_id: Optional[int] = None
    last_activity: datetime = field(default_factory=now)
    close_request_sent: bool = False


tickets: dict[int, Ticket] = {}
ticket_counter = 0
creating_users: set[int] = set()
notify_cooldowns: dict[int, float] = {}
STATS = {"created": 0, "closed": 0, "reopened": 0, "deleted": 0, "transcripts": 0}
CATEGORY_COUNTS: Counter = Counter()
CLAIMS_BY_STAFF: Counter = Counter()
_panel_boot_done = False


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def sanitize_channel_name(value: str) -> str:
    value = value.lower().strip().replace(" ", "-")
    value = re.sub(r"[^a-z0-9\-_]", "", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:90] or "ticket"


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


def is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator or any(r.id == ADMIN_ROLE_ID for r in member.roles)


def is_staff(member: discord.Member) -> bool:
    return is_admin(member) or any(r.id == SUPPORT_ROLE_ID for r in member.roles)


def can_confirm_payment(member: discord.Member) -> bool:
    if PAYMENT_CONFIRM_USER_IDS:
        return member.id in PAYMENT_CONFIRM_USER_IDS
    return is_admin(member)


def count_open(user_id: int) -> int:
    return sum(1 for t in tickets.values() if t.owner_id == user_id and t.status == "open")


def get_category_channel(guild: discord.Guild, channel_id: int) -> Optional[discord.CategoryChannel]:
    ch = guild.get_channel(channel_id) if channel_id else None
    return ch if isinstance(ch, discord.CategoryChannel) else None


def get_text_channel(guild: discord.Guild, channel_id: int) -> Optional[discord.TextChannel]:
    ch = guild.get_channel(channel_id) if channel_id else None
    return ch if isinstance(ch, discord.TextChannel) else None


async def get_member(guild: discord.Guild, user_id: int) -> Optional[discord.Member]:
    member = guild.get_member(user_id)
    if member:
        return member
    try:
        return await guild.fetch_member(user_id)
    except discord.HTTPException:
        return None


def build_channel_name(prefix: str, number: int, user_name: str) -> str:
    try:
        raw = TICKET_NAME_FORMAT.format(prefix=prefix, number=number, user=sanitize_channel_name(user_name))
    except (KeyError, ValueError, IndexError):
        raw = f"{prefix}-{number:04d}"
    return sanitize_channel_name(raw)


def closed_channel_name(ticket: Ticket) -> str:
    try:
        return sanitize_channel_name(CLOSED_NAME_FORMAT.format(number=ticket.number, prefix="closed"))
    except (KeyError, ValueError, IndexError):
        return f"closed-{ticket.number:04d}"


def format_welcome(category_key: str, values: dict) -> str:
    template = WELCOME_MESSAGES.get(category_key) or WELCOME_MESSAGES.get("default", "Welcome {user}!")
    try:
        return template.format_map(_Safe(values))
    except (ValueError, IndexError):
        return template


def component_text(components) -> list[str]:
    out: list[str] = []
    for comp in components or []:
        content = getattr(comp, "content", None)
        if isinstance(content, str) and content:
            out.append(content)
        kids = getattr(comp, "children", None)
        if kids:
            out.extend(component_text(kids))
    return out


def staff_mention(ticket: Ticket) -> tuple[str, discord.AllowedMentions]:
    if ticket.claimed_by:
        return f"<@{ticket.claimed_by}>", discord.AllowedMentions(users=[discord.Object(id=ticket.claimed_by)])
    if SUPPORT_ROLE_ID:
        return f"<@&{SUPPORT_ROLE_ID}>", discord.AllowedMentions(roles=[discord.Object(id=SUPPORT_ROLE_ID)])
    return "Staff", discord.AllowedMentions.none()


def add_banner(container, small: bool = False) -> None:
    if not BANNER_URL:
        return
    if small and not FEATURES["banner_on_notice"]:
        return
    container.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(BANNER_URL)))


class HButton(discord.ui.Button):

    def __init__(self, handler, **kwargs):
        super().__init__(**kwargs)
        self._handler = handler

    async def callback(self, interaction: discord.Interaction):
        await self._handler(interaction)


class HSelect(discord.ui.Select):

    def __init__(self, handler, **kwargs):
        super().__init__(**kwargs)
        self._handler = handler

    async def callback(self, interaction: discord.Interaction):
        await self._handler(interaction, self)


class BaseLayout(discord.ui.LayoutView):
    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        log.error("View error: %s", "".join(traceback.format_exception(type(error), error, error.__traceback__)))
        try:
            await say(interaction, "Something went wrong while handling that action.", "error")
        except discord.HTTPException:
            pass


class Notice(BaseLayout):

    def __init__(self, text: str, kind: str = "info", banner: bool = True):
        super().__init__(timeout=None)
        container = discord.ui.Container(accent_colour=KIND_COLORS.get(kind, KIND_COLORS["info"]))
        container.add_item(discord.ui.TextDisplay(text))
        if banner:
            add_banner(container, small=True)
        self.add_item(container)


async def say(interaction: discord.Interaction, text: str, kind: str = "info") -> None:
    view = Notice(text, kind, banner=False)
    if interaction.response.is_done():
        await interaction.followup.send(view=view, ephemeral=True)
    else:
        await interaction.response.send_message(view=view, ephemeral=True)


async def ack(interaction: discord.Interaction) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True, thinking=True)


async def log_event(guild: discord.Guild, title: str, description: str, kind: str = "info") -> None:
    if not FEATURES["logging"]:
        return
    channel = get_text_channel(guild, LOG_CHANNEL_ID)
    if not channel:
        return
    try:
        await channel.send(
            view=Notice(f"### {title}\n{description}\n-# <t:{int(now().timestamp())}:F>", kind),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException:
        log.warning("Could not write to the log channel.")


class PanelView(BaseLayout):

    def __init__(self):
        super().__init__(timeout=None)
        container = discord.ui.Container(accent_colour=PANEL_COLOR)
        head = f"# {PANEL_TITLE}\n{PANEL_DESCRIPTION}"
        if PANEL_THUMBNAIL_URL:
            container.add_item(
                discord.ui.Section(discord.ui.TextDisplay(head), accessory=discord.ui.Thumbnail(PANEL_THUMBNAIL_URL))
            )
        else:
            container.add_item(discord.ui.TextDisplay(head))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
        lines = [f"**{c['label']}** - {c['description']}" for c in TICKET_CATEGORIES.values()]
        container.add_item(discord.ui.TextDisplay("\n".join(lines)))
        container.add_item(discord.ui.Separator())
        options = [
            discord.SelectOption(label=c["label"], value=key, description=c["description"][:100])
            for key, c in TICKET_CATEGORIES.items()
        ]
        container.add_item(
            discord.ui.ActionRow(
                HSelect(on_panel_select, custom_id=CID_PANEL, placeholder=PANEL_SELECT_PLACEHOLDER, options=options)
            )
        )
        if PANEL_FOOTER:
            container.add_item(discord.ui.TextDisplay(f"-# {PANEL_FOOTER}"))
        add_banner(container)
        self.add_item(container)


def _ticket_details(ticket: Ticket) -> str:
    cat = TICKET_CATEGORIES.get(ticket.category, {"label": ticket.category})
    lines = [
        f"**Owner:** <@{ticket.owner_id}>",
        f"**Category:** {cat['label']}",
    ]
    if ticket.service:
        lines.append(f"**Service:** {ticket.service}")
    if ticket.payment:
        lines.append(f"**Payment:** {ticket.payment}")
    if cat.get("ask_payment"):
        status = PAYMENT_STATUS_TEXT.get(ticket.payment_status, ticket.payment_status)
        lines.append(f"**Payment status:** {status}")
        if ticket.payment_status == "verified" and ticket.payment_verified_by:
            lines.append(f"**Confirmed by:** <@{ticket.payment_verified_by}>")
    if ticket.status == "open":
        lines.append("**Status:** Open")
        lines.append(f"**Claimed by:** <@{ticket.claimed_by}>" if ticket.claimed_by else "**Claimed by:** *Unclaimed*")
    else:
        lines.append("**Status:** Closed")
        if ticket.closed_by:
            lines.append(f"**Closed by:** <@{ticket.closed_by}>")
        if ticket.close_reason:
            lines.append(f"**Reason:** {ticket.close_reason}")
    lines.append(f"**Created:** <t:{int(ticket.created_at.timestamp())}:R>")
    if ticket.added_users:
        lines.append("**Added users:** " + ", ".join(f"<@{u}>" for u in sorted(ticket.added_users)))
    return "\n".join(lines)


class TicketView(BaseLayout):

    def __init__(self, ticket: Optional[Ticket] = None, *, ping: bool = False):
        super().__init__(timeout=None)
        container = discord.ui.Container(accent_colour=0x00bfff)
        if ticket:
            if ping:
                mentions = f"<@{ticket.owner_id}>"
                if SUPPORT_ROLE_ID:
                    mentions += f" <@&{SUPPORT_ROLE_ID}>"
                container.add_item(discord.ui.TextDisplay(f"-# {mentions}"))
            container.add_item(discord.ui.TextDisplay(f"# Ticket #{ticket.number:04d}"))
            container.add_item(discord.ui.Separator())
            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(_ticket_details(ticket)),
                    accessory=discord.ui.Thumbnail(ticket.owner_avatar),
                )
            )
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(ticket.welcome))
            container.add_item(discord.ui.Separator())
        else:
            container.add_item(discord.ui.TextDisplay("Ticket"))

        claimed = bool(ticket and ticket.claimed_by)
        buttons = [
            HButton(handle_close_button, label="Close", emoji=emoji("close"),
                    style=discord.ButtonStyle.primary, custom_id=CID_CLOSE)
        ]
        if FEATURES["transcript_button"]:
            buttons.append(
                HButton(handle_transcript, label="Transcript", emoji=emoji("transcript"),
                        style=discord.ButtonStyle.primary, custom_id=CID_TRANSCRIPT)
            )
        if FEATURES["claim_button"]:
            buttons.append(
                HButton(
                    handle_claim,
                    label="Unclaim" if claimed else "Claim",
                    emoji=emoji("unclaim" if claimed else "claim"),
                    style=discord.ButtonStyle.secondary if claimed else discord.ButtonStyle.primary,
                    custom_id=CID_CLAIM,
                )
            )
        if FEATURES["notify_button"]:
            buttons.append(
                HButton(handle_notify, label="Notify", emoji=emoji("notify"),
                        style=discord.ButtonStyle.primary, custom_id=CID_NOTIFY)
            )
        container.add_item(discord.ui.ActionRow(*buttons))

        show_payment = ticket is None or bool(TICKET_CATEGORIES.get(ticket.category, {}).get("ask_payment"))
        if show_payment:
            pay_buttons = []
            if FEATURES["payment_info_button"] and PAYMENT_DETAILS:
                pay_buttons.append(
                    HButton(handle_payment_info, label="Payment Info", emoji=emoji("payment_info"),
                            style=discord.ButtonStyle.primary, custom_id=CID_PAYMENT_INFO)
                )
            if pay_buttons:
                container.add_item(discord.ui.ActionRow(*pay_buttons))
        add_banner(container)
        self.add_item(container)


class ClosedTicketView(BaseLayout):

    def __init__(self, ticket: Optional[Ticket] = None):
        super().__init__(timeout=None)
        container = discord.ui.Container(accent_colour=0x00bfff)
        if ticket:
            container.add_item(discord.ui.TextDisplay(f"# Ticket #{ticket.number:04d} (closed)"))
            container.add_item(discord.ui.Separator())
            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(_ticket_details(ticket)),
                    accessory=discord.ui.Thumbnail(ticket.owner_avatar),
                )
            )
            container.add_item(discord.ui.Separator())
        else:
            container.add_item(discord.ui.TextDisplay("Closed ticket"))
        buttons = [
            HButton(handle_reopen, label="Reopen", emoji=emoji("reopen"),
                    style=discord.ButtonStyle.primary, custom_id=CID_REOPEN)
        ]
        if FEATURES["transcript_button"]:
            buttons.append(
                HButton(handle_transcript, label="Transcript", emoji=emoji("closed_transcript"),
                        style=discord.ButtonStyle.primary, custom_id=CID_CLOSED_TRANSCRIPT)
            )
        if FEATURES["delete_button"]:
            buttons.append(
                HButton(handle_delete, label="Delete", emoji=emoji("delete"),
                        style=discord.ButtonStyle.primary, custom_id=CID_DELETE))
        container.add_item(discord.ui.ActionRow(*buttons))
        add_banner(container)
        self.add_item(container)


class PaymentInfoView(BaseLayout):

    def __init__(self, ticket: Optional[Ticket] = None):
        super().__init__(timeout=None)
        container = discord.ui.Container(accent_colour=PANEL_COLOR)
        container.add_item(discord.ui.TextDisplay("# Payment Information"))
        container.add_item(discord.ui.Separator())
        selected = ticket.payment if ticket else None
        labels = list(PAYMENT_DETAILS.keys())
        if selected in PAYMENT_DETAILS:
            labels.remove(selected)
            labels.insert(0, selected)
        for label in labels:
            title = f"### {label}" + (" (selected)" if label == selected else "")
            container.add_item(discord.ui.TextDisplay(f"{title}\n```\n{PAYMENT_DETAILS[label]}\n```"))
        container.add_item(discord.ui.Separator())
        container.add_item(
            discord.ui.TextDisplay(
                "-# After sending your payment, press the Payment Confirmation button in the ticket.")
        )

        self.add_item(container)


class PaymentConfirmView(BaseLayout):

    def __init__(self, ticket: Optional[Ticket] = None):
        super().__init__(timeout=None)
        container = discord.ui.Container(accent_colour=PANEL_COLOR)
        confirmed = bool(ticket and ticket.payment_status == "verified")
        if ticket:
            lines = ["### Payment Confirmation", f"**Method:** {ticket.payment or '-'}"]
            if confirmed:
                status = f"**Status:** Confirmed by <@{ticket.payment_verified_by}>"
                if ticket.payment_confirmed_at:
                    status += f" <t:{int(ticket.payment_confirmed_at.timestamp())}:R>"
                lines.append(status)
            else:
                lines.append("**Status:** Awaiting payment")
                lines.append("-# Only the shop owner can confirm the payment once it has been received.")
            text = "\n".join(lines)
        else:
            text = "### Payment Confirmation"
        container.add_item(discord.ui.TextDisplay(text))
        container.add_item(
            discord.ui.ActionRow(
                HButton(
                    handle_payment_confirm,
                    label="Payment Confirmed" if confirmed else "Payment Confirmation",
                    emoji=emoji("payment_confirmed" if confirmed else "payment_confirm"),
                    style=discord.ButtonStyle.secondary if confirmed else discord.ButtonStyle.primary,
                    disabled=confirmed,
                    custom_id=CID_PAYMENT_CONFIRM,
                )
            )
        )
        self.add_item(container)


class CloseRequestView(BaseLayout):

    def __init__(self, ticket: Optional[Ticket] = None):
        super().__init__(timeout=None)
        container = discord.ui.Container(accent_colour=KIND_COLORS["warn"])
        if ticket:
            text = (
                f"## Close Request\n<@{ticket.owner_id}>, there has been no activity in this ticket for "
                f"{INACTIVITY_HOURS} hours.\nIf you do not need further help, you can close it now. "
                f"Writing a message here keeps the ticket open."
            )
        else:
            text = "## Close Request"
        container.add_item(discord.ui.TextDisplay(text))
        container.add_item(
            discord.ui.ActionRow(
                HButton(handle_request_close, label="Close Ticket", emoji=emoji("request_close"),
                        style=discord.ButtonStyle.primary, custom_id=CID_REQUEST_CLOSE),
                HButton(handle_request_keep, label="Keep Open", emoji=emoji("request_keep"),
                        style=discord.ButtonStyle.primary, custom_id=CID_REQUEST_KEEP),
            )
        )
        add_banner(container)
        self.add_item(container)


class CreateWizard(BaseLayout):

    def __init__(self, category_key: str):
        super().__init__(timeout=300)
        self.category_key = category_key
        self.service: Optional[str] = None
        self.payment: Optional[str] = None
        self.build()

    @property
    def cat(self) -> dict:
        return TICKET_CATEGORIES[self.category_key]

    @property
    def needs_service(self) -> bool:
        return bool(self.cat.get("ask_service") and SERVICES)

    @property
    def needs_payment(self) -> bool:
        return bool(self.cat.get("ask_payment") and PAYMENT_METHODS)

    def ready(self) -> bool:
        return (not self.needs_service or self.service is not None) and (
                not self.needs_payment or self.payment is not None)

    @staticmethod
    def _options(items: list[dict], selected: Optional[str]) -> list[discord.SelectOption]:
        return [
            discord.SelectOption(
                label=i["label"][:100],
                value=i["label"][:100],
                description=i.get("description", "")[:100] or None,
                default=(i["label"][:100] == selected),
            )
            for i in items[:25]
        ]

    def build(self) -> None:
        self.clear_items()
        cat = self.cat
        container = discord.ui.Container(accent_colour=cat.get("color", 0x00bfff))
        container.add_item(discord.ui.TextDisplay(f"## {cat['label']}\n{cat['description']}"))
        container.add_item(discord.ui.Separator())
        step = 1
        if self.needs_service:
            container.add_item(discord.ui.TextDisplay(f"**Step {step} - Choose a service**"))
            container.add_item(
                discord.ui.ActionRow(HSelect(self.on_service, placeholder="Select a service...",
                                             options=self._options(SERVICES, self.service)))
            )
            step += 1
        if self.needs_payment:
            container.add_item(discord.ui.TextDisplay(f"**Step {step} - Choose a payment method**"))
            container.add_item(
                discord.ui.ActionRow(
                    HSelect(self.on_payment, placeholder="Select a payment method...",
                            options=self._options(PAYMENT_METHODS, self.payment))
                )
            )
        container.add_item(discord.ui.Separator())
        container.add_item(
            discord.ui.ActionRow(
                HButton(
                    self.on_create,
                    label=icon_label("wizard_create"),
                    emoji=emoji("wizard_create"),
                    style=discord.ButtonStyle.primary,
                    disabled=not self.ready()
                ),
                HButton(
                    self.on_cancel,
                    label=icon_label("wizard_cancel"),
                    emoji=emoji("wizard_cancel"),
                    style=discord.ButtonStyle.primary
                )
            )
        )
        add_banner(container)
        self.add_item(container)

    async def on_service(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.service = select.values[0]
        self.build()
        await interaction.response.edit_message(view=self)

    async def on_payment(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.payment = select.values[0]
        self.build()
        await interaction.response.edit_message(view=self)

    async def on_cancel(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(view=Notice("Ticket creation cancelled.", "warn", banner=False))

    async def on_create(self, interaction: discord.Interaction):
        if not self.ready():
            await say(interaction, "Please complete all selections first.", "warn")
            return
        member = interaction.user
        guild = interaction.guild
        if guild is None or not isinstance(member, discord.Member):
            await say(interaction, "This can only be used inside the server.", "error")
            return
        await interaction.response.edit_message(view=Notice("Creating your ticket...", "info", banner=False))
        self.stop()
        ticket, error = await open_ticket(guild, member, self.category_key, self.service, self.payment)
        if error or not ticket:
            await interaction.edit_original_response(view=Notice(f"{error}", "error", banner=False))
            return
        await interaction.edit_original_response(
            view=Notice(f"Your ticket has been created: <#{ticket.channel_id}>", "success", banner=False))


class ConfirmCloseView(BaseLayout):
    def __init__(self, channel_id: int):
        super().__init__(timeout=60)
        self.channel_id = channel_id
        container = discord.ui.Container(accent_colour=KIND_COLORS["warn"])
        container.add_item(
            discord.ui.TextDisplay(
                "## Close this ticket?\nThe channel will be locked and moved to the closed category.")
        )
        container.add_item(
            discord.ui.ActionRow(
                HButton(self.on_confirm, label="Confirm", emoji=emoji("confirm"),
                        style=discord.ButtonStyle.primary),
                HButton(self.on_cancel, label="Cancel", emoji=emoji("cancel"),
                        style=discord.ButtonStyle.primary),
            )
        )
        self.add_item(container)

    async def on_cancel(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(view=Notice("Cancelled.", "info", banner=False))

    async def on_confirm(self, interaction: discord.Interaction):
        self.stop()
        ticket = tickets.get(self.channel_id)
        guild = interaction.guild
        member = interaction.user
        if not ticket or guild is None or not isinstance(member, discord.Member):
            await interaction.response.edit_message(
                view=Notice("This ticket is no longer tracked.", "error", banner=False))
            return
        if not can(member, ticket, "close"):
            await interaction.response.edit_message(
                view=Notice("You are not allowed to close this ticket.", "error", banner=False))
            return
        await interaction.response.edit_message(view=Notice("Closing ticket...", "info", banner=False))
        channel = guild.get_channel(ticket.channel_id)
        ok, text = await core_close(guild, channel, ticket, member, None)
        await interaction.edit_original_response(view=Notice(text, "success" if ok else "error", banner=False))


def can(member: discord.Member, ticket: Ticket, action: str) -> bool:
    staff = is_staff(member)
    owner = member.id == ticket.owner_id
    if action == "close":
        return staff or (owner and FEATURES["owner_can_close"])
    if action == "transcript":
        return staff or (owner and FEATURES["owner_can_transcript"])
    if action == "reopen":
        return staff or (owner and FEATURES["owner_can_reopen"])
    if action in ("notify", "payment"):
        return staff or owner
    if action == "payment_confirm":
        return can_confirm_payment(member)
    return staff


async def ctx(interaction: discord.Interaction, action: str) -> Optional[tuple[Ticket, discord.Member]]:
    guild = interaction.guild
    member = interaction.user
    if guild is None or guild.id != GUILD_ID or not isinstance(member, discord.Member):
        await say(interaction, "This can only be used inside the configured server.", "error")
        return None
    ticket = tickets.get(interaction.channel_id or 0)
    if not ticket:
        await say(interaction,
                  "This is not an active ticket channel (or the bot was restarted and no longer tracks it).", "error")
        return None
    if not can(member, ticket, action):
        denied = "Only the shop owner can confirm payments." if action == "payment_confirm" else \
            "You don't have permission to do that."
        await say(interaction, denied, "error")
        return None
    return ticket, member


async def open_ticket(
        guild: discord.Guild, member: discord.Member, category_key: str, service: Optional[str], payment: Optional[str]
) -> tuple[Optional[Ticket], Optional[str]]:
    global ticket_counter
    if category_key not in TICKET_CATEGORIES:
        return None, "Unknown ticket category."
    if member.id in creating_users:
        return None, "Your ticket is already being created."
    creating_users.add(member.id)
    try:
        if count_open(member.id) >= MAX_TICKETS_PER_USER:
            return None, f"You already have {MAX_TICKETS_PER_USER} open ticket(s). Please close one first."

        cat = TICKET_CATEGORIES[category_key]
        support_role = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None
        admin_role = guild.get_role(ADMIN_ROLE_ID) if ADMIN_ROLE_ID else None

        user_ow = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True,
            add_reactions=True
        )
        staff_ow = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, attach_files=True,
            embed_links=True, add_reactions=True, manage_messages=True,
        )
        bot_ow = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, attach_files=True,
            embed_links=True, manage_channels=True, manage_messages=True, manage_permissions=True,
        )
        overwrites: dict = {guild.default_role: discord.PermissionOverwrite(view_channel=False), member: user_ow}
        if guild.me:
            overwrites[guild.me] = bot_ow
        for role in (support_role, admin_role):
            if role:
                overwrites[role] = staff_ow

        ticket_counter += 1
        number = ticket_counter
        name = build_channel_name(cat["prefix"], number, member.name)
        topic = f"Ticket #{number:04d} | Owner: {member} ({member.id}) | Category: {cat['label']}"

        try:
            channel = await guild.create_text_channel(
                name=name,
                category=get_category_channel(guild, TICKET_CATEGORY_ID),
                overwrites=overwrites,
                topic=topic[:1000],
                reason=f"Ticket #{number:04d} opened by {member}",
            )
        except discord.Forbidden:
            return None, "I don't have permission to create channels (need Manage Channels)."
        except discord.HTTPException as exc:
            return None, f"Discord refused to create the channel: {exc.text or exc}"

        welcome = format_welcome(
            category_key,
            {
                "user": member.mention,
                "category": cat["label"],
                "service": service or "-",
                "payment": payment or "-",
                "support_role": support_role.mention if support_role else "Our team",
                "number": f"{number:04d}",
            },
        )
        ticket = Ticket(
            number=number,
            channel_id=channel.id,
            guild_id=guild.id,
            owner_id=member.id,
            owner_name=str(member),
            owner_avatar=member.display_avatar.url,
            category=category_key,
            service=service,
            payment=payment,
            base_name=name,
            welcome=welcome,
            created_at=now(),
        )
        tickets[channel.id] = ticket
        STATS["created"] += 1
        CATEGORY_COUNTS[category_key] += 1

        try:
            msg = await channel.send(
                view=TicketView(ticket, ping=True),
                allowed_mentions=discord.AllowedMentions(
                    users=[discord.Object(id=member.id)],
                    roles=[discord.Object(id=SUPPORT_ROLE_ID)] if support_role else [],
                ),
            )
            ticket.panel_message_id = msg.id
        except discord.HTTPException:
            log.exception("Could not post the ticket panel in %s", channel.id)

        if cat.get("ask_payment") and FEATURES["payment_confirm_button"]:
            try:
                pay_msg = await channel.send(
                    view=PaymentConfirmView(ticket), allowed_mentions=discord.AllowedMentions.none()
                )
                ticket.payment_message_id = pay_msg.id
            except discord.HTTPException:
                log.exception("Could not post the payment message in %s", channel.id)

        await log_event(
            guild,
            "Ticket opened",
            f"**Ticket:** #{number:04d} ({channel.mention})\n**Owner:** {member.mention}\n"
            f"**Category:** {cat['label']}\n**Service:** {service or '-'}\n**Payment:** {payment or '-'}",
            "success",
        )
        return ticket, None
    finally:
        creating_users.discard(member.id)


async def refresh_panel(ticket: Ticket, channel) -> None:
    if not ticket.panel_message_id or channel is None:
        return
    view = ClosedTicketView(ticket) if ticket.status == "closed" else TicketView(ticket)
    try:
        await channel.get_partial_message(ticket.panel_message_id).edit(view=view)
    except discord.HTTPException:
        log.warning("Could not refresh the panel of ticket %s", ticket.number)


async def refresh_payment_message(ticket: Ticket, channel) -> None:
    if not ticket.payment_message_id or channel is None:
        return
    try:
        await channel.get_partial_message(ticket.payment_message_id).edit(view=PaymentConfirmView(ticket))
    except discord.HTTPException:
        log.warning("Could not refresh the payment message of ticket %s", ticket.number)


async def set_ticket_state(guild: discord.Guild, channel: discord.TextChannel, ticket: Ticket, *, closed: bool) -> None:
    overwrites = dict(channel.overwrites)
    for uid in {ticket.owner_id, *ticket.added_users}:
        member = await get_member(guild, uid)
        if not member:
            continue
        current = dict(overwrites.get(member, discord.PermissionOverwrite()))
        current.update(view_channel=True, send_messages=not closed)
        overwrites[member] = discord.PermissionOverwrite(**current)

    kwargs: dict = {"overwrites": overwrites,
                    "reason": f"Ticket #{ticket.number:04d} {'closed' if closed else 'reopened'}"}
    target_cat = get_category_channel(guild, CLOSED_TICKET_CATEGORY_ID if closed else TICKET_CATEGORY_ID)
    if target_cat and channel.category_id != target_cat.id:
        kwargs["category"] = target_cat
    if closed and FEATURES["rename_on_close"]:
        new_name = closed_channel_name(ticket)
    elif not closed:
        new_name = ticket.base_name
    else:
        new_name = channel.name
    if new_name != channel.name:
        kwargs["name"] = new_name
    await channel.edit(**kwargs)


async def build_transcript(ticket: Ticket, channel: discord.abc.Messageable) -> tuple[bytes, str, int]:
    messages = [m async for m in channel.history(limit=TRANSCRIPT_MESSAGE_LIMIT, oldest_first=True)]
    name = getattr(channel, "name", f"ticket-{ticket.number:04d}")
    ext = "html" if TRANSCRIPT_FORMAT == "html" else "txt"
    filename = f"transcript-{name}.{ext}"

    def body_of(m: discord.Message) -> str:
        parts = []
        if m.clean_content:
            parts.append(m.clean_content)
        parts.extend(component_text(m.components))
        for e in m.embeds:
            bits = [b for b in (e.title, e.description) if b]
            if bits:
                parts.append("[embed] " + " - ".join(bits))
        return "\n".join(parts)

    if ext == "txt":
        lines = [
            f"Transcript of ticket #{ticket.number:04d} ({name})",
            f"Owner: {ticket.owner_name} ({ticket.owner_id})",
            f"Generated: {now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "=" * 60,
        ]
        for m in messages:
            lines.append(f"[{m.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {m.author.display_name}: {body_of(m)}")
            for a in m.attachments:
                lines.append(f"    [attachment] {a.filename}: {a.url}")
        return "\n".join(lines).encode("utf-8"), filename, len(messages)

    rows = []
    for m in messages:
        text = html.escape(body_of(m)).replace("\n", "<br>")
        atts = "".join(
            f'<div class="att"><a href="{html.escape(a.url)}">{html.escape(a.filename)}</a></div>' for a in
            m.attachments
        )
        tag = ' <span class="bot">BOT</span>' if m.author.bot else ""
        rows.append(
            f'<div class="msg"><img src="{html.escape(m.author.display_avatar.url)}" class="av">'
            f'<div><span class="name">{html.escape(m.author.display_name)}</span>{tag} '
            f'<span class="time">{m.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}</span>'
            f'<div class="txt">{text}</div>{atts}</div></div>'
        )
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Transcript #{ticket.number:04d}</title>
<style>
body{{background:#313338;color:#dbdee1;font-family:Arial,Helvetica,sans-serif;margin:0;padding:24px}}
h1{{font-size:20px;margin:0 0 4px}} .meta{{color:#949ba4;font-size:13px;margin-bottom:20px}}
.msg{{display:flex;gap:12px;padding:8px 0}} .av{{width:40px;height:40px;border-radius:50%}}
.name{{font-weight:bold;color:#fff}} .time{{color:#949ba4;font-size:12px}}
.bot{{background:#5865f2;color:#fff;font-size:10px;padding:1px 4px;border-radius:3px}}
.txt{{margin-top:2px;line-height:1.4;word-break:break-word}} .att a{{color:#00a8fc}}
</style></head><body>
<h1>Transcript - Ticket #{ticket.number:04d} (#{html.escape(name)})</h1>
<div class="meta">Owner: {html.escape(ticket.owner_name)} ({ticket.owner_id}) - Messages: {len(messages)} -
Generated: {now().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
{''.join(rows)}
</body></html>"""
    return doc.encode("utf-8"), filename, len(messages)


async def post_transcript(guild: discord.Guild, ticket: Ticket, data: bytes, filename: str, count: int,
                          by: str) -> None:
    channel = get_text_channel(guild, TRANSCRIPT_CHANNEL_ID)
    if not channel:
        return
    try:
        await channel.send(
            view=Notice(
                f"### Transcript - Ticket #{ticket.number:04d}\n**Owner:** <@{ticket.owner_id}>\n"
                f"**Messages:** {count}\n**Generated by:** {by}",
                "info",
            ),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await channel.send(file=discord.File(io.BytesIO(data), filename=filename))
    except discord.HTTPException:
        log.warning("Could not post transcript to the transcript channel.")


async def core_close(guild, channel, ticket: Ticket, closer: discord.Member, reason: Optional[str]) -> tuple[bool, str]:
    if ticket.status != "open":
        return False, "This ticket is already closed."
    if channel is None:
        return False, "Ticket channel not found."
    ticket.status = "closed"
    ticket.closed_by = closer.id
    ticket.closed_at = now()
    ticket.close_reason = reason[:200] if reason else None
    STATS["closed"] += 1

    text = f"**Ticket closed** by {closer.mention}"
    if ticket.close_reason:
        text += f"\n**Reason:** {ticket.close_reason}"
    try:
        await channel.send(view=Notice(text, "error", banner=False), allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        pass
    await refresh_panel(ticket, channel)

    if FEATURES["auto_transcript_on_close"] or FEATURES["dm_transcript_to_owner"]:
        try:
            data, filename, count = await build_transcript(ticket, channel)
            STATS["transcripts"] += 1
            if FEATURES["auto_transcript_on_close"]:
                await post_transcript(guild, ticket, data, filename, count, closer.mention)
            if FEATURES["dm_transcript_to_owner"]:
                owner = await get_member(guild, ticket.owner_id)
                if owner:
                    try:
                        await owner.send(
                            view=Notice(f"Transcript of your ticket **#{ticket.number:04d}** ({guild.name})", "info"))
                        await owner.send(file=discord.File(io.BytesIO(data), filename=filename))
                    except discord.HTTPException:
                        pass
        except discord.HTTPException:
            log.warning("Transcript generation failed for ticket %s", ticket.number)

    warning = ""
    try:
        await set_ticket_state(guild, channel, ticket, closed=True)
    except discord.Forbidden:
        warning = " (Could not lock/move the channel - missing permissions.)"
    except discord.HTTPException as exc:
        warning = f" (Channel update failed: {exc.text or exc})"

    await log_event(
        guild,
        "Ticket closed",
        f"**Ticket:** #{ticket.number:04d} ({channel.mention})\n**Owner:** <@{ticket.owner_id}>\n"
        f"**Closed by:** {closer.mention}\n**Reason:** {ticket.close_reason or '-'}",
        "error",
    )
    return True, "Ticket closed." + warning


async def core_reopen(guild, channel, ticket: Ticket, member: discord.Member) -> tuple[bool, str]:
    if ticket.status != "closed":
        return False, "This ticket is not closed."
    if channel is None:
        return False, "Ticket channel not found."
    owner = await get_member(guild, ticket.owner_id)
    if not owner:
        return False, "The ticket owner is no longer in the server."
    ticket.status = "open"
    ticket.closed_by = None
    ticket.closed_at = None
    ticket.close_reason = None
    ticket.last_activity = now()
    ticket.close_request_sent = False
    STATS["reopened"] += 1

    warning = ""
    try:
        await set_ticket_state(guild, channel, ticket, closed=False)
    except discord.Forbidden:
        warning = " (Could not unlock/move the channel - missing permissions.)"
    except discord.HTTPException as exc:
        warning = f" (Channel update failed: {exc.text or exc})"

    await refresh_panel(ticket, channel)
    try:
        await channel.send(
            view=Notice(f"**Ticket reopened** by {member.mention}\n{owner.mention}, you can write here again.",
                        "success"),
            allowed_mentions=discord.AllowedMentions(users=[discord.Object(id=owner.id)]),
        )
    except discord.HTTPException:
        pass
    await log_event(
        guild, "Ticket reopened",
        f"**Ticket:** #{ticket.number:04d} ({channel.mention})\n**Reopened by:** {member.mention}", "success"
    )
    return True, "Ticket reopened." + warning


async def core_claim(guild, channel, ticket: Ticket, member: discord.Member, mode: str = "toggle") -> tuple[bool, str]:
    if ticket.status != "open":
        return False, "Only open tickets can be claimed."
    if mode == "unclaim" or (mode == "toggle" and ticket.claimed_by == member.id):
        if ticket.claimed_by is None:
            return False, "This ticket is not claimed."
        if ticket.claimed_by != member.id and not is_admin(member):
            return False, f"Only <@{ticket.claimed_by}> or an admin can unclaim this ticket."
        ticket.claimed_by = None
        msg, kind, title = f"{member.mention} released this ticket.", "info", "Ticket unclaimed"
    else:
        if ticket.claimed_by and ticket.claimed_by != member.id and not is_admin(member):
            return False, f"This ticket is already claimed by <@{ticket.claimed_by}>."
        ticket.claimed_by = member.id
        CLAIMS_BY_STAFF[member.id] += 1
        msg, kind, title = f"{member.mention} claimed this ticket and will assist you.", "success", "Ticket claimed"
    await refresh_panel(ticket, channel)
    try:
        await channel.send(view=Notice(msg, kind, banner=False), allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        pass
    await log_event(guild, f"{title}",
                    f"**Ticket:** #{ticket.number:04d} ({channel.mention})\n**Staff:** {member.mention}", kind)
    return True, title + "."


async def reset_panel_select(interaction: discord.Interaction) -> None:
    try:
        if interaction.message:
            await interaction.message.edit(view=PanelView())
    except discord.HTTPException:
        pass


async def on_panel_select(interaction: discord.Interaction, select: discord.ui.Select) -> None:
    guild = interaction.guild
    member = interaction.user
    key = select.values[0]
    if guild is None or guild.id != GUILD_ID or not isinstance(member, discord.Member):
        await say(interaction, "This panel only works in the configured server.", "error")
        return
    if key not in TICKET_CATEGORIES:
        await say(interaction, "Unknown category.", "error")
        return
    if count_open(member.id) >= MAX_TICKETS_PER_USER:
        await say(interaction, f"You already have {MAX_TICKETS_PER_USER} open ticket(s). Please close one first.",
                  "error")
        await reset_panel_select(interaction)
        return

    cat = TICKET_CATEGORIES[key]
    needs_steps = bool((cat.get("ask_service") and SERVICES) or (cat.get("ask_payment") and PAYMENT_METHODS))
    if needs_steps:
        await interaction.response.send_message(view=CreateWizard(key), ephemeral=True)
    else:
        await ack(interaction)
        ticket, error = await open_ticket(guild, member, key, None, None)
        if error or not ticket:
            await say(interaction, f"{error}", "error")
        else:
            await say(interaction, f"Your ticket has been created: <#{ticket.channel_id}>", "success")
    await reset_panel_select(interaction)


async def handle_close_button(interaction: discord.Interaction) -> None:
    got = await ctx(interaction, "close")
    if not got:
        return
    ticket, member = got
    if ticket.status != "open":
        await say(interaction, "This ticket is already closed.", "error")
        return
    if FEATURES["confirm_close"]:
        await interaction.response.send_message(view=ConfirmCloseView(ticket.channel_id), ephemeral=True)
        return
    await ack(interaction)
    ok, text = await core_close(interaction.guild, interaction.guild.get_channel(ticket.channel_id), ticket, member,
                                None)
    await say(interaction, text, "success" if ok else "error")


async def handle_transcript(interaction: discord.Interaction) -> None:
    got = await ctx(interaction, "transcript")
    if not got:
        return
    ticket, member = got
    await ack(interaction)
    channel = interaction.guild.get_channel(ticket.channel_id) or interaction.channel
    try:
        data, filename, count = await build_transcript(ticket, channel)
    except discord.HTTPException as exc:
        await say(interaction, f"Could not read the channel history: {exc.text or exc}", "error")
        return
    STATS["transcripts"] += 1
    await post_transcript(interaction.guild, ticket, data, filename, count, member.mention)
    await interaction.followup.send(view=Notice(f"Transcript generated ({count} messages).", "success", banner=False),
                                    ephemeral=True)
    await interaction.followup.send(file=discord.File(io.BytesIO(data), filename=filename), ephemeral=True)
    await log_event(
        interaction.guild, "Transcript generated",
        f"**Ticket:** #{ticket.number:04d}\n**By:** {member.mention}\n**Messages:** {count}"
    )


async def handle_claim(interaction: discord.Interaction) -> None:
    got = await ctx(interaction, "claim")
    if not got:
        return
    ticket, member = got
    await ack(interaction)
    ok, text = await core_claim(interaction.guild, interaction.guild.get_channel(ticket.channel_id), ticket, member)
    await say(interaction, text, "success" if ok else "error")


async def do_notify(interaction: discord.Interaction, ticket: Ticket, member: discord.Member) -> tuple[bool, str]:
    if ticket.status != "open":
        return False, "Only open tickets can send notifications."
    last = notify_cooldowns.get(ticket.channel_id, 0.0)
    elapsed = asyncio.get_running_loop().time() - last
    if elapsed < NOTIFY_COOLDOWN_SECONDS:
        return False, f"Please wait {int(NOTIFY_COOLDOWN_SECONDS - elapsed)}s before notifying again."
    notify_cooldowns[ticket.channel_id] = asyncio.get_running_loop().time()

    channel = interaction.guild.get_channel(ticket.channel_id) or interaction.channel
    if is_staff(member) and member.id != ticket.owner_id:
        text = f"<@{ticket.owner_id}>, {member.mention} is waiting for your reply."
        mentions = discord.AllowedMentions(users=[discord.Object(id=ticket.owner_id)])
    else:
        mention, mentions = staff_mention(ticket)
        text = f"{mention}, {member.mention} needs assistance."
    await channel.send(view=Notice(text, "warn", banner=False), allowed_mentions=mentions)
    return True, "Notification sent."


async def handle_notify(interaction: discord.Interaction) -> None:
    got = await ctx(interaction, "notify")
    if not got:
        return
    ticket, member = got
    await ack(interaction)
    ok, text = await do_notify(interaction, ticket, member)
    await say(interaction, text, "success" if ok else "error")


async def handle_payment_info(interaction: discord.Interaction) -> None:
    got = await ctx(interaction, "payment")
    if not got:
        return
    ticket, member = got
    if ticket.status != "open":
        await say(interaction, "This ticket is closed.", "error")
        return
    if not PAYMENT_DETAILS:
        await say(interaction, "No payment details are configured.", "error")
        return
    await interaction.response.send_message(
        view=PaymentInfoView(ticket), ephemeral=not FEATURES["payment_info_public"]
    )


async def handle_payment_confirm(interaction: discord.Interaction) -> None:
    got = await ctx(interaction, "payment_confirm")
    if not got:
        return
    ticket, member = got
    if ticket.status != "open":
        await say(interaction, "This ticket is closed.", "error")
        return
    if ticket.payment_status == "verified":
        await say(interaction, "The payment of this ticket is already confirmed.", "info")
        return
    await ack(interaction)
    guild = interaction.guild
    channel = guild.get_channel(ticket.channel_id) or interaction.channel
    ticket.payment_status = "verified"
    ticket.payment_verified_by = member.id
    ticket.payment_confirmed_at = now()
    await refresh_payment_message(ticket, channel)
    await refresh_panel(ticket, channel)
    try:
        await channel.send(
            view=Notice(
                f"Payment confirmed by {member.mention}. <@{ticket.owner_id}>, thank you for your payment!",
                "success",
                banner=False,
            ),
            allowed_mentions=discord.AllowedMentions(users=[discord.Object(id=ticket.owner_id)]),
        )
    except discord.HTTPException:
        pass
    await log_event(
        guild, "Payment confirmed",
        f"**Ticket:** #{ticket.number:04d} ({channel.mention})\n**Method:** {ticket.payment or '-'}\n"
        f"**Confirmed by:** {member.mention}",
        "success",
    )
    await say(interaction, "Payment confirmed.", "success")


async def handle_request_close(interaction: discord.Interaction) -> None:
    got = await ctx(interaction, "close")
    if not got:
        return
    ticket, member = got
    if ticket.status != "open":
        await say(interaction, "This ticket is already closed.", "error")
        return
    await ack(interaction)
    guild = interaction.guild
    ok, text = await core_close(guild, guild.get_channel(ticket.channel_id), ticket, member,
                                "Closed after inactivity close request")
    if ok:
        try:
            await interaction.message.edit(
                view=Notice(f"Close request accepted by {member.mention}.", "success", banner=False),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            pass
    await say(interaction, text, "success" if ok else "error")


async def handle_request_keep(interaction: discord.Interaction) -> None:
    got = await ctx(interaction, "notify")
    if not got:
        return
    ticket, member = got
    if ticket.status != "open":
        await say(interaction, "This ticket is already closed.", "error")
        return
    ticket.last_activity = now()
    ticket.close_request_sent = False
    await interaction.response.edit_message(
        view=Notice(f"{member.mention} chose to keep this ticket open. The inactivity timer was reset.", "success",
                    banner=False),
        allowed_mentions=discord.AllowedMentions.none(),
    )


async def handle_reopen(interaction: discord.Interaction) -> None:
    got = await ctx(interaction, "reopen")
    if not got:
        return
    ticket, member = got
    await ack(interaction)
    ok, text = await core_reopen(interaction.guild, interaction.guild.get_channel(ticket.channel_id), ticket, member)
    await say(interaction, text, "success" if ok else "error")


async def handle_delete(interaction: discord.Interaction) -> None:
    got = await ctx(interaction, "delete")
    if not got:
        return
    ticket, member = got
    if ticket.status != "closed":
        await say(interaction, "Only closed tickets can be deleted.", "error")
        return
    await ack(interaction)
    channel = interaction.guild.get_channel(ticket.channel_id)
    if channel is None:
        await say(interaction, "Channel not found.", "error")
        return
    await say(interaction, f"Deleting in {DELETE_DELAY_SECONDS}s...", "warn")
    try:
        await channel.send(
            view=Notice(f"This ticket will be deleted in {DELETE_DELAY_SECONDS} seconds by {member.mention}.", "warn"),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException:
        pass
    await asyncio.sleep(DELETE_DELAY_SECONDS)
    tickets.pop(ticket.channel_id, None)
    STATS["deleted"] += 1
    try:
        await channel.delete(reason=f"Ticket #{ticket.number:04d} deleted by {member}")
    except discord.HTTPException as exc:
        tickets[ticket.channel_id] = ticket
        STATS["deleted"] -= 1
        await say(interaction, f"Could not delete the channel: {exc.text or exc}", "error")
        return
    await log_event(
        interaction.guild, "Ticket deleted",
        f"**Ticket:** #{ticket.number:04d}\n**Owner:** <@{ticket.owner_id}>\n**Deleted by:** {member.mention}", "error"
    )


class TicketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)

    async def setup_hook(self) -> None:
        self.add_view(PanelView())
        self.add_view(TicketView(None))
        self.add_view(ClosedTicketView(None))
        self.add_view(CloseRequestView(None))
        self.add_view(PaymentConfirmView(None))
        guild = discord.Object(id=GUILD_ID)
        self.tree.add_command(ticket_group, guild=guild)
        await self.tree.sync(guild=guild)
        self.inactivity_loop.start()

    async def on_ready(self) -> None:
        global _panel_boot_done
        log.info("Logged in as %s (%s) | discord.py %s", self.user, getattr(self.user, "id", "?"), discord.__version__)
        guild = self.get_guild(GUILD_ID)
        if guild is None:
            log.error("The bot is not in the guild with GUILD_ID=%s.", GUILD_ID)
            return
        if FEATURES["auto_post_panel"] and not _panel_boot_done:
            _panel_boot_done = True
            ok, text = await post_panel(guild)
            log.info("Auto panel: %s", text)

    async def on_message(self, message: discord.Message) -> None:
        if message.guild and not message.author.bot:
            ticket = tickets.get(message.channel.id)
            if ticket and ticket.status == "open":
                ticket.last_activity = now()
                ticket.close_request_sent = False
        await self.process_commands(message)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        ticket = tickets.pop(channel.id, None)
        if ticket:
            await log_event(
                channel.guild,
                "Ticket channel deleted manually",
                f"**Ticket:** #{ticket.number:04d}\n**Owner:** <@{ticket.owner_id}>",
                "warn",
            )

    @tasks.loop(seconds=INACTIVITY_CHECK_INTERVAL_SECONDS)
    async def inactivity_loop(self) -> None:
        if not FEATURES["inactivity_close_request"]:
            return
        guild = self.get_guild(GUILD_ID)
        if guild is None:
            return
        limit = timedelta(hours=INACTIVITY_HOURS)
        for ticket in list(tickets.values()):
            if ticket.status != "open" or ticket.close_request_sent:
                continue
            if now() - ticket.last_activity < limit:
                continue
            channel = guild.get_channel(ticket.channel_id)
            if channel is None:
                continue
            ticket.close_request_sent = True
            try:
                await channel.send(
                    view=CloseRequestView(ticket),
                    allowed_mentions=discord.AllowedMentions(users=[discord.Object(id=ticket.owner_id)]),
                )
            except discord.HTTPException:
                ticket.close_request_sent = False
                continue
            except Exception:
                log.exception("Inactivity check failed for ticket %s", ticket.number)
                continue
            await log_event(
                guild, "Close request sent",
                f"**Ticket:** #{ticket.number:04d} ({channel.mention})\n"
                f"**Reason:** No activity for {INACTIVITY_HOURS} hours",
                "warn",
            )

    @inactivity_loop.before_loop
    async def _before_inactivity_loop(self) -> None:
        await self.wait_until_ready()


bot = TicketBot()
ticket_group = app_commands.Group(name=SLASH_GROUP_NAME, description="Ticket management", guild_only=True)


@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    log.error("Command error: %s", "".join(traceback.format_exception(type(error), error, error.__traceback__)))
    try:
        await say(interaction, "An unexpected error occurred while running that command.", "error")
    except discord.HTTPException:
        pass


async def post_panel(guild: discord.Guild) -> tuple[bool, str]:
    channel = get_text_channel(guild, PANEL_CHANNEL_ID)
    if not channel:
        return False, "PANEL_CHANNEL_ID is not set or is not a text channel."
    try:
        async for m in channel.history(limit=30):
            if bot.user and m.author.id == bot.user.id and PANEL_TITLE in "\n".join(component_text(m.components)):
                await m.edit(view=PanelView())
                return True, f"Existing panel updated in {channel.mention}."
        await channel.send(view=PanelView())
    except discord.Forbidden:
        return False, f"I lack permission to post in {channel.mention}."
    except discord.HTTPException as exc:
        return False, f"Could not post the panel: {exc.text or exc}"
    return True, f"Panel posted in {channel.mention}."


@ticket_group.command(name="panel", description="Post (or update) the ticket panel in the panel channel")
async def cmd_panel(interaction: discord.Interaction):
    member = interaction.user
    if not isinstance(member, discord.Member) or not is_admin(member):
        await say(interaction, "Only admins can do that.", "error")
        return
    await ack(interaction)
    ok, text = await post_panel(interaction.guild)
    await say(interaction, text, "success" if ok else "error")


@ticket_group.command(name="close", description="Close this ticket")
@app_commands.describe(reason="Optional reason for closing")
async def cmd_close(interaction: discord.Interaction, reason: Optional[str] = None):
    got = await ctx(interaction, "close")
    if not got:
        return
    ticket, member = got
    await ack(interaction)
    ok, text = await core_close(interaction.guild, interaction.guild.get_channel(ticket.channel_id), ticket, member,
                                reason)
    await say(interaction, text, "success" if ok else "error")


@ticket_group.command(name="reopen", description="Reopen a closed ticket")
async def cmd_reopen(interaction: discord.Interaction):
    await handle_reopen(interaction)


@ticket_group.command(name="claim", description="Claim this ticket")
async def cmd_claim(interaction: discord.Interaction):
    got = await ctx(interaction, "claim")
    if not got:
        return
    ticket, member = got
    await ack(interaction)
    ok, text = await core_claim(interaction.guild, interaction.guild.get_channel(ticket.channel_id), ticket, member,
                                "claim")
    await say(interaction, text, "success" if ok else "error")


@ticket_group.command(name="unclaim", description="Release this ticket")
async def cmd_unclaim(interaction: discord.Interaction):
    got = await ctx(interaction, "claim")
    if not got:
        return
    ticket, member = got
    await ack(interaction)
    ok, text = await core_claim(interaction.guild, interaction.guild.get_channel(ticket.channel_id), ticket, member,
                                "unclaim")
    await say(interaction, text, "success" if ok else "error")


@ticket_group.command(name="notify", description="Ping the responsible party of this ticket")
async def cmd_notify(interaction: discord.Interaction):
    await handle_notify(interaction)


@ticket_group.command(name="transcript", description="Generate a transcript of this ticket")
async def cmd_transcript(interaction: discord.Interaction):
    await handle_transcript(interaction)


@ticket_group.command(name="paymentinfo", description="Show the payment details")
async def cmd_paymentinfo(interaction: discord.Interaction):
    await handle_payment_info(interaction)


@ticket_group.command(name="add", description="Add a user to this ticket")
@app_commands.describe(user="The user to add")
async def cmd_add(interaction: discord.Interaction, user: discord.Member):
    got = await ctx(interaction, "add")
    if not got:
        return
    ticket, member = got
    await ack(interaction)
    channel = interaction.guild.get_channel(ticket.channel_id)
    if user.bot:
        await say(interaction, "Bots can't be added to tickets.", "error")
        return
    if user.id == ticket.owner_id or user.id in ticket.added_users or is_staff(user):
        await say(interaction, f"{user.mention} already has access to this ticket.", "error")
        return
    try:
        await channel.set_permissions(
            user,
            overwrite=discord.PermissionOverwrite(
                view_channel=True, send_messages=(ticket.status == "open"), read_message_history=True,
                attach_files=True, embed_links=True
            ),
            reason=f"Added to ticket #{ticket.number:04d} by {member}",
        )
    except discord.HTTPException as exc:
        await say(interaction, f"Could not update permissions: {exc.text or exc}", "error")
        return
    ticket.added_users.add(user.id)
    await refresh_panel(ticket, channel)
    await channel.send(
        view=Notice(f"{user.mention} was added to this ticket by {member.mention}.", "success"),
        allowed_mentions=discord.AllowedMentions(users=[discord.Object(id=user.id)]),
    )
    await log_event(interaction.guild, "User added",
                    f"**Ticket:** #{ticket.number:04d}\n**User:** {user.mention}\n**By:** {member.mention}")
    await say(interaction, f"Added {user.mention}.", "success")


@ticket_group.command(name="remove", description="Remove a user from this ticket")
@app_commands.describe(user="The user to remove")
async def cmd_remove(interaction: discord.Interaction, user: discord.Member):
    got = await ctx(interaction, "remove")
    if not got:
        return
    ticket, member = got
    await ack(interaction)
    channel = interaction.guild.get_channel(ticket.channel_id)
    if user.id == ticket.owner_id:
        await say(interaction, "You can't remove the ticket owner.", "error")
        return
    if user.id not in ticket.added_users:
        await say(interaction, f"{user.mention} was not added to this ticket.", "error")
        return
    try:
        await channel.set_permissions(user, overwrite=None,
                                      reason=f"Removed from ticket #{ticket.number:04d} by {member}")
    except discord.HTTPException as exc:
        await say(interaction, f"Could not update permissions: {exc.text or exc}", "error")
        return
    ticket.added_users.discard(user.id)
    await refresh_panel(ticket, channel)
    await channel.send(
        view=Notice(f"{user.mention} was removed from this ticket by {member.mention}.", "warn"),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    await log_event(interaction.guild, "User removed",
                    f"**Ticket:** #{ticket.number:04d}\n**User:** {user.mention}\n**By:** {member.mention}", "warn")
    await say(interaction, f"Removed {user.mention}.", "success")


@ticket_group.command(name="rename", description="Rename this ticket channel")
@app_commands.describe(name="New channel name")
async def cmd_rename(interaction: discord.Interaction, name: app_commands.Range[str, 1, 90]):
    got = await ctx(interaction, "rename")
    if not got:
        return
    ticket, member = got
    await ack(interaction)
    channel = interaction.guild.get_channel(ticket.channel_id)
    new_name = sanitize_channel_name(name)
    old_name = ticket.base_name
    ticket.base_name = new_name
    try:
        if ticket.status == "open":
            await channel.edit(name=new_name, reason=f"Renamed by {member}")
    except discord.HTTPException as exc:
        ticket.base_name = old_name
        await say(interaction, f"Could not rename: {exc.text or exc}", "error")
        return
    await log_event(interaction.guild, "Ticket renamed",
                    f"**Ticket:** #{ticket.number:04d}\n**New name:** `{new_name}`\n**By:** {member.mention}")
    note = "" if ticket.status == "open" else " (applied when the ticket is reopened)"
    await say(interaction, f"Renamed to `{new_name}`{note}.", "success")


@ticket_group.command(name="stats", description="Show ticket statistics")
async def cmd_stats(interaction: discord.Interaction):
    member = interaction.user
    if interaction.guild is None or not isinstance(member, discord.Member) or not is_staff(member):
        await say(interaction, "Only staff can view statistics.", "error")
        return
    all_t = list(tickets.values())
    open_t = [t for t in all_t if t.status == "open"]
    closed_t = [t for t in all_t if t.status == "closed"]
    claimed = [t for t in open_t if t.claimed_by]
    durations = [(t.closed_at - t.created_at).total_seconds() for t in closed_t if t.closed_at]
    avg = format_duration(sum(durations) / len(durations)) if durations else "-"

    cat_lines = [
                    f"{TICKET_CATEGORIES[k]['label']}: **{v}**"
                    for k, v in CATEGORY_COUNTS.most_common()
                    if k in TICKET_CATEGORIES
                ] or ["-"]
    staff_lines = [f"<@{uid}>: **{n}** claims" for uid, n in CLAIMS_BY_STAFF.most_common(5)] or ["-"]

    text = (
        "# Ticket Statistics\n"
        f"**Created (since start):** {STATS['created']}\n"
        f"**Currently open:** {len(open_t)} (claimed: {len(claimed)}, unclaimed: {len(open_t) - len(claimed)})\n"
        f"**Currently closed:** {len(closed_t)}\n"
        f"**Closed total / Reopened / Deleted:** {STATS['closed']} / {STATS['reopened']} / {STATS['deleted']}\n"
        f"**Transcripts generated:** {STATS['transcripts']}\n"
        f"**Avg. ticket lifetime (closed):** {avg}"
    )
    container = discord.ui.Container(accent_colour=KIND_COLORS["info"])
    container.add_item(discord.ui.TextDisplay(text))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay("### By category\n" + "\n".join(cat_lines)))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay("### Top staff\n" + "\n".join(staff_lines)))
    container.add_item(discord.ui.TextDisplay("-# Statistics are in-memory and reset when the bot restarts."))
    add_banner(container)
    view = BaseLayout(timeout=None)
    view.add_item(container)
    await interaction.response.send_message(view=view, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


def validate_config() -> None:
    problems = []
    if not GUILD_ID:
        problems.append("GUILD_ID is not set (required).")
    for label, value in (
            ("PANEL_CHANNEL_ID", PANEL_CHANNEL_ID),
            ("TICKET_CATEGORY_ID", TICKET_CATEGORY_ID),
            ("CLOSED_TICKET_CATEGORY_ID", CLOSED_TICKET_CATEGORY_ID),
            ("SUPPORT_ROLE_ID", SUPPORT_ROLE_ID),
            ("ADMIN_ROLE_ID", ADMIN_ROLE_ID),
            ("LOG_CHANNEL_ID", LOG_CHANNEL_ID),
            ("TRANSCRIPT_CHANNEL_ID", TRANSCRIPT_CHANNEL_ID),
    ):
        if not value:
            log.warning("%s is not set - the related feature will be skipped.", label)
    if not TICKET_CATEGORIES:
        problems.append("TICKET_CATEGORIES is empty.")
    if len(TICKET_CATEGORIES) > 25:
        problems.append("A select menu supports at most 25 categories.")
    if problems:
        raise SystemExit("Configuration error:\n - " + "\n - ".join(problems))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    validate_config()

    token = os.getenv("DISCORD_TOKEN")

    if not token:
        raise SystemExit("DISCORD_TOKEN fehlt in Railway!")

    bot.run(token.strip(), log_handler=None)


if __name__ == "__main__":
    main()

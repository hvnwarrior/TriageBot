"""Slack adapter: connects the TriageBot assistant to a Slack workspace.

Employees @mention the bot (or DM it) in Slack; the adapter forwards the
message to the same support-assistant service the web demo uses, and
posts the reply back in the thread. Triage tiers surface as Slack
block-kit attachments instead of web badges.

Setup:
    1. Create a Slack app with Socket Mode enabled (no public URL
       needed — outbound WebSocket connection only, friendlier to
       homelab/network setups).
    2. Bot token scopes: chat:write, app_mentions:read, im:history.
    3. Event subscriptions: app_mention, message.im.
    4. Put SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env.
    5. Run:  python -m app.adapters.slack_adapter

Security escalation posts additionally to SLACK_SECURITY_CHANNEL_ID so
incidents surface where security lives, mirroring the writeup design.
"""

import os

from app.dependencies import initialize_services
from fastapi import FastAPI


def main() -> None:
    # Imported here so the adapter can run without slack_bolt installed
    # until first use, and so dependency errors are clear and local.
    try:
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler
    except ImportError as error:
        raise SystemExit(
            "Slack adapter requires slack_bolt. Install it with:\n"
            "    pip install slack-bolt slack-sdk\n"
            f"(ImportError: {error})"
        )

    from app.config import get_settings

    settings = get_settings()

    slack_bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    slack_app_token = os.environ.get("SLACK_APP_TOKEN", "")
    security_channel_id = os.environ.get("SLACK_SECURITY_CHANNEL_ID", "")

    if not slack_bot_token or not slack_app_token:
        raise SystemExit(
            "Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in the environment "
            "(or .env) before starting the Slack adapter."
        )

    # The FastAPI app is only used as the service container.
    app = FastAPI()
    assistant, takeover = initialize_services(app)

    slack_app = App(token=slack_bot_token)

    # Slack thread_ts <-> assistant conversation_id mapping.
    thread_map: dict[tuple[str, str], int] = {}

    TIER_ATTACHMENTS = {
        "security": {
            "color": "#ff6b6b",
            "fields": [
                {
                    "title": "Routing",
                    "value": "Security escalation - human notified immediately",
                    "short": True,
                },
            ],
        },
        "self_serve": {
            "color": "#65d48a",
            "fields": [
                {
                    "title": "Routing",
                    "value": "Self-serve from the knowledge base",
                    "short": True,
                },
            ],
        },
        "assisted": {
            "color": "#7c8cff",
            "fields": [
                {
                    "title": "Routing",
                    "value": "Assisted troubleshooting",
                    "short": True,
                },
            ],
        },
    }

    def handle_it_request(
        say,
        text: str,
        channel_id: str,
        thread_ts: str | None,
        user_name: str,
    ) -> None:
        key = (channel_id, thread_ts or "")

        conversation_id = thread_map.get(key)

        result = assistant.handle_employee_message(
            message=text,
            conversation_id=conversation_id,
            employee_name=user_name,
        )

        thread_map[key] = result["conversation_id"]

        attachments = []

        tier = result.get("tier")

        if tier in TIER_ATTACHMENTS:
            attachments.append(dict(TIER_ATTACHMENTS[tier]))

        ticket_id = result.get("ticket_id")

        if ticket_id is not None:
            attachments.append(
                {
                    "color": "#9aa1ad",
                    "fields": [
                        {
                            "title": "Ticket",
                            "value": f"#{ticket_id} created for tracking",
                            "short": True,
                        },
                    ],
                }
            )

        say(
            text=result.get("reply") or "",
            thread_ts=thread_ts,
            attachments=attachments,
        )

        # Security tier: also ping the security channel, P1 style.
        if tier == "security" and security_channel_id:
            slack_app.client.chat_postMessage(
                channel=security_channel_id,
                text=(
                    ":rotating_light: *Possible security incident* from "
                    f"<@{user_name}>: {result.get('reply', '')}"
                ),
            )

    @slack_app.event("app_mention")
    def on_app_mention(event, say) -> None:
        user_name = event.get("user", "unknown-user")
        text = event.get("text", "").strip()

        # Strip the bot mention itself from the message.
        for token in text.split():
            if token.startswith("<@") and token.endswith(">"):
                text = text.replace(token, "").strip()

        if not text:
            say(
                "Hi! Describe your IT problem and I'll help.",
                thread_ts=event.get("ts"),
            )
            return

        handle_it_request(
            say=say,
            text=text,
            channel_id=event["channel"],
            thread_ts=event.get("thread_ts") or event.get("ts"),
            user_name=user_name,
        )

    @slack_app.event("message")
    def on_direct_message(event, say) -> None:
        # Only handle DMs to the bot (im:history), not other channels.
        if event.get("channel_type") != "im":
            return

        if event.get("subtype") is not None:
            return

        handle_it_request(
            say=say,
            text=event.get("text", "").strip(),
            channel_id=event["channel"],
            thread_ts=event.get("thread_ts") or event.get("ts"),
            user_name=event.get("user", "unknown-user"),
        )

    print("Starting TriageBot Slack adapter (Socket Mode)...")
    SocketModeHandler(slack_app, slack_app_token).start()


if __name__ == "__main__":
    main()

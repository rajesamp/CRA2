"""Single-workspace Slack Socket Mode entry point; no public HTTP server."""

import argparse
import logging
import os
import queue
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from cra2.secrets import configure_sdk_logging
from week2.slack_engine import Session, SlackEngine
from week2.slack_ui import (GENERAL, SERVICE_ACTION, QUESTION_ACTION, VIEW_CALLBACK,
                           answer_payload, modal_question, picker, question_modal)

BUSY = "CRA2 is busy. Please try again shortly."
UNAVAILABLE = "The request could not be completed. Please start again with /cra."


class ConfigurationError(ValueError):
    pass


def valid_id(value, prefixes):
    return isinstance(value, str) and bool(re.fullmatch("[" + prefixes + r"][A-Z0-9]{8,32}", value))


def safe_response_url(value):
    if not isinstance(value, str) or len(value) > 1000:
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and parsed.hostname == "hooks.slack.com"
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and not parsed.fragment and not parsed.query
                and parsed.path.startswith(("/commands/", "/actions/")))
    except ValueError:
        return False


@dataclass(frozen=True)
class Settings:
    team: str
    channel: str
    bot_token: str = field(repr=False)
    app_token: str = field(repr=False)

    def __post_init__(self):
        if (not valid_id(self.team, "T") or not valid_id(self.channel, "C")
                or not isinstance(self.bot_token, str) or not self.bot_token.startswith("xoxb-")
                or not isinstance(self.app_token, str) or not self.app_token.startswith("xapp-")
                or not 20 <= len(self.bot_token) <= 500 or not 20 <= len(self.app_token) <= 500
                or any(c.isspace() for c in self.bot_token + self.app_token)):
            raise ConfigurationError("Slack configuration is incomplete or invalid.")

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("CRA2_SLACK_TEAM_ID", ""), os.environ.get("CRA2_SLACK_CHANNEL_ID", ""),
                   os.environ.get("SLACK_BOT_TOKEN", ""), os.environ.get("SLACK_APP_TOKEN", ""))


@dataclass(frozen=True)
class Origin:
    team: str
    user: str
    channel: str
    thread: str = ""
    response_url: str = field(default="", repr=False)

    def __post_init__(self):
        if (not valid_id(self.team, "T") or not valid_id(self.user, "UW") or not valid_id(self.channel, "CGD")
                or not isinstance(self.thread, str) or (self.thread and not re.fullmatch(r"\d{10,20}\.\d{6}", self.thread))
                or (self.response_url and not safe_response_url(self.response_url))):
            raise ValueError("Invalid request origin")

    @property
    def session_key(self):
        return self.team, self.user, self.channel, self.thread or "slash"


class Adapter:
    """Bounded single-worker queue, retry deduplication and server-only context."""

    def __init__(self, settings, send, *, engine=None, clock=time.monotonic):
        self.settings, self.send, self.clock = settings, send, clock
        self.engine = engine if engine is not None else SlackEngine((settings.bot_token, settings.app_token))
        self.pending = queue.Queue(maxsize=16)
        self.contexts, self.seen, self.sessions = {}, {}, {}
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.worker = None

    def context(self, origin):
        if origin.team != self.settings.team:
            raise ValueError("Workspace unavailable")
        with self.lock:
            now = self.clock()
            self.contexts = {key: value for key, value in self.contexts.items() if value[0] > now}
            if len(self.contexts) >= 128:
                raise ValueError("Context capacity unavailable")
            token = secrets.token_urlsafe(24)
            self.contexts[token] = (now + 900, origin)
            return token

    def resolve(self, token, team, user, *, consume=False):
        if not isinstance(token, str) or len(token) > 100:
            return None
        with self.lock:
            found = self.contexts.get(token)
            if not found or found[0] <= self.clock() or (team, user) != (found[1].team, found[1].user):
                return None
            if consume:
                self.contexts.pop(token)
            return found[1]

    def submit(self, identity, origin, question, service=GENERAL):
        if origin.team != self.settings.team or not isinstance(identity, str) or not 1 <= len(identity) <= 150:
            return False
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 4000:
            self.send(origin, "Enter one question of up to 4000 characters.")
            return False
        with self.lock:
            now = self.clock()
            self.seen = {key: expiry for key, expiry in self.seen.items() if expiry > now}
            if identity in self.seen:
                return False
            busy = len(self.seen) >= 2048 or self.pending.full()
            if not busy:
                self.seen[identity] = now + 600
                self.pending.put_nowait((now, origin, question, service))
        # Slack delivery may block on the network; never hold the context lock
        # while sending, or another slash command could miss its ack deadline.
        if busy:
            self.send(origin, BUSY)
        return not busy

    def run_next(self, timeout=0):
        try:
            queued, origin, question, service = self.pending.get(timeout=timeout)
        except queue.Empty:
            return False
        try:
            now = self.clock()
            if now - queued > 120:
                self.send(origin, BUSY)
                return True
            self.sessions = {key: value for key, value in self.sessions.items() if now - value[0] < 3600}
            if origin.session_key not in self.sessions and len(self.sessions) >= 32:
                self.send(origin, BUSY)
                return True
            session = self.sessions.get(origin.session_key, (now, Session()))[1]
            self.sessions[origin.session_key] = (now, session)
            try:
                answer = self.engine.ask(origin, question, service, session)
            except Exception:
                answer = UNAVAILABLE
            self.send(origin, answer)
        except Exception:
            # Never retry an assessment automatically after an uncertain send.
            # SDK errors/payloads are not rendered, logged or echoed to Slack.
            pass
        finally:
            self.pending.task_done()
        return True

    def start(self):
        def work():
            while not self.stop.is_set():
                self.run_next(timeout=.2)
        self.worker = threading.Thread(target=work, name="cra2-slack-worker", daemon=True)
        self.worker.start()

    def close(self):
        self.stop.set()
        if self.worker:
            self.worker.join(timeout=1)


def quiet_logger():
    configure_sdk_logging()
    for name in list(logging.Logger.manager.loggerDict) + ["slack_sdk", "slack_bolt", "cra2.slack"]:
        if name.startswith(("slack_sdk", "slack_bolt", "cra2.slack")):
            logger = logging.getLogger(name)
            logger.disabled, logger.propagate = True, False
            logger.setLevel(logging.CRITICAL + 1)
            logger.addHandler(logging.NullHandler())
    return logging.getLogger("cra2.slack")


def create_app(settings, *, client=None, engine=None, send=None):
    from slack_bolt import App
    from slack_bolt.authorization import AuthorizeResult
    from slack_sdk import WebClient
    from slack_sdk.webhook import WebhookClient

    logger = quiet_logger()
    client = client if client is not None else WebClient(token=settings.bot_token, timeout=3, retry_handlers=[], logger=logger)
    identity = client.auth_test()
    if not identity.get("ok") or identity.get("team_id") != settings.team or not valid_id(identity.get("user_id"), "UW"):
        raise ConfigurationError("Slack identity does not match the configured workspace.")

    def authorize(team_id, **_kwargs):
        if team_id != settings.team:
            return None
        return AuthorizeResult(enterprise_id=None, team_id=team_id, bot_token=settings.bot_token,
                               bot_user_id=identity["user_id"], bot_id=identity.get("bot_id"))

    def delivery(origin, answer=None, blocks=None):
        payload = answer_payload(answer) if blocks is None else {"text": "Choose a service or ask a question.", "blocks": blocks}
        if origin.response_url:
            if not safe_response_url(origin.response_url):
                raise ValueError("Invalid response destination")
            response = WebhookClient(origin.response_url, timeout=3, logger=logger, retry_handlers=[]).send(
                **payload, response_type="ephemeral", replace_original=False)
            if response.status_code != 200:
                raise ValueError("Slack delivery unavailable")
        else:
            result = client.chat_postEphemeral(channel=origin.channel, user=origin.user,
                thread_ts=origin.thread or None, **payload, parse="none", link_names=False)
            if not result.get("ok"):
                raise ValueError("Slack delivery unavailable")

    deliver = delivery if send is None else send
    adapter = Adapter(settings, deliver, engine=engine)
    app = App(client=client, authorize=authorize, logger=logger,
              token_verification_enabled=False, request_verification_enabled=True)

    @app.command("/cra")
    def slash(ack, body):
        try:
            origin = Origin(body["team_id"], body["user_id"], body["channel_id"], response_url=body["response_url"])
            if origin.team != settings.team:
                raise ValueError
            question = body.get("text", "").strip()
            if question:
                ack(text="Reviewing your question…", response_type="ephemeral")
                adapter.submit("slash:" + body["trigger_id"], origin, question)
            else:
                token = adapter.context(origin)
                ack(text="Choose a service or ask a question.", blocks=picker(token), response_type="ephemeral")
        except Exception:
            ack(text=UNAVAILABLE, response_type="ephemeral")

    @app.event("message")
    def channel(body, event):
        if (body.get("team_id") != settings.team or event.get("channel") != settings.channel
                or body.get("is_ext_shared_channel") or event.get("is_ext_shared_channel")
                or event.get("subtype") or event.get("bot_id") or event.get("hidden")
                or event.get("user_team", settings.team) != settings.team
                or event.get("source_team", settings.team) != settings.team):
            return
        try:
            origin = Origin(settings.team, event["user"], settings.channel, thread=event.get("thread_ts") or event["ts"])
            question = event.get("text", "").strip()
            if question.casefold() in {"cra", "/cra", "start", "menu", "services"}:
                # Menu events are deduplicated too, without entering the graph.
                key = "menu:" + body["event_id"]
                with adapter.lock:
                    adapter.seen = {k: v for k, v in adapter.seen.items() if v > adapter.clock()}
                    if key in adapter.seen:
                        return
                    if len(adapter.seen) >= 2048:
                        return
                    adapter.seen[key] = adapter.clock() + 600
                token = adapter.context(origin)
                deliver(origin, blocks=picker(token))
            elif question:
                adapter.submit("event:" + body["event_id"], origin, question)
        except Exception:
            return

    def open_question(ack, body):
        ack()
        try:
            action = body["actions"][0]
            token = action["block_id"].removeprefix("ctx_")
            origin = adapter.resolve(token, body["team"]["id"], body["user"]["id"])
            if origin is None:
                return
            service = action["selected_option"]["value"] if action["action_id"] == SERVICE_ACTION else GENERAL
            client.views_open(trigger_id=body["trigger_id"], view=question_modal(token, service))
        except Exception:
            return

    app.action(SERVICE_ACTION)(open_question)
    app.action(QUESTION_ACTION)(open_question)

    @app.view(VIEW_CALLBACK)
    def submitted(ack, body, view):
        try:
            token, team, user = view["private_metadata"], body["team"]["id"], body["user"]["id"]
            origin = adapter.resolve(token, team, user)
            if origin is None:
                ack(response_action="errors", errors={"question": "This form has expired. Start again with /cra."})
                return
            try:
                question, service = modal_question(view)
            except (KeyError, TypeError, ValueError):
                ack(response_action="errors", errors={"question": "Choose a matching known service and enter a question of up to 3800 characters."})
                return
            if adapter.resolve(token, team, user, consume=True) is None:
                ack()
                return
            ack()
            adapter.submit("view:" + view["id"], origin, question, service)
        except Exception:
            ack()

    @app.error
    def protected_error(error):
        # Silence framework exception details, which may contain user payloads.
        return None

    return app, adapter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate local configuration without contacting Slack or Groq")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        if not os.environ.get("GROQ_API_KEY", "").strip() or os.environ["GROQ_API_KEY"].startswith("replace_"):
            raise ConfigurationError("Groq configuration is missing.")
        if args.check:
            print("Local Slack configuration is valid. Workspace connectivity has not been verified.")
            return
        from slack_bolt.adapter.socket_mode import SocketModeHandler
        app, adapter = create_app(settings)
        handler = SocketModeHandler(app, settings.app_token, logger=quiet_logger())
        adapter.start()
        print("CRA2 Slack Socket Mode is starting. Stop with Ctrl+C.")
        try:
            handler.start()
        finally:
            handler.close()
            adapter.close()
    except KeyboardInterrupt:
        pass
    except Exception:
        parser.exit(1, "Slack setup is unavailable. Verify the ignored environment file, workspace/channel IDs, tokens and app installation.\n")


if __name__ == "__main__":
    main()

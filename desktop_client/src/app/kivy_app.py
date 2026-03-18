from __future__ import annotations

import sys
import traceback
from pathlib import Path
from threading import Thread
from typing import Dict, List

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.button import Button
from kivy.uix.label import Label

from httpx import HTTPStatusError

from .encryption import EncryptionError, EncryptionKeyStore
from .models import PendingMessageEntry, TokenResponse
from .network import APIClient

KV_PATH = Path(__file__).resolve().parent / "ui" / "app.kv"

MAX_PASSWORD_BYTES = 72

MIN_PASSWORD_LENGTH = 8
PASSWORD_REQUIREMENTS = {
    "ru": "Не менее 8 символов, должна быть одна заглавная буква и одна цифра.",
    "en": "At least 8 characters, must include one uppercase letter and one digit.",
}

STATUS_MESSAGES = {
    "ready": {"ru": "Готово.", "en": "Ready."},
    "fill_credentials": {"ru": "Заполните ник и пароль.", "en": "Please enter a nick and password."},
    "registering": {"ru": "Регистрация...", "en": "Registering..."},
    "register_complete": {"ru": "Готово. Входим автоматически...", "en": "Done. Signing you in..."},
    "login_progress": {"ru": "Вход...", "en": "Logging in..."},
    "authenticated": {"ru": "Аутентифицировано.", "en": "Authenticated."},
    "public_key_synchronized": {
        "ru": "Публичный ключ синхронизирован.",
        "en": "Public key synchronized.",
    },
    "friends_loaded": {
        "ru": "Загружено {count} контактов.",
        "en": "Loaded {count} contacts.",
    },
    "pending_loaded": {
        "ru": "Входящих: {count}.",
        "en": "Inbox: {count}.",
    },
    "friend_selected": {"ru": "Выбран {nick}.", "en": "Selected {nick}."},
    "empty_message": {"ru": "Сообщение не может быть пустым.", "en": "Message cannot be empty."},
    "select_contact": {"ru": "Выберите контакт.", "en": "Select a contact."},
    "no_keys": {"ru": "Нет ключей шифрования.", "en": "No encryption keys."},
    "message_sent": {"ru": "Сообщение отправлено.", "en": "Message sent."},
    "request_sent": {"ru": "Запрос отправлен.", "en": "Request sent."},
    "ping": {"ru": "Клиент на связи.", "en": "Client is online."},
    "encryption_error": {"ru": "Ошибка шифрования: {error}", "en": "Encryption error: {error}"},
    "error": {"ru": "Ошибка: {error}", "en": "Error: {error}"},
}


class SecureMessengerApp(App):
    log_text = StringProperty(STATUS_MESSAGES["ready"]["ru"])
    friends = ListProperty([])
    pending = ListProperty([])
    authenticated = BooleanProperty(False)
    selected_friend_index = NumericProperty(-1)
    current_language = StringProperty("ru")
    login_title = StringProperty("")
    nick_hint_text = StringProperty("")
    password_label = StringProperty("")
    password_hint_text = StringProperty("")
    language_button_text = StringProperty("")
    friends_label = StringProperty("")
    messages_label = StringProperty("")
    request_button_text = StringProperty("")
    register_button_text = StringProperty("")
    login_button_text = StringProperty("")
    send_button_text = StringProperty("")
    fetch_pending_text = StringProperty("")
    ping_button_text = StringProperty("")
    friend_hint_text = StringProperty("")
    password_guidance = StringProperty("")

    TRANSLATIONS = {
        "ru": {
            "login_title": "Добро пожаловать",
            "nick_hint_text": "Ник",
            "password_label": "Пароль",
            "password_hint_text": PASSWORD_REQUIREMENTS["ru"],
            "language_button_text": "English",
            "friends_label": "Контакты",
            "messages_label": "Входящие",
            "request_button_text": "Отправить заявку",
            "register_button_text": "Регистрация",
            "login_button_text": "Войти",
            "send_button_text": "Отправить",
            "fetch_pending_text": "Обновить сообщения",
            "ping_button_text": "Пинг",
            "friend_hint_text": "Ник друга",
        },
        "en": {
            "login_title": "Welcome",
            "nick_hint_text": "Nick",
            "password_label": "Password",
            "password_hint_text": PASSWORD_REQUIREMENTS["en"],
            "language_button_text": "Русский",
            "friends_label": "Friends",
            "messages_label": "Inbox",
            "request_button_text": "Send request",
            "register_button_text": "Register",
            "login_button_text": "Login",
            "send_button_text": "Send",
            "fetch_pending_text": "Refresh messages",
            "ping_button_text": "Ping",
            "friend_hint_text": "Friend nick",
        },
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api = APIClient()
        self.key_store: EncryptionKeyStore | None = None
        self.worker_threads: List[Thread] = []
        self.root_widget = None
        self.update_texts()

    def build(self):
        self.root_widget = Builder.load_file(str(KV_PATH))
        return self.root_widget

    def on_start(self):
        Clock.schedule_interval(self._periodic_sync, 20)

    def _periodic_sync(self, _dt):
        if self.authenticated:
            self.update_pending()
            self.presence_ping()

    def _localize(self, translations: Dict[str, str], **format_kwargs):
        text = translations.get(self.current_language) or translations.get("ru") or next(iter(translations.values()))
        return text.format(**format_kwargs) if format_kwargs else text

    def set_log(self, message: str | Dict[str, str], **format_kwargs):
        if isinstance(message, dict):
            self.log_text = self._localize(message, **format_kwargs)
        elif format_kwargs:
            self.log_text = message.format(**format_kwargs)
        else:
            self.log_text = message

    def toggle_language(self):
        self.current_language = "en" if self.current_language == "ru" else "ru"
        self.update_texts()
        if self.password_guidance:
            self.password_guidance = PASSWORD_REQUIREMENTS[self.current_language]

    def update_texts(self):
        translation = self.TRANSLATIONS[self.current_language]
        self.login_title = translation["login_title"]
        self.nick_hint_text = translation["nick_hint_text"]
        self.password_label = translation["password_label"]
        self.password_hint_text = translation["password_hint_text"]
        self.language_button_text = translation["language_button_text"]
        self.friends_label = translation["friends_label"]
        self.messages_label = translation["messages_label"]
        self.request_button_text = translation["request_button_text"]
        self.register_button_text = translation["register_button_text"]
        self.login_button_text = translation["login_button_text"]
        self.send_button_text = translation["send_button_text"]
        self.fetch_pending_text = translation["fetch_pending_text"]
        self.ping_button_text = translation["ping_button_text"]
        self.friend_hint_text = translation["friend_hint_text"]

    def run_thread(self, target, callback=None, on_error=None):
        def wrapper():
            try:
                result = target()
            except Exception as exc:
                print("Error in worker thread:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                message = STATUS_MESSAGES["error"]
                Clock.schedule_once(lambda *_ , msg=message, err=str(exc): self.set_log(msg, error=err), 0)
                if on_error:
                    Clock.schedule_once(lambda *_ , error_exc=exc: on_error(error_exc), 0)
                return
            if callback:
                Clock.schedule_once(lambda *_: callback(result), 0)

        thread = Thread(target=wrapper, daemon=True)
        self.worker_threads.append(thread)
        thread.start()

    def _password_is_valid(self, password: str) -> bool:
        if len(password) < MIN_PASSWORD_LENGTH:
            return False
        if not any(ch.isalpha() for ch in password):
            return False
        if not any(ch.isupper() for ch in password):
            return False
        if not any(ch.isdigit() for ch in password):
            return False
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            return False
        return True

    def register(self, nick: str, password: str):
        if not nick or not password:
            self.set_log(STATUS_MESSAGES["fill_credentials"])
            return
        if not self._password_is_valid(password):
            self.password_guidance = PASSWORD_REQUIREMENTS[self.current_language]
            self.set_log(self.password_guidance)
            return
        self.password_guidance = ""
        self.set_log(STATUS_MESSAGES["registering"])

        def task():
            return self.api.register(nick, password)

        def on_success(_):
            self.set_log(STATUS_MESSAGES["register_complete"])
            Clock.schedule_once(lambda *_: self.login(nick, password), 0)

        self.run_thread(task, on_success, on_error=lambda exc: self._handle_http_error(exc, highlight_password=True))

    def _handle_http_error(self, exc: Exception, *, highlight_password: bool = False):
        detail = ""
        if isinstance(exc, HTTPStatusError):
            try:
                payload = exc.response.json()
                detail = payload.get("detail", "")
            except ValueError:
                detail = exc.response.text or ""
            if not detail:
                reason = getattr(exc.response, "reason_phrase", "")
                detail = f"{exc.response.status_code} {reason}".strip()
        if detail:
            if highlight_password:
                self.password_guidance = detail
            else:
                self.password_guidance = ""
            self.set_log(detail)
        else:
            self.set_log(STATUS_MESSAGES["error"], error=str(exc))

    def login(self, nick: str, password: str):
        if not nick or not password:
            self.set_log(STATUS_MESSAGES["fill_credentials"])
            return
        self.set_log(STATUS_MESSAGES["login_progress"])

        def task():
            return self.api.login(nick, password)

        def on_success(token: TokenResponse):
            self.api.save_token(token.access_token)
            try:
                self.key_store = EncryptionKeyStore(password)
            except EncryptionError as exc:
                self.set_log(STATUS_MESSAGES["encryption_error"], error=str(exc))
                return
            self.authenticated = True
            self.set_log(STATUS_MESSAGES["authenticated"])
            Clock.schedule_once(lambda *_: setattr(self.root_widget.ids.screens, "current", "chat"), 0)
            self.update_friends()
            self.update_pending()
            self.run_thread(
                lambda: self.api.update_public_key(self.key_store.public_key_pem()),
                lambda _: self.set_log(STATUS_MESSAGES["public_key_synchronized"]),
            )

        self.run_thread(task, on_success, on_error=lambda exc: self._handle_http_error(exc))

    def update_friends(self):
        def task():
            return self.api.get_friends()

        def on_success(entries):
            self.friends = [entry.dict() for entry in entries]
            if self.key_store:
                for friend in self.friends:
                    if friend.get("public_key"):
                        self.key_store.set_friend_public_key(friend["nick"], friend["public_key"])
            self.refresh_friend_list()
            self.set_log(STATUS_MESSAGES["friends_loaded"], count=len(self.friends))

        self.run_thread(task, on_success)

    def refresh_friend_list(self):
        if not self.root_widget:
            return
        container = self.root_widget.ids.friends_container
        container.clear_widgets()
        for index, friend in enumerate(self.friends):
            status = friend.get("status_message") or ""
            btn = Button(
                text=f"{friend['nick']} ({status})" if status else friend["nick"],
                size_hint_y=None,
                height="44dp",
                background_normal="",
                background_color=(0.08, 0.12, 0.2, 1),
                color=(0.95, 0.95, 1, 1),
            )
            btn.bind(on_release=lambda *_ , idx=index: self.select_friend(idx))
            container.add_widget(btn)

    def update_pending(self):
        def task():
            return self.api.get_pending()

        def on_success(messages: List[PendingMessageEntry]):
            entries = []
            for msg in messages:
                text = "<зашифровано>"
                if self.key_store:
                    try:
                        text = self.key_store.decrypt(msg.payload)
                    except EncryptionError:
                        text = "<ошибка дешифровки>"
                entries.append({"sender": msg.sender_nick, "text": text})
            self.pending = entries
            self.refresh_pending_list()
            self.set_log(STATUS_MESSAGES["pending_loaded"], count=len(entries))

        self.run_thread(task, on_success)

    def refresh_pending_list(self):
        if not self.root_widget:
            return
        container = self.root_widget.ids.pending_container
        container.clear_widgets()
        for entry in self.pending:
            label = Label(
                text=f"{entry['sender']}: {entry['text']}",
                size_hint_y=None,
                height="36dp",
                color=(0.8, 0.9, 1, 1),
                halign="left",
                valign="middle",
            )
            label.text_size = (self.root_widget.width - 32, None)
            container.add_widget(label)

    def select_friend(self, index: int):
        self.selected_friend_index = index
        if 0 <= index < len(self.friends):
            self.set_log(STATUS_MESSAGES["friend_selected"], nick=self.friends[index]["nick"])

    def send_message(self, text: str):
        if not text:
            self.set_log(STATUS_MESSAGES["empty_message"])
            return
        if self.selected_friend_index < 0 or self.selected_friend_index >= len(self.friends):
            self.set_log(STATUS_MESSAGES["select_contact"])
            return
        friend = self.friends[self.selected_friend_index]
        if not self.key_store:
            self.set_log(STATUS_MESSAGES["no_keys"])
            return
        try:
            encrypted = self.key_store.encrypt_for(friend["nick"], text)
        except EncryptionError as exc:
            self.set_log(STATUS_MESSAGES["encryption_error"], error=str(exc))
            return

        def task():
            self.api.send_message(encrypted, [friend["nick"]])

        self.run_thread(task, lambda _: self.set_log(STATUS_MESSAGES["message_sent"]))

    def send_friend_request(self, nick: str):
        if not nick:
            self.set_log(STATUS_MESSAGES["select_contact"])
            return

        def task():
            self.api.send_friend_request(nick)

        self.run_thread(task, lambda _: self.set_log(STATUS_MESSAGES["request_sent"]))

    def presence_ping(self):
        def task():
            self.api.presence_ping()

        self.run_thread(task, lambda _: self.set_log(STATUS_MESSAGES["ping"]))

    def on_stop(self):
        self.api.close()

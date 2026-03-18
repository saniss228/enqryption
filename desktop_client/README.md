# Secure Messenger Desktop Client

This Kivy-based desktop client pairs with the secure messenger server at `45.90.45.92` (or `localhost`) and ensures every payload is encrypted before it leaves the machine. The interface focuses on the requested flows: account lifecycle, contact discovery, encrypted messaging, transient media handling, and group conversations.

## Stack

* Python 3.12+
* PySide6 for the UI
* `httpx` for talking to the FastAPI backend
* `cryptography` to manage per-contact Fernet keys + storage encryption
* `pydantic` for typed request/response helpers

## Getting started

```powershell
cd desktop_client
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
python -m desktop_client
```

Config sits in `src/app/config.py`—set `API_BASE_URL` and optionally override the media root, encryption salt, and login token file.

## Packaging

Use PyInstaller to create a standalone EXE:

```powershell
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --add-data "src/app/resources:resources" --name SecureMessengerClient __main__.py
```

Add `--windowed` if you want a GUI-only bundle.

## UI & feature notes

* Built-in keyring: each friend gets a random asymmetric key encrypted with a derived master password.
* Contacts list mirrors server friends along with approval states and public keys.
* Every message is encrypted/decrypted locally using the stored key and the server never sees plaintext.
* Background threads keep the UI responsive while polling `/messages/pending` and pinging presence.

After the desktop client is working, we can repeat the workflow for Android.

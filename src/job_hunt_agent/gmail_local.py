"""Local Gmail OAuth for a profile; refresh tokens live in the OS credential store."""

from pathlib import Path

from .profiles import validate_profile_id


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SERVICE_NAME = "JobHuntAgent"


def credential_name(profile_id: str) -> str:
    return f"{validate_profile_id(profile_id)}:gmail-oauth"


def _dependencies():
    try:
        import keyring
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as error:
        raise RuntimeError('Install Gmail support with: python -m pip install -e ".[gmail]"') from error
    return keyring, InstalledAppFlow


def authorize(profile_id: str, credentials_file: Path) -> None:
    """Open the local browser consent flow and persist the granted token locally."""
    if not credentials_file.is_file():
        raise FileNotFoundError(f"OAuth client file not found: {credentials_file}")
    keyring, flow_type = _dependencies()
    flow = flow_type.from_client_secrets_file(str(credentials_file), [GMAIL_READONLY_SCOPE])
    credentials = flow.run_local_server(port=0)
    keyring.set_password(SERVICE_NAME, credential_name(profile_id), credentials.to_json())


def is_authorized(profile_id: str) -> bool:
    keyring, _ = _dependencies()
    return keyring.get_password(SERVICE_NAME, credential_name(profile_id)) is not None


def disconnect(profile_id: str) -> None:
    keyring, _ = _dependencies()
    try:
        keyring.delete_password(SERVICE_NAME, credential_name(profile_id))
    except keyring.errors.PasswordDeleteError:
        pass

"""Actionable, credential-free Plex diagnostics for web operations."""
from urllib.parse import urlsplit
import re
import requests


class PlexDiagnosticError(RuntimeError):
    pass


def plex_error(exc, operation='contact Plex'):
    if isinstance(exc, PlexDiagnosticError):
        return str(exc)
    if isinstance(exc, requests.exceptions.SSLError):
        return 'Plex TLS certificate could not be verified. Check the HTTPS URL and certificate in Settings → Plex.'
    if isinstance(exc, requests.exceptions.Timeout):
        return 'Plex timed out. Check the server URL in Settings → Plex and confirm the server is running and reachable from Playlist Bridge.'
    if isinstance(exc, requests.exceptions.ConnectionError):
        return 'Cannot connect to Plex. Check the server URL and port in Settings → Plex. In Docker, localhost refers to the container; use an address reachable from the container.'
    if isinstance(exc, requests.exceptions.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        if status in (401, 403):
            return 'Plex rejected access. Check the Plex token and library permissions in Settings → Plex.'
        if status == 404:
            return 'Plex resource was not found (HTTP 404). Check the server URL, selected music library, and destination playlist in Settings → Plex.'
        return f'Plex returned HTTP {status}. Check the server and reverse proxy before retrying.'
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return 'The server returned an invalid Plex response. Check that Settings → Plex points to your Plex server, including the correct port.'
    return f'Could not {operation}. Check Settings → Plex and try Test & Discover Libraries.'


def validate_plex_config(config):
    plex = config.config.get('plex') or {}
    url = str(plex.get('url') or '').strip()
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme in ('http', 'https') and parsed.hostname and parsed.port != 0
    except ValueError:
        valid = False
    if not valid:
        raise PlexDiagnosticError('Plex server URL is missing or invalid. Set an http:// or https:// server URL and port in Settings → Plex.')
    if not plex.get('token'):
        raise PlexDiagnosticError('Plex token is missing. Configure it in Settings → Plex.')
    if not plex.get('music_library_key'):
        raise PlexDiagnosticError('Plex music library is not selected. Use Test & Discover Libraries in Settings → Plex.')
    return {**plex, "url": url}


def redact(message, config=None):
    text = str(message)
    if config:
        for secret in (config.config.get('plex', {}).get('token'),
                       (config.config.get('notifications') or {}).get('url')):
            if secret:
                text = text.replace(str(secret), '[REDACTED]')
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    text = re.sub(r'(?i)(https?://)[^\s/@]+:[^\s/@]+@', r'\1[REDACTED]@', text)
    text = re.sub(r'(?i)((?:x-plex-token|token|authorization|password|secret)[\s\"\x27]*[:=][\s\"\x27]*)([^\s&,\"\x27}]+)', r'\1[REDACTED]', text)
    return text[:16000]

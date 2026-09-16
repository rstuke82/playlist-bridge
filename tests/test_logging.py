import time
import unittest
import requests
from playlist_bridge.diagnostics import redact, service_failure

class DiagnosticsTests(unittest.TestCase):
    def test_secret_redaction(self):
        text = redact('X-Api-Key: abc api_key=def Authorization: Bearer xyz token=ghi https://user:pass@example.com')
        for secret in ('abc','def','xyz','ghi','user:pass'):
            self.assertNotIn(secret, text)

    def test_service_errors_are_distinct(self):
        for error, expected in ((requests.Timeout(), 'timed out'), (requests.ConnectionError(), 'Connection failed'), (ValueError(), 'invalid JSON')):
            self.assertIn(expected, service_failure('MusicBrainz', error, time.monotonic()).detail)
        for code in (403,429,503):
            response = requests.Response()
            response.status_code = code
            error = requests.HTTPError(response=response)
            detail = service_failure('MusicBrainz', error, time.monotonic()).detail
            self.assertIn(str(code), detail)
            self.assertEqual('Rate limited' in detail, code == 429)

    def test_api_logs_keep_reason_and_request_id(self):
        from unittest.mock import patch
        from fastapi import HTTPException
        from fastapi.testclient import TestClient
        from playlist_bridge import api
        route_count = len(api.app.router.routes)
        @api.app.get('/api/diagnostic-test')
        def fail():
            raise HTTPException(502, 'MusicBrainz returned HTTP 503')
        try:
            with patch.object(api, '_record_log') as log:
                response = TestClient(api.app).get('/api/diagnostic-test')
            self.assertEqual(response.status_code, 502)
            self.assertIn('X-Request-ID', response.headers)
            message = log.call_args.args[2]
            self.assertIn('MusicBrainz returned HTTP 503', message)
            self.assertIn(response.headers['X-Request-ID'], message)
        finally:
            del api.app.router.routes[route_count:]

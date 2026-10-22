import asyncio
import unittest
from starlette.requests import Request
from backend.http import ApiError, read_body


class BodyTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_stream_bytes_are_limited_even_if_content_length_lies(self):
        sent = False
        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"x" * 256, "more_body": False}
            return {"type": "http.disconnect"}
        req = Request({"type": "http", "headers": [(b"content-type", b"application/json"), (b"content-length", b"2")]}, receive)
        with self.assertRaises(ApiError) as error:
            await read_body(req, "CreateReplay", limit=128)
        self.assertEqual(error.exception.status, 413)

    async def test_slow_body_has_a_bounded_read_deadline(self):
        async def receive():
            await asyncio.Event().wait()
        req = Request({"type": "http", "headers": [(b"content-type", b"application/json")]}, receive)
        with self.assertRaises(ApiError) as error:
            await read_body(req, "CreateReplay", timeout=0.01)
        self.assertEqual((error.exception.status, error.exception.code), (408, "TIMEOUT"))

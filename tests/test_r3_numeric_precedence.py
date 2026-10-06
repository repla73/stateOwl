from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stateowl.r3_publish.types import PublicationFault
from stateowl.r3_publish.validation import _strict_request_json, _validate_publish_request

BASE = (
    '{"protocol":"stateowl/0.2-draft.3","op":"publish",'
    '"target":{"kind":"git","authority":"github.com","resource":"fixture/project","namespace":"refs/heads/state"},'
    '"expected":{"id":"git:sha1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},'
    '"mode":"submit","validation":null,'
    '"changes":[{"path":"state/x","put":{"encoding":"utf8","data":"x"}}]'
)


def parse_extra(token: str):
    raw = (BASE + ',"extra":' + token + "}").encode("utf-8")
    return _strict_request_json(raw, 64)


class R3NumericPrecedenceTests(unittest.TestCase):
    def test_unrepresentable_fraction_precedes_schema_rejection(self):
        with self.assertRaises(PublicationFault) as caught:
            parse_extra("0.10000000000000001")
        self.assertEqual(caught.exception.code, "NUMBER_UNREPRESENTABLE")

    def test_unsafe_integer_precedes_schema_rejection(self):
        with self.assertRaises(PublicationFault) as caught:
            parse_extra("9007199254740992")
        self.assertEqual(caught.exception.code, "NUMBER_UNREPRESENTABLE")

    def test_representable_extra_numeric_reaches_schema_rejection(self):
        request = parse_extra("0.1")
        self.assertFalse(_validate_publish_request(request))

    def test_negative_zero_remains_invalid_request(self):
        for token in ("-0", "-0.0", "-0e3"):
            with self.subTest(token=token):
                with self.assertRaises(PublicationFault) as caught:
                    parse_extra(token)
                self.assertEqual(caught.exception.code, "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()

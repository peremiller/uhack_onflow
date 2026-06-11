"""Unit tests for flow_utils (no network required)."""

import json
import unittest
from unittest.mock import patch, MagicMock
import flow_utils


def _mock_urlopen(responses: dict):
    """Return a context-manager mock that serves canned JSON responses by URL suffix."""
    def side_effect(url):
        for suffix, payload in responses.items():
            if suffix in url:
                cm = MagicMock()
                cm.__enter__ = lambda s: s
                cm.__exit__ = MagicMock(return_value=False)
                cm.read.return_value = json.dumps(payload).encode()
                return cm
        raise ValueError(f"Unexpected URL: {url}")
    return side_effect


class TestFlowBalance(unittest.TestCase):
    def test_balance_conversion(self):
        account_payload = {"balance": "123456789", "keys": [], "contracts": {}}
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen({"/accounts/": account_payload})):
            balance = flow_utils.flow_balance("0xABC123")
        self.assertAlmostEqual(balance, 1.23456789)

    def test_strips_0x_prefix(self):
        account_payload = {"balance": "0", "keys": [], "contracts": {}}
        captured = []
        original = flow_utils._get
        def capturing_get(base, path):
            captured.append(path)
            return account_payload
        with patch.object(flow_utils, "_get", side_effect=capturing_get):
            flow_utils.flow_balance("0xDEADBEEF")
        self.assertIn("DEADBEEF", captured[0])
        self.assertNotIn("0x", captured[0])


class TestGetTransaction(unittest.TestCase):
    TX_ID = "abc123def456"
    TX_PAYLOAD = {"id": TX_ID}
    RESULT_PAYLOAD = {
        "status": "SEALED",
        "error_message": "",
        "gas_used": "500",
        "events": [
            {
                "type": "flow.AccountCreated",
                "transaction_index": "0",
                "event_index": "0",
                "payload": "base64==",
            }
        ],
    }

    def test_get_transaction_structure(self):
        responses = {
            f"/transactions/{self.TX_ID}": self.TX_PAYLOAD,
            f"/transaction_results/{self.TX_ID}": self.RESULT_PAYLOAD,
        }
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen(responses)):
            result = flow_utils.get_transaction(self.TX_ID)

        self.assertEqual(result["id"], self.TX_ID)
        self.assertEqual(result["status"], "SEALED")
        self.assertEqual(result["gas_used"], 500)
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["type"], "flow.AccountCreated")

    def test_get_transaction_strips_0x(self):
        captured = []
        def fake_get(base, path):
            captured.append(path)
            if "transaction_results" in path:
                return self.RESULT_PAYLOAD
            return self.TX_PAYLOAD
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.get_transaction(f"0x{self.TX_ID}")
        for path in captured:
            self.assertNotIn("0x", path)


if __name__ == "__main__":
    unittest.main()

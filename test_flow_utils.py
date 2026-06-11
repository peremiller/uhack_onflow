"""Unit tests for flow_utils (no network required)."""

import json
import unittest
import urllib.error
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


class TestGetAccount(unittest.TestCase):
    ACCOUNT_PAYLOAD = {"balance": "500000000", "keys": ["key1"], "contracts": {"Contract": "code"}}

    def _capturing_get(self, payload):
        captured = []
        def fake_get(base, path):
            captured.append((base, path))
            return payload
        return fake_get, captured

    def test_mainnet_url(self):
        fake_get, captured = self._capturing_get(self.ACCOUNT_PAYLOAD)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.get_account("ABC123", network="mainnet")
        self.assertEqual(captured[0][0], flow_utils.MAINNET_URL)

    def test_testnet_url(self):
        fake_get, captured = self._capturing_get(self.ACCOUNT_PAYLOAD)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.get_account("ABC123", network="testnet")
        self.assertEqual(captured[0][0], flow_utils.TESTNET_URL)

    def test_strips_0x_prefix(self):
        fake_get, captured = self._capturing_get(self.ACCOUNT_PAYLOAD)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.get_account("0xDEADBEEF")
        self.assertIn("DEADBEEF", captured[0][1])
        self.assertNotIn("0x", captured[0][1])

    def test_expands_contracts_and_keys(self):
        fake_get, captured = self._capturing_get(self.ACCOUNT_PAYLOAD)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.get_account("ABC123")
        path = captured[0][1]
        self.assertIn("contracts", path)
        self.assertIn("keys", path)

    def test_returns_full_payload(self):
        fake_get, _ = self._capturing_get(self.ACCOUNT_PAYLOAD)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            result = flow_utils.get_account("ABC123")
        self.assertEqual(result, self.ACCOUNT_PAYLOAD)


class TestGetBlock(unittest.TestCase):
    BLOCK_PAYLOAD = {"id": "blockid123", "height": "12345", "timestamp": "2024-01-01T00:00:00Z"}

    def _capturing_get(self, payload):
        captured = []
        def fake_get(base, path):
            captured.append((base, path))
            return payload
        return fake_get, captured

    def test_sealed_path_when_no_height(self):
        fake_get, captured = self._capturing_get(self.BLOCK_PAYLOAD)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.get_block()
        self.assertIn("sealed", captured[0][1])

    def test_specific_height_path(self):
        fake_get, captured = self._capturing_get(self.BLOCK_PAYLOAD)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.get_block(height=12345)
        self.assertIn("12345", captured[0][1])
        self.assertNotIn("sealed", captured[0][1])

    def test_mainnet_url(self):
        fake_get, captured = self._capturing_get(self.BLOCK_PAYLOAD)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.get_block(network="mainnet")
        self.assertEqual(captured[0][0], flow_utils.MAINNET_URL)

    def test_testnet_url(self):
        fake_get, captured = self._capturing_get(self.BLOCK_PAYLOAD)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.get_block(network="testnet")
        self.assertEqual(captured[0][0], flow_utils.TESTNET_URL)

    def test_returns_payload(self):
        fake_get, _ = self._capturing_get(self.BLOCK_PAYLOAD)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            result = flow_utils.get_block()
        self.assertEqual(result, self.BLOCK_PAYLOAD)


class TestFlowBalanceEdgeCases(unittest.TestCase):
    def _fake_get_returning_balance(self, balance_str, captured_bases=None):
        def fake_get(base, path):
            if captured_bases is not None:
                captured_bases.append(base)
            return {"balance": balance_str, "keys": [], "contracts": {}}
        return fake_get

    def test_testnet_url(self):
        captured = []
        fake_get = self._fake_get_returning_balance("0", captured)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.flow_balance("ABC123", network="testnet")
        self.assertEqual(captured[0], flow_utils.TESTNET_URL)

    def test_zero_balance(self):
        fake_get = self._fake_get_returning_balance("0")
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            balance = flow_utils.flow_balance("ABC123")
        self.assertEqual(balance, 0.0)

    def test_missing_balance_key_defaults_to_zero(self):
        def fake_get(base, path):
            return {"keys": [], "contracts": {}}
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            balance = flow_utils.flow_balance("ABC123")
        self.assertEqual(balance, 0.0)

    def test_large_balance_precision(self):
        fake_get = self._fake_get_returning_balance("10000000000")
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            balance = flow_utils.flow_balance("ABC123")
        self.assertAlmostEqual(balance, 100.0)


class TestGetTransactionEdgeCases(unittest.TestCase):
    TX_ID = "deadbeef1234"
    TX_PAYLOAD = {"id": TX_ID}

    def _fake_get(self, result_payload, captured_bases=None):
        def fake_get(base, path):
            if captured_bases is not None:
                captured_bases.append(base)
            if "transaction_results" in path:
                return result_payload
            return self.TX_PAYLOAD
        return fake_get

    def test_testnet_url(self):
        captured = []
        result_payload = {"status": "SEALED", "error_message": "", "gas_used": "0", "events": []}
        fake_get = self._fake_get(result_payload, captured)
        with patch.object(flow_utils, "_get", side_effect=fake_get):
            flow_utils.get_transaction(self.TX_ID, network="testnet")
        self.assertTrue(all(b == flow_utils.TESTNET_URL for b in captured))

    def test_empty_events(self):
        result_payload = {"status": "SEALED", "error_message": "", "gas_used": "100", "events": []}
        with patch.object(flow_utils, "_get", side_effect=self._fake_get(result_payload)):
            result = flow_utils.get_transaction(self.TX_ID)
        self.assertEqual(result["events"], [])

    def test_multiple_events_all_returned(self):
        result_payload = {
            "status": "SEALED",
            "error_message": "",
            "gas_used": "200",
            "events": [
                {"type": "A.event1", "transaction_index": "0", "event_index": "0", "payload": "p1"},
                {"type": "A.event2", "transaction_index": "0", "event_index": "1", "payload": "p2"},
            ],
        }
        with patch.object(flow_utils, "_get", side_effect=self._fake_get(result_payload)):
            result = flow_utils.get_transaction(self.TX_ID)
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(result["events"][0]["type"], "A.event1")
        self.assertEqual(result["events"][1]["type"], "A.event2")

    def test_missing_error_message_defaults_to_empty_string(self):
        result_payload = {"status": "SEALED", "gas_used": "0", "events": []}
        with patch.object(flow_utils, "_get", side_effect=self._fake_get(result_payload)):
            result = flow_utils.get_transaction(self.TX_ID)
        self.assertEqual(result["error_message"], "")

    def test_missing_gas_used_defaults_to_zero(self):
        result_payload = {"status": "SEALED", "error_message": "", "events": []}
        with patch.object(flow_utils, "_get", side_effect=self._fake_get(result_payload)):
            result = flow_utils.get_transaction(self.TX_ID)
        self.assertEqual(result["gas_used"], 0)


class TestHttpErrorHandling(unittest.TestCase):
    def test_http_404_propagates(self):
        err = urllib.error.HTTPError(url="http://x", code=404, msg="Not Found", hdrs=None, fp=None)
        with patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(urllib.error.HTTPError):
                flow_utils._get(flow_utils.MAINNET_URL, "/accounts/abc")

    def test_http_500_propagates(self):
        err = urllib.error.HTTPError(url="http://x", code=500, msg="Server Error", hdrs=None, fp=None)
        with patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(urllib.error.HTTPError):
                flow_utils._get(flow_utils.MAINNET_URL, "/blocks/1")

    def test_network_error_propagates(self):
        err = urllib.error.URLError("connection refused")
        with patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(urllib.error.URLError):
                flow_utils._get(flow_utils.MAINNET_URL, "/accounts/abc")

    def test_get_constructs_correct_url(self):
        captured_urls = []
        def fake_urlopen(url):
            captured_urls.append(url)
            cm = MagicMock()
            cm.__enter__ = lambda s: s
            cm.__exit__ = MagicMock(return_value=False)
            cm.read.return_value = b"{}"
            return cm
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            flow_utils._get(flow_utils.MAINNET_URL, "/accounts/ABC")
        self.assertEqual(captured_urls[0], f"{flow_utils.MAINNET_URL}/accounts/ABC")


if __name__ == "__main__":
    unittest.main()

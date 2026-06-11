"""
Utility helpers for interacting with the Flow blockchain REST API.

Docs: https://developers.flow.com/http-api
"""

import json
import urllib.request
import urllib.error
from typing import Optional

MAINNET_URL = "https://rest-mainnet.onflow.org/v1"
TESTNET_URL = "https://rest-testnet.onflow.org/v1"


def _get(base_url: str, path: str) -> dict:
    url = f"{base_url}{path}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode())


def get_account(address: str, network: str = "mainnet") -> dict:
    """Fetch account info (balance, keys, contracts) for a Flow address."""
    base = MAINNET_URL if network == "mainnet" else TESTNET_URL
    # Normalize: strip leading 0x
    address = address.lstrip("0x")
    return _get(base, f"/accounts/{address}?expand=contracts,keys")


def flow_balance(address: str, network: str = "mainnet") -> float:
    """Return the FLOW token balance for an address as a human-readable float."""
    account = get_account(address, network)
    # Balance is returned in units of 10^-8 (like satoshis)
    raw = int(account.get("balance", "0"))
    return raw / 1e8


def get_block(height: Optional[int] = None, network: str = "mainnet") -> dict:
    """Return the latest sealed block, or the block at a specific height."""
    base = MAINNET_URL if network == "mainnet" else TESTNET_URL
    if height is None:
        return _get(base, "/blocks?height=sealed")
    return _get(base, f"/blocks/{height}")


def get_transaction(tx_id: str, network: str = "mainnet") -> dict:
    """Fetch a transaction by ID and return status, events, and gas used.

    Returns a dict with keys:
        id, status, error_message, gas_used, events (list of dicts)
    """
    base = MAINNET_URL if network == "mainnet" else TESTNET_URL
    tx_id = tx_id.lstrip("0x")

    tx = _get(base, f"/transactions/{tx_id}")
    result = _get(base, f"/transaction_results/{tx_id}")

    events = [
        {
            "type": e.get("type"),
            "transaction_index": e.get("transaction_index"),
            "event_index": e.get("event_index"),
            "payload": e.get("payload"),
        }
        for e in result.get("events", [])
    ]

    return {
        "id": tx.get("id"),
        "status": result.get("status"),
        "error_message": result.get("error_message", ""),
        "gas_used": int(result.get("gas_used", 0)),
        "events": events,
    }


# TODO: Implement get_nft_collection(address, contract_name, network) that
# queries the NFT collection stored at the given address and returns a list of
# token IDs.


# TODO: Add retry logic with exponential backoff to _get() so transient
# network errors don't crash callers.

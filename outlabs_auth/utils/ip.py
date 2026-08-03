"""IP-address and CIDR allow-list helpers."""

from ipaddress import ip_address, ip_network
from typing import Iterable, List


def normalize_ip_rule(value: str) -> str:
    """Validate and canonicalize one IP address or CIDR rule."""
    raw = value.strip()
    network = ip_network(raw, strict=False)
    if "/" not in raw:
        return str(network.network_address)
    return str(network)


def normalize_ip_rules(values: Iterable[str]) -> List[str]:
    """Normalize and deduplicate an allow-list while preserving order."""
    return list(dict.fromkeys(normalize_ip_rule(value) for value in values))


def ip_matches_rules(client_ip: str, rules: Iterable[str]) -> bool:
    """Return whether ``client_ip`` belongs to any valid address/CIDR rule.

    Invalid stored rules are ignored, keeping authorization fail-closed while
    allowing operators to repair legacy data.
    """
    try:
        address = ip_address(client_ip)
    except ValueError:
        return False

    for rule in rules:
        try:
            if address in ip_network(rule, strict=False):
                return True
        except (TypeError, ValueError):
            continue
    return False

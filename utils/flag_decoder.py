# utils/flag_decoder.py

from typing import Optional

# Define known flag sets and what they mean
FLAG_MAP = {
    'route': {
        'X': 'disabled',
        'A': 'active',
        'D': 'dynamic',
        'C': 'connected',
        'S': 'static',
        'r': 'rip',
        'b': 'bgp',
        'o': 'ospf',
        'm': 'mme',
        'B': 'blackhole',
        'U': 'unreachable',
        'P': 'prohibit'
    },
    'arp': {
        'X': 'disabled',
        'I': 'invalid',
        'H': 'DHCP',
        'D': 'dynamic',
        'P': 'published',
        'C': 'complete'
    },
    'interface': {
        'D': 'dynamic',
        'X': 'disabled',
        'R': 'running',
        'S': 'slave'
    },
    'interface-list': {
        '*': 'builtin',
        'D': 'dynamic'
    },
    'dhcp-lease': {
        'X': 'disabled',
        'R': 'radius',
        'D': 'dynamic',
        'B': 'blocked'
    }
}

def normalize_section(section: str) -> str:
    section = section.lower().strip()
    if "ip route" in section:
        return "/ip route"
    elif "interface list" in section:
        return "/interface list"
    elif "interface" in section:
        return "/interface"
    elif "ip arp" in section:
        return "/ip arp"
    elif "ip dhcp-server lease" in section:
        return "/ip dhcp-server lease"
    else:
        return section


def decode_flags(flags: str, section: str) -> dict[str, bool]:
    if not flags:
        return {}

    # Known flag meanings per section
    section_flags = {
        "/ip route": {
            "X": "disabled",
            "A": "active",
            "D": "dynamic",
            "C": "connect",
            "S": "static",
            "r": "rip",
            "b": "bgp",
            "o": "ospf",
            "m": "mme",
            "B": "blackhole",
            "U": "unreachable",
            "P": "prohibit",
        },
        "/interface": {
            "D": "dynamic",
            "X": "disabled",
            "R": "running",
            "S": "slave",
        },
        "/ip arp": {
            "X": "disabled",
            "I": "invalid",
            "H": "dhcp",
            "D": "dynamic",
            "P": "published",
            "C": "complete",
        },
        "/ip dhcp-server lease": {
            "X": "disabled",
            "R": "radius",
            "D": "dynamic",
            "B": "blocked",
        },
    }

    results = {}
    flag_map = section_flags.get(normalize_section(section), {})
    for char in flags:
        if char in flag_map:
            results[flag_map[char]] = True
        else:
            results[char] = True  # catch-all for unknowns

    return results

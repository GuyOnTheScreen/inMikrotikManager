# core/arp_controller.py
"""
Controller for managing ARP table operations on Mikrotik routers.

This class handles fetching, parsing, and updating ARP entries using SSH.
Updated to use shared SSH connection from client.py and fallback to profiles for credentials.
"""

from typing import List, Dict

from .client import MikrotikClient, Profiles
from .log import append
import logging

class ArpController:
    """ARP Controller class for Mikrotik operations."""

    def __init__(self, parent=None):
        self.parent = parent
        self._client = None
        self.profiles = Profiles()  # Load profiles for credential fallback

    def set_ssh_client(self, client):
        self._client = client

    def _get_client(self):
        if self._client is None:
            # Fallback to test profile from profiles.json
            test_profile = self.profiles.get("test_router")
            if test_profile:
                host = test_profile.get("host", "192.168.1.1")
                username = test_profile.get("username", "admin")
                password = test_profile.get("password", "password")
                port = test_profile.get("port", 22)
                self._client = MikrotikClient.get_instance(host, username, password, port)
            else:
                raise RuntimeError("No SSH client set and no test profile found in profiles.json")
        return self._client

    def fetch_arp_table(self) -> List[Dict[str, str]]:
        """Fetch and parse the ARP table from the Mikrotik router."""
        try:
            client = self._get_client()
            output = client.cmd("/ip arp print detail")
            arp_entries = self._parse_arp_output(output)
            logging.info(f"Fetched {len(arp_entries)} ARP entries")
            append(f"Fetched ARP table")
            return arp_entries
        except Exception as e:
            logging.error(f"Error fetching ARP table: {e}")
            append(f"Error in ARP fetch: {e}")
            return []

    def _parse_arp_output(self, output: str) -> List[Dict[str, str]]:
        """Parse the raw ARP output into a list of dictionaries."""
        entries = []
        lines = output.splitlines()
        for line in lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    entry = {
                        "flags": parts[0] if len(parts) > 4 else "",
                        "address": parts[1],
                        "mac": parts[2],
                        "interface": parts[3],
                        "comment": " ".join(parts[4:]) if len(parts) > 4 else "",
                    }
                    entries.append(entry)
        return entries

    def add_arp_entry(self, address: str, mac: str, interface: str, comment: str = "") -> bool:
        """Add a new ARP entry to the Mikrotik router."""
        try:
            client = self._get_client()
            command = f"/ip arp add address={address} mac-address={mac} interface={interface}"
            if comment:
                command += f" comment={comment}"
            client.cmd(command)
            logging.info(f"Added ARP entry {address}/{mac}")
            append(f"Added ARP: {address}/{mac} on {interface}")
            return True
        except Exception as e:
            logging.error(f"Error adding ARP entry: {e}")
            append(f"Error adding ARP: {e}")
            return False

    def remove_arp_entry(self, address: str) -> bool:
        """Remove an ARP entry from the Mikrotik router."""
        try:
            client = self._get_client()
            command = f"/ip arp remove [find address={address}]"
            client.cmd(command)
            logging.info(f"Removed ARP entry {address}")
            append(f"Removed ARP: {address}")
            return True
        except Exception as e:
            logging.error(f"Error removing ARP entry: {e}")
            append(f"Error removing ARP: {e}")
            return False

    def update_arp_entry(self, address: str, new_mac: str = "", new_interface: str = "", new_comment: str = "") -> bool:
        """Update an ARP entry on the Mikrotik router."""
        try:
            client = self._get_client()
            command = f"/ip arp set [find address={address}]"
            if new_mac:
                command += f" mac-address={new_mac}"
            if new_interface:
                command += f" interface={new_interface}"
            if new_comment:
                command += f" comment={new_comment}"
            client.cmd(command)
            logging.info(f"Updated ARP entry {address}")
            append(f"Updated ARP: {address}")
            return True
        except Exception as e:
            logging.error(f"Error updating ARP entry: {e}")
            append(f"Error updating ARP: {e}")
            return False
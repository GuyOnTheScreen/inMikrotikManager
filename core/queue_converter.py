# core/queue_converter.py
import re
from typing import List, Dict

from utils.universal_parser import parse_detail_blocks
from utils.text             import clean_field, quote_field


class QueueConversionError(Exception):
    """Raised for any unrecoverable problem during conversion."""


class QueueConverter:
    """
    Low-level helper used by QueueConversionController.

    • convert(name, target_ip) –
        * fetches the DHCP lease
        * records & clears rate-limit
        * detects any conflicting *static* queue
        Returns {"lease_rate": str, "conflict": dict | None}

      NOTE: it **never** creates / removes queues itself – that is now left
      to the high-level controller so we don’t add the queue twice.
    """

    def __init__(self, ssh_client, default_limit_at: str):
        self.ssh  = ssh_client
        self.limt = default_limit_at
        # {ip: {"rate": "...", "comment": "..."}}
        self._stash: Dict[str, Dict[str, str]] = {}

    # ───────────────────────────────────────────────────────────────── convert
    def convert(self, name: str, target: str) -> Dict:
        """
        Clear the lease’s rate-limit and return information for the caller.

        Returns
        -------
        { "lease_rate": str,                       # always
          "conflict":   dict | None,               # present only if clash
          "comment":    str  | "" }                # existing queue comment
        """

        # 1) ------------- fetch the lease ----------------------------------
        lease_cmd = f'/ip dhcp-server lease print detail where address={target}'
        lease_out, lease_err = self.ssh.execute(lease_cmd)
        if lease_err or not lease_out:
            raise QueueConversionError(f"No DHCP lease for {target}: {lease_err or '<empty>'}")

        # grab rate-limit
        lease_rate = ""
        for ln in lease_out.splitlines():
            if "rate-limit=" in ln:
                lease_rate = ln.split("rate-limit=", 1)[1].split()[0]
                break
        if not lease_rate:
            raise QueueConversionError(f"No rate-limit in lease for {target}")

        # stash for overwrite / rollback
        self._stash[target] = {"rate": lease_rate, "comment": ""}

        # 2) ------------- clear rate-limit on the router --------------------
        self.ssh.execute(
            f'/ip dhcp-server lease set [find address={quote_field(target)}] rate-limit=""'
        )

        # 3) ------------- look for an existing *static* queue --------------
        raw_qs, _ = self.ssh.execute("/queue simple print detail without-paging")
        recs: List[Dict[str, str]] = parse_detail_blocks(raw_qs.splitlines(), "/queue simple")

        conflict = next((
            r for r in recs
            if clean_field(r.get("name", "")) == name or
               clean_field(r.get("target", "")).split("/")[0] == target
        ), None)

        # record existing comment (needed if we end up overwriting)
        if conflict:
            self._stash[target]["comment"] = conflict.get("comment", "")

        return {
            "lease_rate": lease_rate,
            "conflict":   conflict,
            "comment":    self._stash[target]["comment"],
        }

    # ───────────────────────────────────────────────────────────── overwrite ▼
    def overwrite(self, existing_name: str, target: str, comment: str | None = None):
        info = self._stash.get(target)
        if not info:
            raise QueueConversionError("convert() must run before overwrite()")

        rate    = info["rate"]
        comment = comment if comment is not None else info.get("comment", "")

        # 1) drop old static
        self.ssh.execute(f'/queue simple remove [find name={quote_field(existing_name)}]')

        # 2) re-create with new params
        add_cmd = (
            f'/queue simple add '
            f'name={quote_field(target)} '
            f'target={quote_field(target)} '
            f'max-limit={rate} '
            f'limit-at={self.limt} '
            f'queue=default-small/default-small '
            f'comment={quote_field(comment)}'
        )
        out, err = self.ssh.execute(add_cmd)
        if err or "failure" in out.lower():
            raise QueueConversionError(f"Overwrite failed: {err or out}")

    # ───────────────────────────────────────────────────────────── utilities ▼
    def remove_rate_limit(self, _target: str):
        """convert() already did the work – nothing further needed."""
        return

    def rollback_rate_limit(self, target: str):
        info = self._stash.get(target)
        if not info:
            raise QueueConversionError("Nothing to roll back")
        rate = info["rate"]
        cmd  = (
            f'/ip dhcp-server lease set '
            f'[find address={quote_field(target)}] rate-limit={quote_field(rate)}'
        )
        out, err = self.ssh.execute(cmd)
        if err:
            raise QueueConversionError(f"Rollback failed: {err}")

# core/queue_conversion_controller.py

from PyQt6.QtWidgets import QMessageBox
from core.queue_converter import QueueConverter, QueueConversionError
from utils.action_manager import manager as action_manager
from core.log import append as log_append
from utils.text import quote_field


class QueueConversionController:
    """
    Convert a DHCP-queue → static queue, deal with conflicts and
    record forward & inverse CLI so that ActionManager.undo() can
    roll everything back.

    The two “direct” methods at the bottom (_add_static_queue_direct
    and _handle_conflict_direct) allow NewMacController to bypass
    any “lease must have a rate-limit” or popup logic.
    """

    def __init__(self, ssh_client, default_limit_at: str, parent_widget=None):
        self.ssh  = ssh_client
        self.limt = default_limit_at
        self.ui   = parent_widget

    # ------------------------------------------------------------------ public
    def convert_dhcp_queue(self, name: str, target_ip: str) -> None:
        """High-level wrapper used by QueuePage (legacy)."""
        qc = QueueConverter(self.ssh, self.limt)
        result     = qc.convert(name, target_ip)      # may raise QueueConversionError
        lease_rate = result["lease_rate"]
        conflict   = result.get("conflict")           # None or dict

        if conflict:
            self._handle_conflict(qc, conflict, name, target_ip, lease_rate)
        else:
            self._add_static_queue(qc, name, target_ip, lease_rate)

    # -------------- (1) no conflict ───────────────────────────────────────
    def _add_static_queue(self, qc: QueueConverter, dhcp_name: str, ip: str, lease_rate: str):
        """
        DHCP queue had no conflicting static queue.  We add the new static
        one and record *three* inverse commands so Undo completely reverts
        the router to its pre-conversion state:
          1. remove static queue by name
          2. remove static queue by exact target (/32)
          3. restore the original DHCP lease rate-limit
        """
        cmd_add = (
            f'/queue simple add '
            f'name={quote_field(ip)} '
            f'target={quote_field(ip)} '
            f'max-limit={lease_rate} '
            f'limit-at={self.limt} '
            f'queue=default-small/default-small'
        )
        self.ssh.execute(cmd_add)

        inverse_cmds = [
            f'/queue simple remove [find name={quote_field(ip)}]',
            f'/queue simple remove [find target={quote_field(ip+"/32")}]',
            f'/ip dhcp-server lease set [find address={quote_field(ip)}] rate-limit={lease_rate}',
        ]

        action_manager.record(
            "add_static_queue",
            {
                "name":          dhcp_name,
                "target":        ip,
                "lease_rate":    lease_rate,
                "limit_at":      self.limt,
                "cmds_executed": [cmd_add],
                "inverse_cmds":  inverse_cmds,
            }
        )
        log_append(f"ADD static queue {ip} @ {lease_rate}")

    # -------------- (2) conflict ─────────────────────────────────────────
    def _handle_conflict(
        self,
        qc: QueueConverter,
        conflict: dict,
        dhcp_name: str,
        ip: str,
        lease_rate: str,
    ):
        old = {
            "name":        conflict["name"],
            "target":      conflict["target"].split("/")[0],
            "max":         conflict.get("max-limit", ""),
            "limit_at":    conflict.get("limit-at", ""),
            "comment":     conflict.get("comment", ""),
        }

        msg = QMessageBox(self.ui)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Queue Conflict Detected")
        msg.setText(
            f"<b>Static queue already exists</b>\n"
            f"Name: {old['name']}\n"
            f"Target: {old['target']}\n"
            f"Max-Limit: {old['max']}\n"
            f"Comment: {old['comment']}\n\n"
            f"<b>DHCP wants</b>\n"
            f"Lease-Rate: {lease_rate}\n"
            f"Limit-At: {self.limt}"
        )
        overwrite   = msg.addButton("Overwrite",              QMessageBox.ButtonRole.AcceptRole)
        keep_static = msg.addButton("Remove Rate-Limit Only", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn  = msg.addButton("Cancel",                 QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        choice = msg.clickedButton()

        # ---- OVERWRITE ------------------------------------------------------
        if choice is overwrite:
            cmd_rm1 = f'/queue simple remove [find name={quote_field(old["name"])}]'
            cmd_rm2 = f'/queue simple remove [find target={quote_field(old["target"]+"/32")}]'
            cmd_add = (
                f'/queue simple add '
                f'name={quote_field(ip)} '
                f'target={quote_field(ip)} '
                f'max-limit={lease_rate} '
                f'limit-at={self.limt} '
                f'queue=default-small/default-small '
                f'comment={quote_field(old["comment"])}'
            )
            for c in (cmd_rm1, cmd_rm2, cmd_add):
                self.ssh.execute(c)

            inverse_cmds = [
                f'/queue simple remove [find name={quote_field(ip)}]',
                f'/queue simple remove [find target={quote_field(ip+"/32")}]',
                (
                    f'/queue simple add '
                    f'name={quote_field(old["name"])} '
                    f'target={quote_field(old["target"])} '
                    f'max-limit={old["max"]} '
                    f'limit-at={old["limit_at"]} '
                    f'queue=default-small/default-small '
                    f'comment={quote_field(old["comment"])}'
                ),
                (
                    f'/ip dhcp-server lease set [find address={quote_field(ip)}] '
                    f'rate-limit={lease_rate}'
                ),
            ]
            action_manager.record(
                "overwrite_queue",
                {
                    "existing":      old,
                    "new_lease":     lease_rate,
                    "cmds_executed": [cmd_rm1, cmd_rm2, cmd_add],
                    "inverse_cmds":  inverse_cmds,
                },
            )
            log_append(f"OVERWRITE queue '{old['name']}' with DHCP rate {lease_rate}")

        # ---- KEEP static (just drop DHCP rate-limit) ------------------------
        elif choice is keep_static:
            inverse_cmds = [
                f'/ip dhcp-server lease set [find address={quote_field(ip)}] rate-limit={lease_rate}'
            ]
            action_manager.record(
                "remove_rate_limit",
                {
                    "target":        ip,
                    "lease_rate":    lease_rate,
                    "cmds_executed": [],
                    "inverse_cmds":  inverse_cmds,
                },
            )
            log_append(f"Dropped DHCP rate-limit for {ip}")

        # ---- Cancel ---------------------------------------------------------
        else:
            qc.rollback_rate_limit(ip)
            action_manager.record(
                "cancel_conversion",
                {"name": dhcp_name, "target": ip, "lease_rate": lease_rate},
            )
            log_append(f"Cancelled conversion for {dhcp_name} / {ip}")

    # ──────────────────────────────────────────────────────────────── Direct methods
    def _add_static_queue_direct(self, dhcp_name: str, ip: str, lease_rate: str):
        """
        Add a new static queue unconditionally (no conflict).
        If lease_rate is empty, uses max-limit=0 and the default limit-at.
        """
        cmd_add = (
            f'/queue simple add '
            f'name={quote_field(ip)} '
            f'target={quote_field(ip)} '
            f'max-limit={lease_rate or "0"} '
            f'limit-at={self.limt} '
            f'queue=default-small/default-small'
        )
        self.ssh.execute(cmd_add)

        inverse_cmds = [
            f'/queue simple remove [find name={quote_field(ip)}]',
            f'/queue simple remove [find target={quote_field(ip+"/32")}]',
            f'/ip dhcp-server lease set [find address={quote_field(ip)}] rate-limit={lease_rate}',
        ]

        action_manager.record(
            "add_static_queue",
            {
                "name":          dhcp_name,
                "target":        ip,
                "lease_rate":    lease_rate,
                "limit_at":      self.limt,
                "cmds_executed": [cmd_add],
                "inverse_cmds":  inverse_cmds,
            }
        )
        log_append(f"ADD static queue {ip} @ {lease_rate}")

    def _handle_conflict_direct(
        self,
        conflict: dict,
        dhcp_name: str,
        ip: str,
        lease_rate: str,
    ):
        """
        Overwrite an existing static queue unconditionally:
        1) Remove it by name  & by target
        2) Add a new static queue (with default limit-at and same comment)
        3) Restore the DHCP lease’s rate-limit (if lease_rate nonempty)
        """
        old = {
            "name":     conflict["name"],
            "target":   conflict["target"].split("/")[0],
            "max":      conflict.get("max-limit", ""),
            "limit_at": conflict.get("limit-at", ""),
            "comment":  conflict.get("comment", ""),
        }

        cmd_rm1 = f'/queue simple remove [find name={quote_field(old["name"])}]'
        cmd_rm2 = f'/queue simple remove [find target={quote_field(old["target"]+"/32")}]'
        cmd_add = (
            f'/queue simple add '
            f'name={quote_field(ip)} '
            f'target={quote_field(ip)} '
            f'max-limit={lease_rate or "0"} '
            f'limit-at={self.limt} '
            f'queue=default-small/default-small '
            f'comment={quote_field(old["comment"])}'
        )

        for c in (cmd_rm1, cmd_rm2, cmd_add):
            self.ssh.execute(c)

        inverse_cmds = [
            f'/queue simple remove [find name={quote_field(ip)}]',
            f'/queue simple remove [find target={quote_field(ip+"/32")}]',
            (
                f'/queue simple add '
                f'name={quote_field(old["name"])} '
                f'target={quote_field(old["target"])} '
                f'max-limit={old["max"]} '
                f'limit-at={old["limit_at"]} '
                f'queue=default-small/default-small '
                f'comment={quote_field(old["comment"])}'
            ),
            (
                f'/ip dhcp-server lease set [find address={quote_field(ip)}] '
                f'rate-limit={lease_rate}'
            ),
        ]

        action_manager.record(
            "overwrite_queue",
            {
                "existing":      old,
                "new_lease":     lease_rate,
                "cmds_executed": [cmd_rm1, cmd_rm2, cmd_add],
                "inverse_cmds":  inverse_cmds,
            },
        )
        log_append(f"OVERWRITE queue '{old['name']}' with DHCP rate {lease_rate}")

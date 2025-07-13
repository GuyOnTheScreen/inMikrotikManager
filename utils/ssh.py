# utils/ssh.py
import paramiko
from utils.text import quote_field

class SSHClient:
    def __init__(self, host, user, password, port=22):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.client = None

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(hostname=self.host, port=self.port, username=self.user, password=self.password)

    def execute(self, command):
        stdin, stdout, stderr = self.client.exec_command(command)
        return stdout.read().decode(), stderr.read().decode()

    def disconnect(self):
        if self.client:
            self.client.close()

    def run(self, command: str) -> list[str]:
        stdout, stderr = self.execute(command)
        if stderr:
            raise RuntimeError(stderr)
        return stdout.splitlines()

    def find(self, path: str, **conditions) -> tuple[str, str]:
        """
        Run a print detail where X query (e.g., find a lease by address).
        Example:
            ssh.find("/ip dhcp-server lease", address="192.168.0.100")
        """
        condition_str = " ".join(f'{k}={quote_field(v)}' for k, v in conditions.items())
        cmd = f"{path} print detail where {condition_str}"
        return self.execute(cmd)

    def find_ids(self, path: str, **conditions) -> list[str]:
        """
        Finds IDs matching conditions. Useful for remove/set targeting.
        Returns list of numeric IDs as strings.
        """
        stdout, _ = self.find(path, **conditions)
        ids = []
        for line in stdout.splitlines():
            parts = line.strip().split()
            if parts and parts[0].isdigit():
                ids.append(parts[0])
        return ids

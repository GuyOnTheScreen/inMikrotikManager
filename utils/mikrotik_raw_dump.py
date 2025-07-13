# mikrotik_raw_dump.py

import paramiko

HOST = "192.168.0.1"
USERNAME = "Temp"
PASSWORD = "TempPassword123"

COMMANDS = [
    "/ip route print detail without-paging",
    "/ip dhcp-server lease print detail without-paging",
    "/ip arp print detail without-paging",
    "/interface print detail without-paging",
    "/interface list print detail without-paging",
    "/queue simple print detail without-paging",
]


def run_command(ssh, command):
    print(f"\n=== {command} ===")
    stdin, stdout, stderr = ssh.exec_command(command)
    output = stdout.read().decode("utf-8", errors="replace")
    error = stderr.read().decode("utf-8", errors="replace")
    if output:
        print(output.strip())
    if error:
        print(f"[stderr] {error.strip()}")


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(HOST, username=USERNAME, password=PASSWORD, timeout=5)
        for cmd in COMMANDS:
            run_command(ssh, cmd)
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()

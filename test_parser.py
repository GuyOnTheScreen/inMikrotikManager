# test_parser.py

from utils.ssh import SSHClient
from utils.universal_parser import parse_all_sections

ssh = SSHClient("192.168.0.1", "Temp", "TempPassword123")
ssh.connect()

commands = [
    "/ip route print detail without-paging",
    "/ip dhcp-server lease print detail without-paging",
    "/ip arp print detail without-paging",
    "/interface print detail without-paging",
    "/interface list print detail without-paging",
    "/queue simple print detail without-paging",
]

all_lines = []
for cmd in commands:
    all_lines.append(f"=== {cmd} ===")
    all_lines.extend(ssh.run(cmd))

ssh.disconnect()

parsed = parse_all_sections(all_lines)

# Print summaries
for section, items in parsed.items():
    print(f"\n--- {section} ({len(items)} items) ---")
    for item in items[:15]:  # Show a few examples
        print(item)
    if len(items) > 3:
        print("...")


# example_usage.py

from utils.ssh import SSHClient
from InNocTools.InMikrotikManager.v3.utils.universal_parser import parse_detail_blocks

ssh = SSHClient("192.168.0.1", "Temp", "TempPassword123")
ssh.connect()

raw_lines = ssh.run("/ip dhcp-server lease print detail without-paging")
parsed_leases = parse_detail_blocks(raw_lines)

for lease in parsed_leases:
    print(lease)

ssh.disconnect()

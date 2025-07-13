# utils/universal_parser.py
import re
from utils.text import clean_field
from utils.flag_decoder import decode_flags

def parse_detail_blocks(lines: list[str], section: str) -> list[dict[str, str]]:
    """
    Parse RouterOS “print detail” output into a list[dict].

    The patch below adds one line: when the record-header line looks like
        “0 X ;;; comment …”     (flags but NO key-value pairs)
    we still capture the flags (e.g. “X”, “D”, etc.) so the GUI can decide
    whether the lease is disabled.

    Only the marked block ◀▶ is new; everything else is unchanged.
    """
    import re
    from utils.text import clean_field
    from utils.flag_decoder import decode_flags

    records: list[dict[str, str]] = []
    current: dict[str, str]     = {}
    current_flags: str | None   = None
    pending_comment: str | None = None

    def flush():
        nonlocal current, current_flags, pending_comment
        if current:
            if current_flags:
                current["_flags"] = current_flags
                current.update(decode_flags(current_flags, section))
            if pending_comment and "comment" not in current:
                current["comment"] = pending_comment
                pending_comment = None
            records.append(current)
            current = {}
            current_flags = None

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()

        if stripped.startswith("Flags:"):
            continue
        if not stripped:
            flush(); continue

        left  = line.lstrip()
        first = left[0]

        # ───────── comment-only record header (no key-value on same line)
        if (first.isdigit() or first == "*") and ";;;" in left and "=" not in left:
            flush()
            # ◀─ NEW: grab flags even on comment-only header
            hdr_parts = left.split(";;;", 1)[0].split(None, 2)
            if len(hdr_parts) >= 2 and hdr_parts[1].isalpha():
                current_flags = hdr_parts[1]
            # ────────────────────────────────────────────────────────────
            pending_comment = left.split(";;;", 1)[1].strip()
            continue

        # ───────── real record header (with = …)
        if (first.isdigit() or first == "*") and "=" in left:
            flush()
            if ";;;" in left:
                before, after = left.split(";;;", 1)
                inline = after.strip(); left = before.rstrip()
            else:
                inline = None

            if left[0] == "*":          # drop leading “* ”
                left = left[1:].lstrip()
            parts = left.split(None, 2)
            if len(parts) >= 2 and parts[1].isalpha():
                current_flags = parts[1]
                remainder     = parts[2] if len(parts) == 3 else ""
            else:
                current_flags = None
                remainder     = " ".join(parts[1:]) if len(parts) > 1 else ""

            if pending_comment:
                current["comment"] = pending_comment; pending_comment = None
            if inline:
                current["comment"] = inline

            for key, val in re.findall(r'([\w\-]+)=("[^"]*"|\S+)', remainder):
                if key == "comment":
                    current["comment"] = clean_field(val)
                else:
                    current[clean_field(key)] = clean_field(val)
            continue

        # ───────── wrapped comment continuation
        if pending_comment and "=" not in stripped:
            fragment = stripped
            if pending_comment[-1].isalnum() and fragment and fragment[0].isalnum():
                pending_comment += fragment
            else:
                pending_comment += " " + fragment
            continue

        # ───────── normal key=value continuation
        for key, val in re.findall(r'([\w\-]+)=("[^"]*"|\S+)', line):
            if key == "comment":
                current["comment"] = clean_field(val)
            else:
                current[clean_field(key)] = clean_field(val)

    flush()          # final record
    return records



def parse_all_sections(lines: list[str]) -> dict[str, list[dict[str, str]]]:
    """
    Break a big dump with === /cmd === into sections.
    Returns {section_header: parsed_records}
    """
    sections: dict[str, list[dict[str, str]]] = {}
    header: str | None = None
    block: list[str] = []

    for line in lines:
        ln = line.rstrip("\n")
        if ln.startswith("=== ") and ln.endswith(" ==="):
            if header is not None and block:
                sections[header] = parse_detail_blocks(block, header)
                block.clear()
            header = ln[4:-4].strip()
        else:
            if header is not None:
                block.append(ln)

    if header is not None and block:
        sections[header] = parse_detail_blocks(block, header)

    return sections

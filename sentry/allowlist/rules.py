from dataclasses import dataclass, field


@dataclass
class AllowlistRule:
    command: str
    allowed_args: list[str] = field(default_factory=list)  # regex patterns args must match
    denied_args: list[str] = field(default_factory=list)  # regex patterns that reject args
    max_args: int = 0


ALLOWLIST_RULES: dict[str, AllowlistRule] = {
    "uptime": AllowlistRule(
        command="uptime",
        allowed_args=[],
        denied_args=[],
        max_args=0,
    ),
    "uname": AllowlistRule(
        command="uname",
        allowed_args=[r"^-[arsnm]$"],
        denied_args=[],
        max_args=2,
    ),
    "df": AllowlistRule(
        command="df",
        allowed_args=[r"^-[hiT]$", r"^/[\w./-]+$"],
        denied_args=[],
        max_args=3,
    ),
    "free": AllowlistRule(
        command="free",
        allowed_args=[r"^-[hmgb]$"],
        denied_args=[],
        max_args=2,
    ),
    "ps": AllowlistRule(
        command="ps",
        allowed_args=[r"^aux$", r"^-ef$", r"^--sort=[\w.,+-]+$", r"^-o$", r"^[\w.,+-]+$"],
        denied_args=[],
        max_args=6,
    ),
    "ss": AllowlistRule(
        command="ss",
        allowed_args=[r"^-[tulnpa]+$"],
        denied_args=[],
        max_args=6,
    ),
    "ip": AllowlistRule(
        command="ip",
        allowed_args=[r"^addr$", r"^route$", r"^link$", r"^-s$", r"^show$"],
        denied_args=[],
        max_args=4,
    ),
    "systemctl": AllowlistRule(
        command="systemctl",
        allowed_args=[r"^status$", r"^[\w@.-]+$"],
        denied_args=[
            r"^start$",
            r"^stop$",
            r"^restart$",
            r"^enable$",
            r"^disable$",
            r"^daemon-reload$",
        ],
        max_args=3,
    ),
    "journalctl": AllowlistRule(
        command="journalctl",
        allowed_args=[
            r"^-u$",
            r"^-n$",
            r"^--no-pager$",
            r"^--since$",
            r"^--until$",
            r"^--grep$",
            r"^-p$",
            r"^[\w@./:, -]+$",
        ],
        denied_args=[r"^-f$"],
        max_args=10,
    ),
    "tail": AllowlistRule(
        command="tail",
        allowed_args=[r"^-n$", r"^-?\d+$", r"^/[\w./-]+$"],
        denied_args=[r"^-f$", r"^--follow$"],
        max_args=4,
    ),
    "head": AllowlistRule(
        command="head",
        allowed_args=[r"^-n$", r"^-?\d+$", r"^/[\w./-]+$"],
        denied_args=[],
        max_args=4,
    ),
    "grep": AllowlistRule(
        command="grep",
        allowed_args=[
            r"^-[nirlABC]$",
            r"^-C$",
            r"^-A$",
            r"^-B$",
            r"^-l$",
            r"^-?\d+$",
            r"^/[\w./-]+$",
            r"^[\w.*^$\[\]|{}()\\?+ -]+$",
        ],
        denied_args=[],
        max_args=8,
    ),
    "dmesg": AllowlistRule(
        command="dmesg",
        allowed_args=[r"^--level=[\w,]+$", r"^-[TH]$"],
        denied_args=[],
        max_args=4,
    ),
    "lsblk": AllowlistRule(
        command="lsblk",
        allowed_args=[r"^-[fo]$", r"^[\w,]+$"],
        denied_args=[],
        max_args=4,
    ),
    "iostat": AllowlistRule(
        command="iostat",
        allowed_args=[r"^-[xd]$", r"^\d+$"],
        denied_args=[],
        max_args=4,
    ),
    "ping": AllowlistRule(
        command="ping",
        allowed_args=[r"^-c$", r"^-W$", r"^\d+$", r"^[\w.-]+$"],
        denied_args=[],
        max_args=5,
    ),
    "dig": AllowlistRule(
        command="dig",
        allowed_args=[r"^[\w.-]+$", r"^[A-Z]+$"],
        denied_args=[],
        max_args=4,
    ),
    "pgrep": AllowlistRule(
        command="pgrep",
        allowed_args=[r"^-[alf]$", r"^[\w.-]+$"],
        denied_args=[],
        max_args=4,
    ),
    "lsof": AllowlistRule(
        command="lsof",
        allowed_args=[r"^-[inpP]$", r"^:?\d+$", r"^[\w.:]+$"],
        denied_args=[],
        max_args=5,
    ),
    "find": AllowlistRule(
        command="find",
        allowed_args=[
            r"^/[\w./-]+$",
            r"^-name$",
            r"^-type$",
            r"^-mtime$",
            r"^-size$",
            r"^[a-z]$",
            r"^[+-]?\d+[cwbkMG]?$",
            r'^[\w.*?"]+$',
        ],
        denied_args=[r"^-exec$", r"^-delete$", r"^-execdir$"],
        max_args=8,
    ),
    "stat": AllowlistRule(
        command="stat",
        allowed_args=[r"^/[\w./-]+$"],
        denied_args=[],
        max_args=2,
    ),
    "file": AllowlistRule(
        command="file",
        allowed_args=[r"^/[\w./-]+$"],
        denied_args=[],
        max_args=2,
    ),
    "md5sum": AllowlistRule(
        command="md5sum",
        allowed_args=[r"^/[\w./-]+$"],
        denied_args=[],
        max_args=2,
    ),
    "sha256sum": AllowlistRule(
        command="sha256sum",
        allowed_args=[r"^/[\w./-]+$"],
        denied_args=[],
        max_args=2,
    ),
    "date": AllowlistRule(
        command="date",
        allowed_args=[r'^\+[\w%/:. -]+$'],
        denied_args=[],
        max_args=1,
    ),
    "whoami": AllowlistRule(
        command="whoami",
        allowed_args=[],
        denied_args=[],
        max_args=0,
    ),
    "id": AllowlistRule(
        command="id",
        allowed_args=[r"^[\w]+$"],
        denied_args=[],
        max_args=1,
    ),
    "top": AllowlistRule(
        command="top",
        allowed_args=[r"^-b$", r"^-bn?\d*$", r"^-n$", r"^-o$", r"^\d+$", r"^[\w%+-]+$"],
        denied_args=[],
        max_args=6,
    ),
    "vmstat": AllowlistRule(
        command="vmstat",
        allowed_args=[r"^\d+$"],
        denied_args=[],
        max_args=3,
    ),
    "mpstat": AllowlistRule(
        command="mpstat",
        allowed_args=[r"^-P$", r"^[\w,]+$", r"^\d+$"],
        denied_args=[],
        max_args=4,
    ),
    "curl": AllowlistRule(
        command="curl",
        allowed_args=[r"^https?://[\w./:?&=%-]+$", r"^-[sSkLv]$", r"^--silent$", r"^--insecure$"],
        denied_args=[
            r"^-X$",
            r"^POST$",
            r"^PUT$",
            r"^DELETE$",
            r"^-d$",
            r"^--data$",
            r"^--data-raw$",
            r"^-o$",
            r"^--output$",
            r"^-T$",
            r"^--upload-file$",
        ],
        max_args=5,
    ),
}

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


PATTERNS = {
    "Razorpay key": re.compile(r"rzp_(?:live|test)_[A-Za-z0-9]{14,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "populated secret setting": re.compile(
        r"(?m)^(?:GEMINI_API_KEY|RAZORPAY_KEY_SECRET|RAZORPAY_WEBHOOK_SECRET|OPERATOR_API_TOKEN)=\S+"
    ),
}


def tracked_files(root: Path) -> list[Path]:
    environment = os.environ.copy()
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "ls-files", "-z"],
        cwd=root,
        env=environment,
        check=True,
        capture_output=True,
    )
    return [root / name for name in result.stdout.decode("utf-8").split("\0") if name]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings: list[tuple[str, int, str]] = []
    for path in tracked_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append((path.relative_to(root).as_posix(), line, label))
    if findings:
        for path, line, label in findings:
            print(f"{path}:{line}: possible {label}")
        return 1
    print("Tracked-secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

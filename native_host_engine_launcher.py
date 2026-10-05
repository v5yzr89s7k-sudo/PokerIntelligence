"""
Poker Intelligence semantic engine launcher for the native macOS host.

ScreenCaptureKit ownership belongs exclusively to the native Swift host.
This process consumes the existing Unix-domain frame socket only.
"""

import os
import runpy
import subprocess
from pathlib import Path


PROJECT_ROOT = (
    Path.home()
    / "Projects"
    / "PokerIntelligence"
)

os.chdir(PROJECT_ROOT)

os.environ["POKER_STANDALONE_APP"] = "1"
os.environ["POKER_SCK_EXTERNAL"] = "1"


# Finder/native applications do not inherit the Terminal environment.
# Recover the OpenAI credential from the user's macOS Keychain.
if not os.environ.get("OPENAI_API_KEY"):
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a",
            os.environ.get("USER", ""),
            "-s",
            "PokerIntelligence-OpenAI",
            "-w",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    os.environ["OPENAI_API_KEY"] = (
        result.stdout.strip()
    )


runpy.run_module(
    "src.v017.run_live_observer",
    run_name="__main__",
)

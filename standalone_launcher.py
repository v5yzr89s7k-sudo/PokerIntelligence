import os
import runpy
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path.home() / "Projects" / "PokerIntelligence"
os.chdir(PROJECT_ROOT)

os.environ["POKER_STANDALONE_APP"] = "1"

# Finder applications do not inherit the Terminal environment.
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
    os.environ["OPENAI_API_KEY"] = result.stdout.strip()

# Wait for the native ACR application process.
while subprocess.run(
    ["pgrep", "-f", "/Applications/ACRPoker.app/Contents/MacOS/Electron"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
).returncode != 0:
    time.sleep(2)

# Allow the poker table window to finish materializing.
time.sleep(5)

runpy.run_module(
    "src.v017.run_live_observer",
    run_name="__main__",
)

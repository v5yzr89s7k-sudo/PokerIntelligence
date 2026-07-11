from pathlib import Path
import time

p = Path("src/api/api_event_coordinator.py")
text = p.read_text()

# Ensure perf_counter is available
if "from time import perf_counter" not in text:
    text = text.replace(
        "import time",
        "import time\nfrom time import perf_counter"
    )

# Instrument the expensive blink detector
old = '''        blink_visible = False
        if state.get("phase") != "WAITING" and hero_visible:
            blink_visible = local_hero_blink_visible()
'''

new = '''        blink_visible = False
        t0 = perf_counter()
        if state.get("phase") != "WAITING" and hero_visible:
            blink_visible = local_hero_blink_visible()
        blink_ms = (perf_counter() - t0) * 1000
'''

if old in text:
    text = text.replace(old, new)

# Print timing next to HERO_CHECK
old = '''            print(
                f"[HERO_CHECK] phase={state.get('phase')} "
                f"loop_ms={loop_ms:.0f} "
                f"hero_visible={hero_visible} buttons={buttons_visible} "
                f"blink={blink_visible} active={state.get('hero_decision_active')}"
            )
'''

new = '''            print(
                f"[HERO_CHECK] "
                f"phase={state.get('phase')} "
                f"loop_ms={loop_ms:.0f} "
                f"blink_ms={blink_ms:.1f} "
                f"hero_visible={hero_visible} "
                f"buttons={buttons_visible} "
                f"blink={blink_visible} "
                f"active={state.get('hero_decision_active')}"
            )
'''

if old in text:
    text = text.replace(old, new)

p.write_text(text)
print("Instrumentation applied.")

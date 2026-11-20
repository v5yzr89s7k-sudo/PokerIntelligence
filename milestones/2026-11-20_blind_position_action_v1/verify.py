#!/usr/bin/env python3
from pathlib import Path
import hashlib, tempfile, subprocess, sys

root = Path(__file__).resolve().parents[2]
snap = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

assert sha(snap/'FullScreenVision.swift') == \
    '700101d94a136375810700eefea35c0c65b7c01f8e77199cdc812ef853e4ea2a'
assert sha(snap/'BoardPresence.swift') == \
    '8a363f2c9a88b81c68316e3770e79168e624bf0d5ca9080d2637af1d6c3d24cf'

for name in ('ACRPoker', 'Electron'):
    result = subprocess.run(
        ['pgrep', '-x', name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    if result.returncode == 0:
        sys.exit('STOP: Close ACR before offline verification.')

source = root/'experiments/fullscreen_vision_v1/FullScreenVision.swift'
record = root/'runtime/debug/pi_native_live_20261119_123904/run'

assert source.is_file() and (record/'frames.json').is_file(), \
    'Source or original recording missing'

with tempfile.TemporaryDirectory(prefix='pi_milestone_check_') as work:
    binary = Path(work)/'Observer'

    build = subprocess.run(
        ['swiftc', '-parse-as-library', '-O', str(source),
         '-o', str(binary)],
        capture_output=True, text=True, timeout=300
    )
    if build.returncode:
        sys.exit('COMPILE FAIL:\n' + build.stderr[-3000:])

    tests = [
        ('--self-test', 'SELF_TEST_PASS', []),
        ('--parallel-self-test', 'PARALLEL_TEST_PASS', []),
        ('--rapid-episode-test', 'RAPID_EPISODE_PASS',
         ['frame=22', 'frame=166', 'frame=173']),
        ('--blind-button-test', 'BLIND_BUTTON_REGRESSION_PASS',
         ['hands=3', 'dropout_guard=YES']),
        ('--seat-order-test', 'RELATIVE_SEAT_ORDER_PASS',
         ['pairs=3', 'actions_promoted=0'])
    ]

    for flag, marker, required in tests:
        command = [str(binary), flag]

        if flag not in ('--self-test', '--parallel-self-test'):
            command.append(str(record))

        result = subprocess.run(
            command, capture_output=True, text=True, timeout=300
        )

        if (result.returncode or marker not in result.stdout
                or any(s not in result.stdout for s in required)):
            sys.exit(
                'REGRESSION FAIL: ' + flag + '\n' +
                result.stdout[-1800:] + result.stderr[-1800:]
            )

        print('PASS:', flag, flush=True)

print('MILESTONE REGRESSION PASS')
print('Production source unchanged; native offline tests completed.')

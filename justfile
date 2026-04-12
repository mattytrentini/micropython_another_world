# Another World - MicroPython deployment targets
#
# Usage:
#   just deploy              # deploy to connected device
#   just deploy /dev/ttyUSB1 # specify serial port
#   just repl                # open MicroPython REPL
#   just run                 # deploy and run on device
#   just reset               # soft-reset the device

# Default serial port (override with: just deploy /dev/ttyACM0)
port := "/dev/ttyUSB0"
mpy := "mpytool -p " + port

# Deploy engine and ODROID Go HAL to device flash
deploy target_port=port:
    #!/usr/bin/env bash
    set -euo pipefail
    MPY="mpytool -p {{target_port}}"

    echo "Deploying to {{target_port}}..."

    # Copy directories (mpytool handles recursive copy)
    echo "Copying aw/..."
    $MPY cp -m aw/ :aw/

    echo "Copying hal_odroid_go/..."
    $MPY cp -m hal_odroid_go/ :hal_odroid_go/

    # Entry point — installed as main.py so it runs on boot
    echo "Copying main_odroid_go.py -> main.py..."
    $MPY cp main_odroid_go.py :main.py

    # Clean up .py files when .mpy exists (MicroPython loads .py over .mpy)
    echo "Cleaning stale .py files..."
    $MPY exec "
import os
for d in ['/aw', '/hal_odroid_go']:
    try:
        files = os.listdir(d)
    except:
        continue
    for f in files:
        if f.endswith('.py') and f[:-3] + '.mpy' in files:
            os.remove(d + '/' + f)
"

    echo "Done. Game data must be on SD card at /game/DAT/"
    echo "Reset the device or run 'just run' to start."

# Open a REPL on the device
repl target_port=port:
    mpytool -p {{target_port}} repl

# Deploy and immediately run the game
run target_port=port: (deploy target_port)
    mpytool -p {{target_port}} reset -- monitor

# Soft-reset the device
reset target_port=port:
    mpytool -p {{target_port}} reset

# List files on the device
ls target_port=port:
    mpytool -p {{target_port}} ls

# Remove all deployed files from device
clean target_port=port:
    #!/usr/bin/env bash
    set -euo pipefail
    MPY="mpytool -p {{target_port}}"
    echo "Removing deployed files from {{target_port}}..."
    $MPY rm -r :aw/ 2>/dev/null || true
    $MPY rm -r :hal_odroid_go/ 2>/dev/null || true
    $MPY rm :main.py 2>/dev/null || true
    echo "Done."

# Show device info
info target_port=port:
    mpytool -p {{target_port}} info

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
mp := "mpremote connect " + port

# Deploy engine and ODROID Go HAL to device flash
deploy target_port=port:
    #!/usr/bin/env bash
    set -euo pipefail
    MP="mpremote connect {{target_port}}"

    echo "Deploying to {{target_port}}..."

    # Create directories
    $MP mkdir :aw 2>/dev/null || true
    $MP mkdir :hal_odroid_go 2>/dev/null || true

    # Core engine
    echo "Copying aw/..."
    for f in aw/*.py; do
        echo "  $f"
        $MP fs cp "$f" ":$f"
    done

    # ODROID Go HAL
    echo "Copying hal_odroid_go/..."
    for f in hal_odroid_go/*.py; do
        echo "  $f"
        $MP fs cp "$f" ":$f"
    done

    # Entry point
    echo "Copying main_odroid_go.py..."
    $MP fs cp main_odroid_go.py :main_odroid_go.py

    echo "Done! Game data must be on SD card at /game/DAT/"

# Open a REPL on the device
repl target_port=port:
    mpremote connect {{target_port}} repl

# Deploy and immediately run the game
run target_port=port: (deploy target_port)
    mpremote connect {{target_port}} exec "exec(open('main_odroid_go.py').read())"

# Soft-reset the device
reset target_port=port:
    mpremote connect {{target_port}} reset

# List files on the device
ls target_port=port path="/":
    mpremote connect {{target_port}} fs ls :{{path}}

# Remove all deployed files from device
clean target_port=port:
    #!/usr/bin/env bash
    set -euo pipefail
    MP="mpremote connect {{target_port}}"
    echo "Removing deployed files from {{target_port}}..."
    for f in aw/*.py; do
        $MP fs rm ":$f" 2>/dev/null || true
    done
    for f in hal_odroid_go/*.py; do
        $MP fs rm ":$f" 2>/dev/null || true
    done
    $MP fs rm :main_odroid_go.py 2>/dev/null || true
    $MP fs rmdir :aw 2>/dev/null || true
    $MP fs rmdir :hal_odroid_go 2>/dev/null || true
    echo "Done."

"""Stop all Consent Management System services.

Usage:
    python scripts/stop.py
"""

import subprocess
import time
import socket

PORTS = [4565, 8000, 8001, 8002, 8003, 8004, 3000]
NAMES = {
    4565: "moto (AWS emulator)",
    8000: "consent-api",
    8001: "consent-processor",
    8002: "notification-service",
    8003: "incident-detector",
    8004: "incident-bridge",
    3000: "frontend",
}


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill_port(port: int) -> bool:
    result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
    killed = False
    for line in result.stdout.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            parts = line.split()
            pid = parts[-1]
            if pid.isdigit():
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                killed = True
    return killed


def main():
    print()
    print("============================================================")
    print("  Consent Management System - Stopping all services")
    print("============================================================")
    print()

    for port in PORTS:
        name = NAMES.get(port, str(port))
        if port_in_use(port):
            kill_port(port)
            deadline = time.time() + 3
            while time.time() < deadline:
                if not port_in_use(port):
                    break
                time.sleep(0.3)
            if not port_in_use(port):
                print(f"  [STOPPED] {name} (:{port})")
            else:
                print(f"  [FAILED]  {name} (:{port}) - could not stop")
        else:
            print(f"  [SKIPPED] {name} (:{port}) - not running")

    print()
    print("  Done.")
    print()


if __name__ == "__main__":
    main()

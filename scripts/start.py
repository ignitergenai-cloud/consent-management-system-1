"""Start all Consent Management System services locally.

Usage:
    python scripts/start.py
""" 

import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
MOTO_PORT = 4565
SERVICES = [
    {"name": "consent-api",          "port": 8000, "module": "consent_api.main:app",          "dir": "consent-api"},
    {"name": "consent-processor",    "port": 8001, "module": "consent_processor.main:app",    "dir": "consent-processor"},
    {"name": "notification-service", "port": 8002, "module": "notification_service.main:app", "dir": "notification-service"},
    {"name": "incident-detector",    "port": 8003, "module": "incident_detector.main:app",    "dir": "incident-detector"},
    {"name": "incident-bridge",      "port": 8004, "module": "incident_bridge.main:app",      "dir": "incident-bridge"},
]
FRONTEND_PORT = 3000


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill_port(port: int) -> None:
    """Kill any process listening on the given port (Windows)."""
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            parts = line.split()
            pid = parts[-1]
            if pid.isdigit():
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True)


def wait_port(port: int, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_in_use(port):
            return True
        time.sleep(0.5)
    return False


def wait_port_free(port: int, timeout: int = 10) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not port_in_use(port):
            return
        time.sleep(0.3)


def start_bg(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.Popen:
    import os
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=full_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main():
    print()
    print("============================================================")
    print("  Consent Management System - Local Startup")
    print("============================================================")
    print()

    # Step 1: Kill existing processes
    print("[1/5] Stopping existing processes on CMS ports...")
    for port in [MOTO_PORT] + [s["port"] for s in SERVICES] + [FRONTEND_PORT]:
        kill_port(port)
        wait_port_free(port)

    # Step 2: Start Moto
    print(f"[2/5] Starting Moto AWS emulator on port {MOTO_PORT}...")
    start_bg([sys.executable, "-m", "moto.server", "-p", str(MOTO_PORT)], cwd=ROOT)
    if not wait_port(MOTO_PORT, timeout=40):
        print("  ERROR: Moto did not start within 40s. Aborting.")
        sys.exit(1)
    time.sleep(2)  # let Moto fully initialise
    print("  Moto ready.")

    # Step 3: Bootstrap
    print("[3/5] Bootstrapping AWS resources (DynamoDB, SNS, SQS)...")
    result = subprocess.run(
        [sys.executable, "-u", str(ROOT / "scripts" / "bootstrap_moto.py")],
        cwd=ROOT,
    )
    if result.returncode != 0:
        print("  ERROR: Bootstrap failed.")
        sys.exit(1)
    print("  Bootstrap complete.")

    # Step 4: Start backend services
    print("[4/5] Starting backend services...")
    for svc in SERVICES:
        py_path = str(ROOT / "services" / "shared" / "src") + ";" + str(ROOT / "services" / svc["dir"] / "src")
        start_bg(
            [sys.executable, "-m", "uvicorn", svc["module"], "--host", "0.0.0.0", "--port", str(svc["port"])],
            cwd=ROOT,
            env={"PYTHONPATH": py_path},
        )
        print(f"  Started {svc['name']} on port {svc['port']}")

    print("  Waiting for all services to be healthy...")
    all_healthy = True
    for svc in SERVICES:
        ok = wait_port(svc["port"], timeout=30)
        status = "[OK]  " if ok else "[FAIL]"
        color = "\033[32m" if ok else "\033[31m"
        reset = "\033[0m"
        print(f"  {color}{status} {svc['name']}:{svc['port']}{reset}")
        if not ok:
            all_healthy = False

    # Step 5: Start frontend
    print(f"[5/5] Starting frontend on port {FRONTEND_PORT}...")
    subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=ROOT / "frontend",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=True,
    )

    print()
    if all_healthy:
        print("\033[32m============================================================\033[0m")
        print("\033[32m  All services started successfully!\033[0m")
        print("\033[32m============================================================\033[0m")
    else:
        print("\033[33m============================================================\033[0m")
        print("\033[33m  Some services failed to start - check errors above.\033[0m")
        print("\033[33m============================================================\033[0m")

    print()
    print(f"  Moto (AWS emulator)      : http://localhost:{MOTO_PORT}")
    for svc in SERVICES:
        print(f"  {svc['name']:<24}: http://localhost:{svc['port']}/health")
    print(f"  Frontend                 : http://localhost:{FRONTEND_PORT}")
    print()


if __name__ == "__main__":
    main()

"""
PKI Cash Launcher — start actors with Reticulum transport.

Usage:
    python run.py --role engine --port 5000
    python run.py --role bank   --port 5001
    python run.py --role wallet --id a --port 5002
    python run.py --role wallet --id b --port 5003
    python run.py --demo                          # all four at once
"""

import argparse
import os
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def launch_single(role: str, port: int, wallet_id: str = None):
    """Start a single actor process (Flask + RNS)."""
    if role == "wallet" and not wallet_id:
        print("Error: --id is required for wallet role")
        sys.exit(1)

    data_dir = os.path.join(BASE_DIR, "data", role if role != "wallet" else f"wallet_{wallet_id}")
    os.makedirs(data_dir, exist_ok=True)

    os.environ["PKICASH_ROLE"] = role
    os.environ["PKICASH_PORT"] = str(port)
    os.environ["PKICASH_DATA_DIR"] = data_dir
    if wallet_id:
        os.environ["PKICASH_WALLET_ID"] = wallet_id

    from src.transport import PKICashTransport
    transport = PKICashTransport(
        role=role,
        data_dir=data_dir,
    )

    from app_actor import create_app
    app = create_app(role=role, transport=transport, data_dir=data_dir, wallet_id=wallet_id)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    print(f"\n=== PKICash {role}{(' ' + wallet_id.upper()) if wallet_id else ''} ===")
    print(f"    Flask:  http://localhost:{port}")
    print(f"    RNS:    {transport.dest_hash_hex}")
    print()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


def launch_demo():
    """Start all four actors as separate sub-processes."""
    actors = [
        ("engine", 5000, None),
        ("bank",   5001, None),
        ("wallet", 5002, "a"),
        ("wallet", 5003, "b"),
    ]
    procs = []
    for role, port, wid in actors:
        cmd = [sys.executable, __file__, "--role", role, "--port", str(port)]
        if wid:
            cmd += ["--id", wid]
        proc = subprocess.Popen(cmd)
        procs.append((role, wid, port, proc))
        time.sleep(2)

    print("\n=== PKICash Demo Mode ===")
    for role, wid, port, _ in procs:
        label = f"{role} {wid.upper()}" if wid else role
        print(f"  {label:12s}  http://localhost:{port}")
    print("\nDruk Ctrl+C om alles te stoppen.\n")

    try:
        for _, _, _, proc in procs:
            proc.wait()
    except KeyboardInterrupt:
        print("\nStopping all actors...")
        for _, _, _, proc in procs:
            proc.terminate()
        for _, _, _, proc in procs:
            proc.wait()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PKI Cash Launcher")
    parser.add_argument("--role", choices=["engine", "bank", "wallet"])
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--id", dest="wallet_id", help="wallet identifier (a, b, ...)")
    parser.add_argument("--demo", action="store_true", help="start all four actors")
    args = parser.parse_args()

    if args.demo:
        launch_demo()
    elif args.role:
        launch_single(args.role, args.port, args.wallet_id)
    else:
        parser.print_help()

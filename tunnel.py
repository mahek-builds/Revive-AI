import sys
import subprocess

port = sys.argv[1] if len(sys.argv) > 1 else "5000"

print("=" * 60)
print(f"Launching LocalTunnel on Port {port}...")
print("=" * 60)

try:
    subprocess.run(f"npx localtunnel --port {port}", shell=True, check=True)
except KeyboardInterrupt:
    print("\nTunnel closed.")
except Exception as e:
    print(f"Error starting tunnel: {e}")
# npm run tunnel
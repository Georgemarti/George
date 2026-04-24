"""
Arranca Betta Judge con Python en modo UTF-8 forzado.
Uso: python run.py
"""
import subprocess
import sys
import os

env = os.environ.copy()
env["PYTHONUTF8"] = "1"          # Modo UTF-8 global (Python 3.7+)
env["PYTHONIOENCODING"] = "utf-8" # Fallback para versiones anteriores

result = subprocess.run(
    [sys.executable, "-X", "utf8", "app.py"] + sys.argv[1:],
    env=env,
)
sys.exit(result.returncode)

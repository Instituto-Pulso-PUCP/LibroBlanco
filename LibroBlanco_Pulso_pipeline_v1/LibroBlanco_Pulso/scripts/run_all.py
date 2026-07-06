import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
subprocess.check_call([sys.executable, str(ROOT/'scripts'/'run_pipeline.py')])
subprocess.check_call([sys.executable, str(ROOT/'scripts'/'02_match_candidates.py')])

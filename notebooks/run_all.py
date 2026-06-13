#!/usr/bin/env python
# coding: utf-8
"""
Runner script for all 3 EDA notebooks.
Handles:
- UTF-8 encoding for Arabic characters in the data
- Non-interactive matplotlib backend (Agg) for headless execution
- Suppresses plt.show() calls by monkey-patching
- Disables LaTeX math parsing to avoid $ sign issues
"""
import sys
import os
import io
from pathlib import Path

# Ensure UTF-8 encoding for stdout/stderr (fixes UnicodeEncodeError with Arabic characters)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Set environment variables for non-interactive matplotlib
os.environ['MPLBACKEND'] = 'Agg'
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Suppress plt.show() and disable LaTeX math parsing
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.show = lambda *args, **kwargs: None
plt.rcParams['text.parse_math'] = False

# Add notebooks directory to sys.path for utils import
notebooks_dir = Path(__file__).parent
sys.path.insert(0, str(notebooks_dir))

notebooks = [
    'hotels_eda.py',
    'restaurants_eda.py',
    'attractions_eda.py',
]

results = {}
for nb in notebooks:
    nb_path = notebooks_dir / nb
    print(f"\n{'='*70}")
    print(f"  RUNNING: {nb}")
    print(f"{'='*70}\n")

    try:
        # Execute the notebook as a module
        code = nb_path.read_text(encoding='utf-8')
        # Remove the shebang line and encoding declaration
        code = code.replace('#!/usr/bin/env python\n', '')
        code = code.replace('# coding: utf-8\n', '')

        # Execute in a clean namespace
        namespace = {'__name__': '__main__', '__file__': str(nb_path)}
        exec(compile(code, str(nb_path), 'exec'), namespace)

        results[nb] = 'SUCCESS'
        print(f"\n[OK] {nb} completed successfully.\n")
    except Exception as e:
        results[nb] = f'FAILED: {e}'
        print(f"\n[FAIL] {nb} failed with error: {e}\n")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 70)
print("  SUMMARY")
print("=" * 70)
for nb, status in results.items():
    icon = "[OK]" if status == "SUCCESS" else "[FAIL]"
    print(f"  {icon} {nb}: {status}")
print("=" * 70)

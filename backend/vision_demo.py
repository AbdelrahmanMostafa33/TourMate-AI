"""
Interactive Vision Demo for TourMate AI — analyse travel images from the terminal.

Usage:
    python vision_demo.py                          # Download + analyse a sample beach photo
    python vision_demo.py path/to/photo.jpg        # Analyse your own image
    python vision_demo.py --url <image_url>        # Download + analyse from URL

The script sends the image to Gemini 2.5 Flash via ``invoke_with_fallback``
(key rotation, rate-limit backoff) and prints structured travel preferences.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add current directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.WARNING)

from ai_engine.vision.image_analyzer import analyze_travel_image


# ── Terminal colours (Windows-safe; stripped if not supported) ─────────────

try:
    _ = sys.stdout.encoding
    CYAN    = "\033[36m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    RED     = "\033[31m"
    MAGENTA = "\033[35m"
    DIM     = "\033[2m"
    BOLD    = "\033[1m"
    RESET   = "\033[0m"
except Exception:
    CYAN = GREEN = YELLOW = RED = MAGENTA = DIM = BOLD = RESET = ""

SAMPLE_PYRAMIDS = (
    "https://images.unsplash.com/photo-1643667996984-fcc69743449d?q=80&w=1074&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
    "?w=800&q=80"
)

SAMPLE_BEACH = (
    "https://images.unsplash.com/photo-1507525428034-b723cf961d3e"
    "?w=800&q=80"
)

SAMPLE_CITY = (
    "https://images.unsplash.com/photo-1502602898657-3e91760cbb34"
    "?w=800&q=80"
)

SAMPLE_MOUNTAIN = (
    "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b"
    "?w=800&q=80"
)

SAMPLE_FOOD = (
    "https://images.unsplash.com/photo-1504674900247-0877df9cc836"
    "?w=800&q=80"
)

SAMPLE_NIGHTLIFE = (
    "https://images.unsplash.com/photo-1548659296-8113e316bf50"
    "?w=800&q=80"
)

# ── Sample registry for batch mode ────────────────────────────────────────

SAMPLE_REGISTRY: list[tuple[str, str, str]] = [
    ("beach",     "Beach",      SAMPLE_BEACH),
    ("city",      "City",       SAMPLE_CITY),
    ("mountain",  "Mountain",   SAMPLE_MOUNTAIN),
    ("pyramids",  "Pyramids",   SAMPLE_PYRAMIDS),
    ("food",      "Food",       SAMPLE_FOOD),
    ("nightlife", "Nightlife",  SAMPLE_NIGHTLIFE),
]


def _banner():
    print(f"""
{CYAN}{BOLD}+========================================================+
|           TourMate AI - Vision Analysis Demo              |
|                                                            |
|  Analyses a travel image and extracts structured           |
|  preferences using Gemini 2.5 Flash.                      |
+========================================================+{RESET}
""")


def _summary_line(k: str, v: str, colour: str = CYAN) -> str:
    return f"  {BOLD}{k}:{RESET} {colour}{v}{RESET}"


def _separator(char: str = "-") -> str:
    return f"{DIM}{char * 56}{RESET}"


async def _download_image(url: str, dest: Path) -> bytes:
    """Download an image from *url* and cache it at *dest*."""
    import httpx
    print(f"  {DIM}Downloading from:{RESET} {url}")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return resp.content


async def analyse(image_path: Path) -> None:
    """Load *image_path*, run the vision pipeline, and print results."""
    # ── 1. Load image ──────────────────────────────────────────────────────
    image_bytes = image_path.read_bytes()
    print(f"  {DIM}Loaded:{RESET} {image_path.name} ({len(image_bytes):,} bytes)")

    # ── 2. Run vision pipeline ─────────────────────────────────────────────
    print(f"\n  {YELLOW}Analysing image with Gemini 2.5 Flash...{RESET}")
    result = await analyze_travel_image(image_bytes)

    # ── 3. Print structured JSON output ────────────────────────────────────
    print(f"\n{GREEN}{BOLD}  Extracted Travel Preferences{RESET}")
    _separator()
    print(result.model_dump_json(indent=2))
    _separator()

    # ── 4. Human-friendly summary ─────────────────────────────────────────
    print(f"\n{BOLD}  Summary{RESET}")
    print(_summary_line("Confidence", result.confidence.upper(),
                        GREEN if result.confidence == "high" else YELLOW))
    if result.environment_type:
        print(_summary_line("Environment", result.environment_type))
    if result.activity_style:
        print(_summary_line("Activity",    result.activity_style))
    if result.vibe:
        print(_summary_line("Vibe",        result.vibe, colour=MAGENTA))
    if result.interests:
        print(_summary_line("Interests",   ", ".join(result.interests)))
    print()

    if result.has_signal:
        print(f"  {GREEN}High-confidence signal — these preferences can be merged into the trip profile.{RESET}")
    else:
        print(f"  {YELLOW}Low-confidence signal — the image may not be clearly travel-related.{RESET}")

    # ── 5. Token / cost hint ──────────────────────────────────────────────
    print(f"\n{DIM}  Token usage logged by TokenTracker — run /usage in chat.py to see totals.{RESET}\n")


# ── Batch comparison — run all sample images ───────────────────────────────-


async def run_all():
    """Analyse every sample image and print a side-by-side comparison table."""
    from ai_engine.schemas.vision_schema import VisionFeatures

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  Running vision pipeline on all {len(SAMPLE_REGISTRY)} sample images...{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    results: list[tuple[str, str, VisionFeatures]] = []
    temp_file = Path("_vision_demo_temp.jpg")

    for key, label, url in SAMPLE_REGISTRY:
        print(f"  {YELLOW}[{label}]{RESET} Downloading...", end=" ", flush=True)
        try:
            await _download_image(url, temp_file)
            image_bytes = temp_file.read_bytes()
            print(f"({len(image_bytes):,} bytes) -> Analysing...", end=" ", flush=True)
            result = await analyze_travel_image(image_bytes)
            results.append((key, label, result))
            print(f"{GREEN}done{RESET}")
        except Exception as e:
            print(f"{RED}FAILED:{RESET} {e}")
        finally:
            if temp_file.exists():
                temp_file.unlink()

    # ── Comparison table ───────────────────────────────────────────────────
    print(f"\n{GREEN}{BOLD}{'=' * 72}{RESET}")
    print(f"{GREEN}{BOLD}  COMPARISON TABLE  —  Extracted preferences across all samples{RESET}")
    print(f"{GREEN}{BOLD}{'=' * 72}{RESET}\n")

    # Header row
    header = f"{'Image':<14} {'Conf':<8} {'Environment':<14} {'Activity':<14} {'Interests':<28}"
    print(f"{DIM}{header}{RESET}")
    print(f"{DIM}{'-' * 72}{RESET}")

    for key, label, vf in results:
        conf      = f"{vf.confidence.upper()}" if vf.confidence else "-"
        env       = vf.environment_type or "-"
        activity  = vf.activity_style or "-"
        interests = ", ".join(vf.interests[:3])
        if len(vf.interests) > 3:
            interests += f" +{len(vf.interests) - 3}"
        if not interests:
            interests = "-"

        conf_colour = GREEN if vf.confidence == "high" else (YELLOW if vf.confidence == "medium" else RED)
        print(
            f"  {label:<12}"
            f"{conf_colour}{conf:<8}{RESET}"
            f"{env:<14}"
            f"{activity:<14}"
            f"{interests:<28}"
        )

    print(f"{DIM}{'-' * 72}{RESET}")
    print(f"  Ran {len(results)}/{len(SAMPLE_REGISTRY)} samples successfully.\n")


# ── CLI entry point ────────────────────────────────────────────────────────


async def main():
    _banner()

    # Check API key
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    try:
        from app.core.config import settings
        api_key = api_key or settings.google_api_key
    except Exception:
        pass

    if not api_key:
        print(f"  {RED}No Google API key found.{RESET}")
        print(f"  {DIM}Set GOOGLE_API_KEY in .env or as an environment variable.{RESET}\n")
        return

    args = sys.argv[1:]

    # ── Determine image source ─────────────────────────────────────────────
    image_path: Optional[Path] = None
    temp_file = Path("_vision_demo_temp.jpg")

    if args:
        arg = args[0]
        if arg.startswith("--url=") or arg.startswith("--url "):
            url = arg.split("=", 1)[1] if "=" in arg else args[1]
            print(f"  {DIM}Downloading from provided URL...{RESET}")
            await _download_image(url, temp_file)
            image_path = temp_file
        elif arg in ("--beach", "--sample"):
            print(f"  {DIM}Using sample beach image...{RESET}")
            await _download_image(SAMPLE_BEACH, temp_file)
            image_path = temp_file
        elif arg == "--city":
            print(f"  {DIM}Using sample city image...{RESET}")
            await _download_image(SAMPLE_CITY, temp_file)
            image_path = temp_file
        elif arg == "--mountain":
            print(f"  {DIM}Using sample mountain image...{RESET}")
            await _download_image(SAMPLE_MOUNTAIN, temp_file)
            image_path = temp_file
        elif arg in ("--pyramids", "--historical"):
            print(f"  {DIM}Using sample pyramids image...{RESET}")
            await _download_image(SAMPLE_PYRAMIDS, temp_file)
            image_path = temp_file
        elif arg in ("--food", "--culinary"):
            print(f"  {DIM}Using sample food image...{RESET}")
            await _download_image(SAMPLE_FOOD, temp_file)
            image_path = temp_file
        elif arg in ("--nightlife", "--night"):
            print(f"  {DIM}Using sample nightlife image...{RESET}")
            await _download_image(SAMPLE_NIGHTLIFE, temp_file)
            image_path = temp_file
        elif arg in ("--all", "--compare"):
            await run_all()
            return
        else:
            # Treat as file path
            p = Path(arg)
            if p.exists():
                image_path = p
            else:
                print(f"  {RED}File not found:{RESET} {arg}")
                return

    if image_path is None:
        # Default: download beach sample
        print(f"  {DIM}No image specified — downloading sample beach photo.{RESET}")
        print(f"  {DIM}Pass a file path or one of: --beach, --city, --mountain, --pyramids, --food, --nightlife, --all{RESET}\n")
        await _download_image(SAMPLE_PYRAMIDS, temp_file)
        image_path = temp_file

    try:
        await analyse(image_path)
    finally:
        # Cleanup temp files
        if temp_file.exists():
            temp_file.unlink()


if __name__ == "__main__":
    asyncio.run(main())

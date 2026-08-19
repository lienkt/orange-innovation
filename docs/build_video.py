"""Build the narrated video walkthrough (docs/Orange_Innovation_Radar.mp4).

Three parts, assembled with ffmpeg:

  1. Concept slides   — rendered from the same .pptx, so the deck and the video
                        can never drift apart.
  2. Live demo        — a real browser driven by Playwright against the running
                        app, recorded as video. Nothing is faked or mocked up.
  3. Architecture     — the closing slides.

Narration is Microsoft's `en-US-BrianNeural` via edge-tts.

Synchronisation approach: every narration clip is generated FIRST, so its exact
duration is known. Slide segments are then held for precisely that long, and the
demo script dwells on each step for its own line's duration. That keeps voice
and picture together without hand-tuned sleeps.

Prerequisites: the API on :8000 and the frontend on :5173 must be running, and
docs/build_deck.py must have been run.

    python3 docs/build_video.py
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
WORK = Path("/tmp/vid")
SLIDES = WORK / "slides"
AUDIO = WORK / "audio"
SEG = WORK / "seg"
DEMO = WORK / "demo"
OUT = ROOT / "docs" / "Orange_Innovation_Radar.mp4"

VOICE = "en-US-BrianNeural"
RATE = "-4%"      # a touch slower than default; this is dense material
W, H = 1920, 1080

# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

# (slide number in the rendered PDF, narration)
SLIDE_SCRIPT = [
    (1, "This is the Orange Business Innovation Radar — a working prototype built "
        "against the requirements baseline. It maintains a regularly refreshed view of "
        "specific innovation opportunities, each scored on how attractive it is, how urgent "
        "the window is, and how strong Orange's right to win is."),
    (2, "The problem it solves is not a shortage of information about technology. The "
        "information that exists is generic, undated, unsourced, and disconnected from what "
        "Orange can actually sell. Ay Eye, Cloud and Cybersecurity are rejected as topics. "
        "A real topic reads like this: private five G plus edge vision for safety compliance "
        "in mining. Specific enough to open a customer meeting with."),
    (3, "So an opportunity space is a triple: a vertical, times a use case, times a "
        "technology. The triple is the identity — it gives deduplication and filtering, and "
        "it is what makes a topic recur across refreshes rather than being recreated. The "
        "human readable statement is a rendering of that triple. A candidate that does not "
        "resolve to exactly one of each fails validation automatically."),
    (4, "Every topic carries two scores that are never combined. Attractiveness asks "
        "whether the world is moving, and is computed from external evidence alone. Right to "
        "win asks whether we can play and whether we can win, and is computed from a curated "
        "graph of Orange's offers, references, partners and certifications — as named query "
        "results, never asserted by a language model. Collapsing them would destroy the "
        "information the strategist needs. A third quantity, conviction, captures what our "
        "own people believe, and adjusts ranking without ever touching the other two."),
    (5, "The model never invents a topic out of its own knowledge. Four defences enforce "
        "that. Every claim must cite signal identifiers that exist in the cluster that "
        "produced it, and uncited claims are stripped rather than rewritten. Taxonomy values "
        "are validated against closed vocabularies. No number is ever generated — market "
        "sizes are looked up and attributed, or they are absent. And a second pass checks "
        "each claim is genuinely entailed by the span it cites. On top of that, an "
        "adversarial critic rejected three hundred and forty five of six hundred and forty "
        "four candidates in the live run, with written reasons."),
    (6, "Portfolio distance is the most decision relevant number in the product. It is the "
        "shortest path from a topic to something Orange could actually deliver. L zero means "
        "an existing offer already addresses it — that is a sales conversation. L two needs a "
        "partner. L four is white space, with no plausible path from the current portfolio. "
        "This is what drives the role modes: a high attractiveness L four topic is exactly the "
        "strategist's innovation agenda, and exactly what a salesperson should never be shown."),
    (7, "Here is what the prototype has actually produced, read live from its database. "
        "One hundred and seventy four opportunity spaces, from four and a half thousand "
        "signals gathered across eighteen live sources, joined to two thousand named asset "
        "links. Fourteen of the fifteen verticals are covered, and the corpus carries five "
        "hundred French language signals — so the anglophone bias named as a principal risk "
        "is measured rather than assumed."),
    (8, "Two further questions a topic cannot be acted on without: how big is it, and who "
        "else is already there. Headline market figures in the press come from paid research, "
        "are quoted without methodology, and often conflict by an order of magnitude. So the "
        "radar builds its own estimate bottom up — enterprise counts, times an observed "
        "adoption rate, times a plausible contract value — and shows its working, with a "
        "method and a confidence label attached. Competitive intensity is scored against a "
        "versioned competitor register. A crowded field is not a reason to walk away; it is a "
        "reason to win on a specific differentiator."),
]

CLOSING_SCRIPT = [
    (16, "Architecturally this is seven pipeline stages, each with a defined input and "
         "output contract so they can be developed and replaced independently. Collect, "
         "normalise, classify, cluster into themes, synthesise candidates, enrich them with "
         "further evidence, score, and serve. A parallel slower path maintains the Orange "
         "Business Graph and joins at the scoring stage, so right to win can be improved "
         "without re-running discovery."),
    (17, "The stack is deliberately unremarkable, because the value is in the schema and "
         "the curation rather than the infrastructure. Nineteen connectors feed a signal "
         "store. DeepSeek sits behind a provider agnostic client, so switching to a sovereign "
         "local model is an environment variable rather than a rewrite. Embeddings run "
         "locally. The graph is thousands of nodes, not millions, so SQLite is entirely "
         "adequate. Taxonomies, weights and thresholds are configuration, validated at load "
         "time so a dangling identifier is a startup error rather than a wrong number three "
         "stages later."),
    (18, "That gives six guarantees about the numbers. Every displayed score decomposes "
         "into named components. Every component stores the inputs used to compute it, so any "
         "number can be re-derived. Lineage runs from a displayed claim back to the raw "
         "ingested item. Every score records its weight set, so trajectories are never "
         "plotted across an incomparable boundary. And counting, diversity and momentum are "
         "arithmetic, never a model — because a model asked to count is occasionally wrong "
         "and always unverifiable."),
    (19, "Finally, what is deliberately not built, and what needs a decision from Orange. "
         "There is no CRM integration and no learned scoring model, because no labels exist "
         "on day one — the capture and replay harness ships instead. No market size is shown "
         "at all, rather than a wrong one. And four things need a human: two thousand links "
         "are machine proposed and unconfirmed, there is no agriculture vertical so agri "
         "topics are being forced into four others, terms of use are unconfirmed for ten "
         "sources, and the refresh cadence is still undecided. The radar surfaces its own "
         "gaps rather than hiding them."),
    (20, "The join between an external signal and an internal asset is the product. Without "
         "it this is a competent trend feed, and trend feeds already exist. With it, the radar "
         "answers a question nobody else can answer for Orange."),
]

# Live demo steps. Each is (narration, action-name).
DEMO_SCRIPT = [
    ("Here is the running application. The radar is the signature view. Angular sectors "
     "are the six business domains; distance from the centre is the time horizon, with Now "
     "at the middle and Later at the rim.", "radar_intro"),
    ("Marker size is attractiveness and marker colour is right to win, so the two questions "
     "the radar exists to answer are visible at the same time. A marker with an exclamation "
     "mark carries an evidence gap — Orange has few published references in that vertical.",
     "radar_dwell"),
    ("Switching role changes the ranking function, not just a filter. Sales sees only topics "
     "with a delivery path, a published reference in the vertical, and no evidence gap — "
     "which is why the count drops.", "role_sales"),
    ("The list view shows the same topics ranked for the selected role, with attractiveness, "
     "right to win, horizon, portfolio distance and the number of supporting signals on every "
     "row.", "list_view"),
    ("Opening a topic gives the detail pane. Every claim under why it is hot now is bound to "
     "the signal identifiers that support it, and each chip links out to the original dated "
     "source.", "open_topic"),
    ("Further down, can we play and can we win is itemised against named Orange assets — a "
     "specific offer, a specific certification, a specific partner tier — never an aggregate "
     "assertion that Orange has relevant capabilities.", "scroll_links"),
    ("Now the part that makes the scoring defensible. Every topic has a how was this "
     "calculated modal.", "open_explain"),
    ("It shows the weight table and the weighted total, and then, per component, the actual "
     "stored inputs: the publishers counted and their entropy, the tier distribution, the per "
     "period buckets the momentum slope was fitted to. This is how a reviewer outside the "
     "project can reconstruct why a topic holds its rank.", "explain_expand"),
    ("The workflow board implements the stage gate. A topic moves from shortlisted, through "
     "demand tested and packaged, to live, and ownership follows the stage.", "workflow"),
    ("Each role assesses only the axis it owns — sales rates customer demand, presales rates "
     "deliverability — on a zero to five scale with written anchors, because people are "
     "unreliable at rating something seventy three out of a hundred.", "assess"),
    ("The analytics view visualises the whole corpus. The heatmap is vertical by domain, and "
     "the empty cells are the white space. The diverging chart shows where the team and the "
     "evidence disagree — that is a review queue, because disagreement is information rather "
     "than friction.", "analytics"),
    ("And throughout, every dense concept explains itself, with a pointer back to the "
     "requirement it comes from.", "help"),
]


async def synth(text: str, path: Path, attempts: int = 4) -> None:
    """Speak one line, verifying the result is actually audio.

    edge-tts occasionally returns an empty file when several requests are in
    flight — the call succeeds and writes nothing. A zero-byte clip then fails
    much later, at the probe step, after the whole narration set has been
    generated. Verifying here turns a ten-minute-later crash into a retry.
    """
    clean = text.replace("—", ",").replace("·", ",")
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            await edge_tts.Communicate(clean, VOICE, rate=RATE).save(str(path))
            # Size alone is not enough: a truncated clip can be 100 KB and still
            # be unreadable. Probing is the only check that means anything.
            if path.exists() and path.stat().st_size > 2048 and _probe_ok(path):
                return
            last = RuntimeError(f"unreadable audio ({path.stat().st_size if path.exists() else 0} bytes)")
        except Exception as exc:  # noqa: BLE001 — the service is the flaky part
            last = exc
        await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"TTS failed for {path.name} after {attempts} attempts: {last}")


def _probe_ok(path: Path) -> bool:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).returncode == 0


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


async def build_narration() -> dict[str, float]:
    AUDIO.mkdir(parents=True, exist_ok=True)
    jobs = []
    for num, line in SLIDE_SCRIPT + CLOSING_SCRIPT:
        jobs.append((f"slide{num:02d}", line))
    for i, (line, _) in enumerate(DEMO_SCRIPT):
        jobs.append((f"demo{i:02d}", line))

    # edge-tts is a network round trip per clip; run them concurrently.
    async def one(key: str, line: str):
        await synth(line, AUDIO / f"{key}.mp3")
        return key

    sem = asyncio.Semaphore(3)

    async def guarded(key, line):
        async with sem:
            return await one(key, line)

    await asyncio.gather(*(guarded(k, l) for k, l in jobs))
    durations = {k: duration(AUDIO / f"{k}.mp3") for k, _ in jobs}
    (WORK / "durations.json").write_text(json.dumps(durations, indent=1))
    print(f"narrated {len(durations)} clips, "
          f"{sum(durations.values()):.0f}s total")
    return durations


def slide_segment(slide_num: int, audio: Path, out: Path) -> None:
    """One still slide held for exactly the length of its narration."""
    img = SLIDES / f"slide-{slide_num:02d}.png"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(img),
        "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,fps=30",
        "-c:a", "aac", "-b:a", "160k", "-shortest",
        str(out),
    ], check=True)


def record_demo(durations: dict[str, float]) -> Path:
    """Drive the real app with Playwright and record it.

    Each step dwells for its own narration length, so the recording lines up
    with the voice track without any manual timing.
    """
    from playwright.sync_api import sync_playwright

    DEMO.mkdir(parents=True, exist_ok=True)
    for stale in DEMO.glob("*.webm"):
        stale.unlink()

    pause = [durations[f"demo{i:02d}"] for i in range(len(DEMO_SCRIPT))]
    # Cumulative targets. Holding for each narration length INDEPENDENTLY drifts,
    # because the interactions between steps take real time the narration does
    # not account for — the first run recorded 198 seconds of video against 146
    # seconds of speech, so the closing visuals were truncated and the last lines
    # played over the wrong screen. Waiting until a running total instead keeps
    # every line on top of its own view.
    targets = []
    running = 0.0
    for d in pause:
        running += d
        targets.append(running)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-device-scale-factor=1"])
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 900},
            record_video_dir=str(DEMO), record_video_size={"width": 1600, "height": 900},
        )
        page = ctx.new_page()

        started = time.monotonic()

        def hold(step: int):
            """Wait until this step's narration would have finished."""
            remaining = targets[step] - (time.monotonic() - started)
            if remaining > 0:
                page.wait_for_timeout(int(remaining * 1000))
            else:
                print(f"  demo: step {step} ran {abs(remaining):.1f}s over its narration")

        # The header has both a view switcher and a skip-navigation landmark
        # that repeat the same words, so every control is scoped to its group.
        def tab(name: str):
            try:
                page.get_by_label("View").get_by_role("button", name=name, exact=True).click()
                page.wait_for_timeout(400)
            except Exception as exc:  # noqa: BLE001
                print(f"  demo: could not open tab {name!r}: {exc}")

        def role_mode(name: str):
            try:
                page.get_by_label("Role mode").get_by_role("button", name=name).first.click()
                page.wait_for_timeout(400)
            except Exception as exc:  # noqa: BLE001
                print(f"  demo: could not switch role {name!r}: {exc}")

        def safe(fn, what: str):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                print(f"  demo: skipped {what}: {exc}")

        # 0-1 radar
        page.goto("http://localhost:5173/?tab=radar", wait_until="networkidle")
        page.wait_for_timeout(2500)
        hold(0)
        # hover a marker so the tooltip shows
        try:
            page.locator("circle.dot").nth(3).hover()
        except Exception:
            pass
        hold(1)

        # 2 role switch
        role_mode("Sales")
        page.wait_for_timeout(1200)
        hold(2)

        # 3 list
        tab("List")
        page.wait_for_timeout(1200)
        hold(3)

        # 4 open a topic
        safe(lambda: page.locator(".topic-row").first.click(), "open topic")
        page.wait_for_timeout(1500)
        hold(4)

        # 5 scroll the detail pane to the linked assets
        try:
            page.locator("text=Can we play, can we win").first.scroll_into_view_if_needed()
        except Exception:
            pass
        page.wait_for_timeout(900)
        hold(5)

        # 6-7 score explanation
        safe(lambda: page.locator(".topic-row .help-btn").first.click(), "open explain modal")
        page.wait_for_timeout(1500)
        hold(6)
        try:
            page.locator(".se-detail summary").first.click()
            page.wait_for_timeout(700)
            page.locator(".se-detail").nth(1).scroll_into_view_if_needed()
        except Exception:
            pass
        hold(7)
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)

        # 8 workflow
        tab("Workflow")
        page.wait_for_timeout(1600)
        hold(8)

        # 9 assessment widget
        try:
            page.locator(".board-card").first.click()
            page.wait_for_timeout(1200)
            page.locator("text=Your assessment").first.scroll_into_view_if_needed()
            page.wait_for_timeout(700)
            page.locator(".rating button").nth(4).hover()
        except Exception:
            pass
        hold(9)

        # 10 analytics
        tab("Analytics")
        page.wait_for_timeout(2200)
        hold(10)

        # 11 help modal
        tab("Radar")
        page.wait_for_timeout(1200)
        try:
            page.locator('button[aria-label^="Help:"]').first.click()
            page.wait_for_timeout(800)
        except Exception:
            pass
        hold(11)

        ctx.close()
        browser.close()

    videos = list(DEMO.glob("*.webm"))
    if not videos:
        raise RuntimeError("Playwright produced no recording")
    print(f"recorded demo: {videos[0].name} ({duration(videos[0]):.1f}s)")
    return videos[0]


def build_demo_segment(video: Path, durations: dict[str, float], out: Path) -> None:
    """Mux the recording with its concatenated narration."""
    listing = WORK / "demo_audio.txt"
    listing.write_text("\n".join(
        f"file '{AUDIO / f'demo{i:02d}.mp3'}'" for i in range(len(DEMO_SCRIPT))))
    demo_audio = WORK / "demo_audio.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", str(demo_audio)], check=True)

    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video), "-i", str(demo_audio),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,fps=30",
        "-c:a", "aac", "-b:a", "160k", "-shortest",
        str(out),
    ], check=True)


def main() -> int:
    for needed in (SLIDES / "slide-01.png",):
        if not needed.exists():
            print("Run docs/build_deck.py first (and render the slides).", file=sys.stderr)
            return 1

    SEG.mkdir(parents=True, exist_ok=True)
    for stale in SEG.glob("*.mp4"):
        stale.unlink()

    durations = asyncio.run(build_narration())

    segments: list[Path] = []
    for num, _ in SLIDE_SCRIPT:
        out = SEG / f"a{num:02d}.mp4"
        slide_segment(num, AUDIO / f"slide{num:02d}.mp3", out)
        segments.append(out)
        print("slide segment", num)

    demo_video = record_demo(durations)
    demo_seg = SEG / "demo.mp4"
    build_demo_segment(demo_video, durations, demo_seg)
    segments.append(demo_seg)
    print("demo segment built")

    for num, _ in CLOSING_SCRIPT:
        out = SEG / f"z{num:02d}.mp4"
        slide_segment(num, AUDIO / f"slide{num:02d}.mp3", out)
        segments.append(out)
        print("slide segment", num)

    listing = WORK / "segments.txt"
    listing.write_text("\n".join(f"file '{s}'" for s in segments))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", str(listing), "-c:v", "libx264", "-crf", "21", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(OUT),
    ], check=True)
    (WORK / "DONE").write_text(str(OUT))
    print(f"\nwrote {OUT}  ({duration(OUT)/60:.1f} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

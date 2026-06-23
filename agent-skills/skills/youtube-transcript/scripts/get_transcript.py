# /// script
# requires-python = ">=3.10"
# dependencies = ["youtube-transcript-api>=1.0.0"]
# ///
"""get_transcript.py - free YouTube transcript extractor.

Faithful rebuild of the youtube-transcript skill's extraction script. Matches the
interface consumed by chainaim-deep-research/extract/youtube.py:

    uv run get_transcript.py "<url_or_id>" [--timestamps] [--lang en,hi]

  - transcript goes to STDOUT, one caption segment per line
      * plain text by default (matches the existing kb/full/*.txt format)
      * "[MM:SS] text" when --timestamps is given
  - on failure: "Error: <message>" to STDERR and exit code 1

No API key required. The PEP 723 header above lets `uv run` auto-install
youtube-transcript-api into an ephemeral environment on first call.

Behaviour is configurable via flags (sensible defaults), so nothing is hardcoded:
  --timestamps   prefix each line with [MM:SS]            (default: off)
  --lang LIST    comma-separated language priority         (default: "en")
  --no-fallback  do NOT fall back to any available language if the
                 preferred languages are missing           (default: fallback on)
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import List, Tuple

# Accepts the common YouTube URL shapes plus a bare 11-char id.
_URL_ID = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|"
    r"youtube\.com/v/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})"
)
_QUERY_V = re.compile(r"[?&]v=([A-Za-z0-9_-]{11})")
_BARE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(source: str) -> str:
    """Pull the 11-char video id out of a URL or accept a bare id. Raises ValueError."""
    s = source.strip()
    for pat in (_URL_ID, _QUERY_V):
        m = pat.search(s)
        if m:
            return m.group(1)
    if _BARE_ID.match(s):
        return s
    raise ValueError(f"could not parse a YouTube video id from: {source!r}")


def _snippets_new(video_id: str, languages: List[str], fallback: bool) -> List[Tuple[str, float]]:
    """youtube-transcript-api >= 1.0 instance API. Returns [(text, start_seconds), ...]."""
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=languages)
        return [(sn.text, float(getattr(sn, "start", 0.0))) for sn in fetched]
    except Exception:
        if not fallback:
            raise
        # Fall back to whatever transcript the video does have.
        transcript_list = api.list(video_id)
        transcript = next(iter(transcript_list))
        fetched = transcript.fetch()
        return [(sn.text, float(getattr(sn, "start", 0.0))) for sn in fetched]


def _snippets_legacy(video_id: str, languages: List[str]) -> List[Tuple[str, float]]:
    """Pre-1.0 static API fallback. Returns [(text, start_seconds), ...]."""
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore

    raw = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)  # type: ignore[attr-defined]
    return [(d["text"], float(d.get("start", 0.0))) for d in raw]


def get_snippets(video_id: str, languages: List[str], fallback: bool) -> List[Tuple[str, float]]:
    """Version-tolerant fetch: try the modern API, then the legacy one."""
    from youtube_transcript_api import YouTubeTranscriptApi

    if hasattr(YouTubeTranscriptApi, "fetch") or hasattr(YouTubeTranscriptApi(), "fetch"):
        return _snippets_new(video_id, languages, fallback)
    return _snippets_legacy(video_id, languages)


def fmt_timestamp(start_seconds: float) -> str:
    total = int(start_seconds)
    return f"[{total // 60:02d}:{total % 60:02d}]"


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="get_transcript.py",
        description="Extract a YouTube transcript to stdout (no API key required).",
    )
    parser.add_argument("source", help="YouTube URL or bare 11-char video id")
    parser.add_argument("--timestamps", action="store_true",
                        help="prefix each line with [MM:SS]")
    parser.add_argument("--lang", default="en",
                        help='comma-separated language priority (default: "en")')
    parser.add_argument("--no-fallback", dest="fallback", action="store_false",
                        help="do not fall back to any available language")
    args = parser.parse_args(argv)

    try:
        video_id = extract_video_id(args.source)
        languages = [s.strip() for s in args.lang.split(",") if s.strip()] or ["en"]
        snippets = get_snippets(video_id, languages, args.fallback)
    except Exception as exc:  # noqa: BLE001 - report any failure on stderr, exit 1
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not snippets:
        print("Error: empty transcript (video may lack captions)", file=sys.stderr)
        return 1

    out = sys.stdout
    for text, start in snippets:
        line = f"{fmt_timestamp(start)} {text}" if args.timestamps else text
        out.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

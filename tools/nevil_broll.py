"""Nevil b-roll flow: LLM decoupage -> per-scene Nano Banana prompts pinned to the
real audio timeline -> you drop images/clips -> assemble with smooth zoom + subtitles.

Two commands:

  plan  --audio narration.mp3 --theme "..." --out DIR
        whisper-times the narration, asks the LLM to group the real cues into
        visual scenes and write a detailed prompt for each, then writes
        DIR/flowchart.md (copy-paste prompts + the exact timeframe each image
        must cover) and DIR/scenes.json. Timing comes from the actual audio, so
        every image lands congruent with the narration.

  build --dir DIR --out final.mp4
        reads DIR/scenes.json + DIR/images/NN.* (image => Ken Burns zoom for the
        scene's duration; video => used as-is, so avatar clips drop in later with
        no code change), concatenates in order, then burns subtitles and muxes
        the narration via the app's own generate_video.

Runs inside the webui container (has config, whisper, moviepy, the LLM provider).
"""
import argparse
import json
import os

import numpy as np
from PIL import Image
from loguru import logger
from moviepy import AudioFileClip, VideoClip, VideoFileClip, concatenate_videoclips

from app.config import config
from app.models.schema import VideoParams, VideoAspect
from app.services import llm, subtitle, video
from app.services.video import close_clip
from app.utils import utils

W, H = 1920, 1080
ZOOM = 1.12  # gentle Ken Burns zoom-in per still
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv")


# ----------------------------------------------------------------------------- plan

def _srt_time_to_sec(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _load_segments(audio_file: str, srt_file: str) -> list[dict]:
    if not os.path.isfile(srt_file):
        logger.info(f"transcribing {audio_file} -> {srt_file}")
        subtitle.create(audio_file=audio_file, subtitle_file=srt_file)
    segs = []
    for idx, times, text in subtitle.file_to_subtitles(srt_file):
        start_s, end_s = [t.strip() for t in times.split("-->")]
        segs.append(
            {"i": idx, "start": _srt_time_to_sec(start_s), "end": _srt_time_to_sec(end_s), "text": text}
        )
    if not segs:
        raise SystemExit("no subtitle cues produced from audio")
    return segs


# The decoupage system prompt is the nevil-image-prompts skill's canonical spec.
# Reading it at runtime keeps the skill as the single source of truth, so editing
# the skill retunes every episode's image prompts with no code change here.
_DECOUPAGE_SKILL = ".claude/skills/nevil-image-prompts/decoupage_prompt.md"


def _decoupage_prompt(target_secs: float) -> str:
    path = os.path.join(utils.root_dir(), _DECOUPAGE_SKILL)
    with open(path, encoding="utf-8") as f:
        return f.read().replace("<<TARGET>>", f"{target_secs:g}")


def _tile(starts: list[float], audio_dur: float) -> list[tuple[float, float]]:
    """Each still holds from its own narration start until the NEXT still's
    narration start; the last one fills to the end of the audio. This tiles
    [0, audio_dur] with no gaps, so stills never drift ahead of the voice and the
    video never ends before the audio (the black-tail bug). Using cue-group END
    times instead would leave the inter-scene silence uncovered and accumulate
    drift."""
    starts = [0.0] + list(starts[1:])  # first image opens the video
    return [
        (starts[i], starts[i + 1] if i + 1 < len(starts) else audio_dur)
        for i in range(len(starts))
    ]


def _coerce_plan(raw: str) -> dict:
    txt = llm._strip_code_fence(raw).strip()
    # tolerate any leading/trailing prose the model may add
    a, b = txt.find("{"), txt.rfind("}")
    if a == -1 or b == -1:
        raise SystemExit(f"LLM did not return JSON:\n{raw[:500]}")
    return json.loads(txt[a : b + 1])


def _normalize_scenes(scenes: list[dict], n: int) -> list[dict]:
    """Force contiguous full coverage of cues 1..n regardless of LLM slips."""
    scenes = sorted(scenes, key=lambda s: int(s["first"]))
    out, cursor = [], 1
    for s in scenes:
        first, last = max(int(s["first"]), cursor), int(s["last"])
        if last < first:
            continue
        out.append({"first": cursor, "last": last, "prompt": s["prompt"].strip()})
        cursor = last + 1
    if not out:
        raise SystemExit("LLM returned no usable scenes")
    if out[-1]["last"] < n:  # cover any tail the model dropped
        out[-1]["last"] = n
    out[-1]["last"] = min(out[-1]["last"], n)
    return out


def cmd_plan(args):
    os.makedirs(args.out, exist_ok=True)
    srt_file = args.srt or os.path.join(args.out, "narration.srt")
    segs = _load_segments(args.audio, srt_file)
    n = len(segs)
    logger.info(f"{n} cues, {segs[-1]['end']:.1f}s of audio")

    cue_lines = "\n".join(f'#{s["i"]} [{s["start"]:.1f}-{s["end"]:.1f}] {s["text"]}' for s in segs)
    prompt = (
        _decoupage_prompt(args.target_secs)
        + f"\n\n# Theme / channel style:\n{args.theme}\n\n# Narration cues:\n{cue_lines}"
    )
    logger.info("asking LLM to decoupage the narration...")
    plan = _coerce_plan(llm._generate_response(prompt=prompt))
    scenes = _normalize_scenes(plan["scenes"], n)

    by_i = {s["i"]: s for s in segs}
    audio_clip = AudioFileClip(args.audio)
    audio_dur = audio_clip.duration
    audio_clip.close()
    spans = _tile([by_i[sc["first"]]["start"] for sc in scenes], audio_dur)
    resolved = [
        {"n": k, "start": round(start, 2), "end": round(end, 2),
         "dur": round(end - start, 2), "type": "still", "prompt": sc["prompt"]}
        for k, (sc, (start, end)) in enumerate(zip(scenes, spans), 1)
    ]

    doc = {
        "audio": os.path.abspath(args.audio), "srt": os.path.abspath(srt_file),
        "width": W, "height": H, "style_base": plan.get("style_base", "").strip(),
        "negative": plan.get("negative", "").strip(), "scenes": resolved,
    }
    with open(os.path.join(args.out, "scenes.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    _write_flowchart(args.out, doc)
    logger.success(
        f"{len(resolved)} scenes, {resolved[-1]['end']:.1f}s covered. "
        f"Wrote {args.out}/flowchart.md and scenes.json. "
        f"Drop images as {args.out}/images/01.png .. {len(resolved):02d}.png"
    )


def _write_flowchart(out_dir: str, doc: dict):
    lines = [
        "# Fluxograma de b-roll — gere cada imagem e salve com o número indicado",
        "",
        "Cole o STYLE BASE no início de cada prompt (já embutido abaixo) e o NEGATIVE no campo negative.",
        f"Salve cada imagem em `images/NN.png` (ou .jpg). Quando tiver todas, rode o `build`.",
        "",
        f"**STYLE BASE:** {doc['style_base']}",
        "",
        f"**NEGATIVE:** {doc['negative']}",
        "",
        "---",
        "",
    ]
    for s in doc["scenes"]:
        lines += [
            f"## Cena {s['n']:02d} — [{s['start']:.1f}s → {s['end']:.1f}s] ({s['dur']:.1f}s)",
            f"Salvar como: `images/{s['n']:02d}.png`",
            "",
            "```",
            f"{doc['style_base']} {s['prompt']}",
            "```",
            "",
        ]
    with open(os.path.join(out_dir, "flowchart.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------- build

def _cover(im: Image.Image, tw: int, th: int) -> Image.Image:
    w, h = im.size
    s = max(tw / w, th / h)
    nw, nh = round(w * s), round(h * s)
    im = im.resize((nw, nh), Image.LANCZOS)
    l, t = (nw - tw) // 2, (nh - th) // 2
    return im.crop((l, t, l + tw, t + th))


def _still_clip(path: str, dur: float) -> VideoClip:
    """Smooth sub-pixel Ken Burns zoom (no per-frame integer-position jitter)."""
    bw, bh = round(W * ZOOM), round(H * ZOOM)
    base = _cover(Image.open(path).convert("RGB"), bw, bh)

    def make_frame(t):
        p = min(t / dur, 1.0) if dur else 0.0
        vw, vh = bw * (1 - (1 - 1 / ZOOM) * p), bh * (1 - (1 - 1 / ZOOM) * p)
        a, e = vw / W, vh / H
        c, f = (bw - vw) / 2.0, (bh - vh) / 2.0
        return np.asarray(base.transform((W, H), Image.AFFINE, (a, 0, c, 0, e, f), resample=Image.BICUBIC))

    return VideoClip(make_frame, duration=dur)


def _video_clip(path: str, dur: float) -> VideoClip:
    # A dropped-in clip (e.g. an avatar take) is fit-covered to the canvas and
    # trimmed to the scene length. ponytail: if the clip is shorter than the beat
    # it just ends early; match clip length to the beat when generating avatars.
    clip = VideoFileClip(path)
    fitted = video._fit_clip_to_canvas(clip, target_width=W, target_height=H, fit_mode=video.VideoFitMode.cover)
    return fitted.subclipped(0, min(dur, fitted.duration))


def _find_slot(images_dir: str, n: int) -> str:
    for ext in IMAGE_EXTS + VIDEO_EXTS:
        for name in (f"{n:02d}{ext}", f"{n}{ext}"):
            p = os.path.join(images_dir, name)
            if os.path.isfile(p):
                return p
    return ""


def cmd_build(args):
    with open(os.path.join(args.dir, "scenes.json"), encoding="utf-8") as f:
        doc = json.load(f)
    images_dir = args.images or os.path.join(args.dir, "images")

    missing = [s["n"] for s in doc["scenes"] if not _find_slot(images_dir, s["n"])]
    if missing:
        raise SystemExit(f"missing images for scenes: {missing} (looked in {images_dir})")

    clips = []
    for s in doc["scenes"]:
        path = _find_slot(images_dir, s["n"])
        is_video = path.lower().endswith(VIDEO_EXTS)
        clips.append(_video_clip(path, s["dur"]) if is_video else _still_clip(path, s["dur"]))
        logger.info(f"scene {s['n']:02d} {'video' if is_video else 'still'} {s['dur']:.1f}s <- {os.path.basename(path)}")

    combined = os.path.join(args.dir, "combined.mp4")
    reel = concatenate_videoclips(clips, method="chain")
    try:
        reel.write_videofile(combined, fps=30, codec="libx264", audio=False, threads=4, logger="bar")
    finally:
        close_clip(reel)
        for c in clips:
            close_clip(c)

    # Reuse the app's burn-subtitles + mux + (optional) bgm path so styling matches.
    params = VideoParams(video_subject="nevil")
    params.video_aspect = VideoAspect.landscape.value
    params.bgm_type = ""  # no background music (user disliked the random pool)
    params.subtitle_enabled = not args.no_subtitles
    for fld in ("font_name", "font_size", "text_fore_color", "stroke_color",
                "stroke_width", "subtitle_position", "custom_position"):
        val = config.ui.get(fld)
        if val is not None:
            setattr(params, fld, val)

    video.generate_video(
        video_path=combined, audio_path=doc["audio"],
        subtitle_path=doc["srt"], output_file=args.out, params=params,
    )
    logger.success(f"done -> {args.out}")


# ----------------------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(description="Nevil b-roll decoupage + assembler")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="narration -> scene prompts + timeframes")
    p.add_argument("--audio", required=True)
    p.add_argument("--theme", required=True, help="channel/episode visual theme")
    p.add_argument("--out", required=True, help="output dir for flowchart.md + scenes.json")
    p.add_argument("--srt", default="", help="reuse an existing srt instead of transcribing")
    p.add_argument("--target-secs", type=float, default=8.0)
    p.set_defaults(func=cmd_plan)

    b = sub.add_parser("build", help="images + scenes.json -> final video")
    b.add_argument("--dir", required=True, help="dir with scenes.json (and images/)")
    b.add_argument("--images", default="", help="override images dir")
    b.add_argument("--out", required=True)
    b.add_argument("--no-subtitles", action="store_true")
    b.set_defaults(func=cmd_build)

    sub.add_parser("selfcheck", help="assert the tiling logic").set_defaults(func=cmd_selfcheck)

    args = ap.parse_args()
    args.func(args)


def cmd_selfcheck(args):
    spans = _tile([0.0, 7.0, 15.5, 30.0], 40.0)  # 4 scenes over 40s of audio
    assert spans[0][0] == 0.0, "first still must open the video at 0"
    assert spans[-1][1] == 40.0, "last still must reach the audio end (no black tail)"
    for i in range(len(spans) - 1):
        assert spans[i][1] == spans[i + 1][0], f"gap/overlap at scene {i + 1}"
    covered = sum(e - s for s, e in spans)
    assert abs(covered - 40.0) < 1e-9, f"reel {covered}s must equal audio 40.0s"
    print("selfcheck OK:", spans)


if __name__ == "__main__":
    main()

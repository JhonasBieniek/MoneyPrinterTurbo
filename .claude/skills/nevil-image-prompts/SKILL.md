---
name: nevil-image-prompts
description: >-
  Turns a Nevil episode's narration (script + timed audio) into ultra-detailed,
  per-scene Nano Banana image prompts with a continuity bible and strict
  congruence to what is being said in each scene. Use this whenever you are
  generating b-roll image prompts for the Nevil channel, running the `plan`
  command of tools/nevil_broll.py, deciding how a narration should be cut into
  still images, or improving the quality/coherence of the generated image
  prompts. The canonical prompt spec lives in decoupage_prompt.md and is the
  single source the pipeline sends to the LLM — edit it here to change how every
  episode's images are prompted.
---

# Nevil image-prompt generation

This skill defines how a Nevil narration becomes a set of image prompts for
Nano Banana (text-to-image), one per visual scene, that a human pastes to
generate stills. It is the second half of the Nevil b-roll flow:

```
script → ElevenLabs narration (.mp3) → [plan] whisper timing + decoupage → flowchart.md (prompts + timeframes) → human generates stills → [build] zoom + concat + subtitles → video
```

## The canonical prompt is decoupage_prompt.md

`decoupage_prompt.md` (next to this file) is the exact system prompt sent to the
LLM. **It is the single source of truth** — `tools/nevil_broll.py plan` reads
this file at runtime, so editing it changes the image prompts for every future
episode with no code change. `<<TARGET>>` is substituted with the target
seconds-per-scene at runtime; leave that token in place.

To tune image quality (more people, tighter congruence, a different palette,
different shot grammar), edit `decoupage_prompt.md`, not the Python.

## Why the rules are the way they are

- **Timeframes are not the LLM's job.** Durations come from the real audio: the
  assembler makes each image hold from its first spoken cue until the next
  scene's first cue, tiling the whole timeline. So the model only chooses cut
  points; if it also guessed durations they would fight the audio and the
  stills would drift out of sync. Keep that responsibility out of the prompt.
- **Congruence is the thing that breaks first.** The most common failure is an
  image that looks nice but shows something the narration is not talking about
  right then (e.g. a handwritten letter during a line about a wireless signal).
  That is why congruence is stated as the top rule — an image the viewer can't
  connect to the current sentence reads as a stock-footage mismatch and kills
  the documentary feel.
- **Self-contained prompts + a shared style base** give scene-to-scene
  consistency without the generator "remembering" anything between images.

## Running it

Inside the webui container (paths are container paths; on Windows host bash use
`MSYS_NO_PATHCONV=1`):

```bash
python -m tools.nevil_broll plan --audio <narration.mp3> --theme "<episode visual theme>" --out <dir>
```

Outputs `<dir>/flowchart.md` (copy-paste prompts, each with its timeframe and
the `images/NN.png` filename to save it as) and `<dir>/scenes.json`. See the
`nevil-script` skill for producing the narration this consumes.

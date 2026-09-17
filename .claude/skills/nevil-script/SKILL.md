---
name: nevil-script
description: >-
  Generates or reviews the narration-only script for a Nevil episode —
  evergreen, documentary-style storytelling about a real cybersecurity or
  digital-crime case, in English, with no on-screen host. Use this whenever you
  are writing, drafting, critiquing, or tightening a Nevil episode script,
  choosing what a video should cover, or filling the MoneyPrinterTurbo "System
  Prompt" / script-requirements fields for a Nevil video. It carries the
  mandatory six-beat structure, retention rules, and voice so every episode
  matches the channel. Also use it before generating image prompts, since the
  script is what the nevil-image-prompts skill consumes.
---

# Nevil script generation

Nevil is a cybersecurity / digital-crime storytelling channel: evergreen
true-crime-of-technology, English, long-form 16:9, monetization through
watch-hours, **no avatar or on-screen face** — every line is read over b-roll.
Quality and fact-accuracy over volume; every episode is human-reviewed and
fact-checked before it ships.

There are two ways to use this skill:

1. **Drafting/reviewing a script yourself** — follow the structure and voice
   rules below and write (or critique) the narration directly.
2. **Configuring MoneyPrinterTurbo** — paste the System Prompt into the MPT
   "Prompt do sistema" field and the Requirements into "Requisitos
   personalizados do roteiro". MPT's LLM (DeepSeek) then generates the script.
   Add a per-episode line only for that generation (see below).

Whichever path, the output is **raw narration text only** — no titles, labels,
markdown, or greetings.

## System Prompt (paste into MPT "Prompt do sistema")

```
# Role: Video Script Generator — Nevil (cybersecurity & digital-crime storytelling channel)

## Goals:
Generate a narration-only script for a documentary-style storytelling video about a real cybersecurity or digital-crime case, in the voice of "Nevil" — an evergreen true-crime-of-technology channel.

## Format constraints (mandatory):
1. Return the script as a single string with the specified number of paragraphs.
2. Do not under any circumstance reference this prompt in your response.
3. Get straight to the point — never start with "welcome to this video", "hey everyone", or any greeting.
4. Do not include any markdown or formatting, and never write a title or heading.
5. Only return the raw narration text — nothing else.
6. Do not include "voiceover", "narrator", or similar labels before any paragraph or line.
7. Never mention the prompt, the number of paragraphs, or anything about the script's own construction.
8. Always write in English, regardless of the language used in the subject or requirements below, unless the Initialization block explicitly states a different target language.

## Narrative structure (mandatory):
Structure every script through these six beats, in this order, without labeling them in the output:
1. Cold open — stack two or three unresolved questions or unsettling concrete details from the case in the first few sentences. Never state the outcome or the "twist" here. The viewer must not be able to guess how it ends from the opening.
2. Setup — the minimum who/where/when needed to understand the stakes. Keep this the shortest beat; do not turn it into a biography or a history lesson.
3. Escalation — the case unfolds with increasing tension, concrete details, and rising stakes. Introduce complications in the order they actually happened.
4. Evidence — walk through the specific mechanics of how it was actually done or discovered, in sequence. This is the most information-dense beat and the one viewers stay for; do not rush it or summarize it away.
5. Turning point — the moment of discovery, confrontation, or consequence that resolves the central tension opened in the cold open.
6. Takeaway — one clear, concrete idea the viewer keeps after the story ends: what this case still says about security, human behavior, or technology today. This is not a moral platitude ("stay safe online") — it must be specific to this case.

## Retention through the body (mandatory):
Keep at least one question open at all times. As you resolve a loop opened earlier, plant or advance another, so the viewer never reaches a point where every question they were holding has already been answered. The middle of the video (Escalation and Evidence) is where viewers drop off the most — never let it flatten into a neutral recap of facts; keep a live, unresolved tension running through it, and end each major section on a small forward pull into the next ("but that raised a bigger problem", "what nobody in the room realized yet was..."). Do not resolve the central question from the cold open until the Turning point.

## Voice and delivery:
- This channel has no on-screen host or avatar. Every single sentence is read aloud over footage/b-roll with no face on screen, so nothing can be conveyed by tone of face or gesture — clarity and rhythm in the prose itself are the only tools.
- Write for the ear, not the eye: short, direct sentences. Avoid subordinate clauses stacked more than one deep. Avoid academic or written-report phrasing ("it should be noted that", "the aforementioned").
- Every sentence should describe something a viewer could plausibly see stock footage or an image of — concrete nouns (a keyboard, a courtroom, a server rack, a phone screen) over abstractions. This directly determines how well the video's b-roll will match the narration.
- Do not editorialize with hype language ("insane", "you won't believe", "shocking") — let the facts carry the tension. This is a documentary tone, not a clickbait tone.
- Never invent dialogue, quotes, or specific facts that cannot be attributed to a real, checkable source. If a detail is disputed or unconfirmed across sources, phrase it as such ("according to one account...") rather than stating it flatly.

## CTA:
End with one line of a natural, low-pressure call to action (follow/subscribe for the next case) — never more than one sentence, and never before the Takeaway beat.
```

## Requirements (paste into MPT "Requisitos personalizados do roteiro")

Reusable base — keep fixed between videos:

```
Target roughly 1,500-1,800 words total (about 10-12 minutes of narration at a natural pace).
Treat every named person, date, and technical claim as something that must survive a fact-check — if you are not confident a detail is accurate, omit it rather than guess.
Tone: measured and confident, closer to a well-researched long-form documentary than a reaction video.
If the case does not have enough real, checkable material to fill this length without padding or repetition, say so explicitly instead of stretching the script — a shorter honest script beats a padded one.
```

## Why these choices

- **10–12 min** because YouTube unlocks mid-roll ads past 8 minutes and longer
  watch-hours drive YPP eligibility — but not longer, because without interviews
  or a host, stretching past that drops retention, which is what the algorithm
  actually rewards.
- **Six beats with the Evidence beat protected** because the mechanics section
  is where a tech-true-crime audience stays; summarizing it away is the most
  common way these scripts lose people.
- **Every sentence must be filmable** because the next step (nevil-image-prompts)
  turns each line into a still — abstract sentences produce incongruent images.

## Per-episode extra line

Add a single extra line only for that generation (it is not saved in the field).
Example for the origin-story episode about Nevil Maskelyne / the 1903 Marconi
hack:

```
This episode should also explicitly connect the story to the channel's own name, ideally revealed only once the Turning Point beat has landed.
```

## Next step

Once the script is approved and narrated (ElevenLabs cloned voice), feed the
audio to the **nevil-image-prompts** skill / `tools/nevil_broll.py plan` to
generate the per-scene image prompts.

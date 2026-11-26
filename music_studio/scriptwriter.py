import json
import random
from typing import Dict
from app.config import get_settings

VIRAL_MYSTERY_STORIES = [
    {
        "artist": "Space Mystery",
        "song_title": "Falling Into Jupiter",
        "hook": "What actually happens if you fall into Jupiter? It's terrifying.",
        "scenes": [
            {
                "visual_prompt": "cinematic astronaut falling from space toward giant swirling orange and white clouds of jupiter, dramatic cosmic lighting, ultra realistic 8k",
                "narration": "If you jumped out of a spaceship above Jupiter, you would fall at over one hundred thousand miles per hour.",
            },
            {
                "visual_prompt": "dark terrifying storm clouds inside jupiter with massive blue lightning bolts, cinematic sci fi atmosphere, hyper detailed",
                "narration": "Unlike Earth, Jupiter has no solid ground. You would plunge through freezing ammonia clouds and lightning bolts a thousand times stronger than Earth's.",
            },
            {
                "visual_prompt": "deep crushing dark abyss with glowing superheated metallic hydrogen ocean, dramatic volumetric lighting, 8k",
                "narration": "Twelve hours later, the pressure becomes so intense it crushes a submarine like a soda can, and the air turns into a boiling ocean of liquid metal.",
            },
            {
                "visual_prompt": "glowing mysterious core of a gas giant planet surrounded by swirling cosmic energy, cinematic 8k",
                "narration": "You wouldn't hit a surface. You would simply dissolve into Jupiter's superheated core forever.",
            },
            {
                "visual_prompt": "epic wide view of jupiter and its moons in deep dark space with stars, cinematic photography",
                "narration": "Would you ever travel to Jupiter if you could? Comment below and follow for more mind-blowing space facts!",
            },
        ],
    },
    {
        "artist": "Forbidden Earth",
        "song_title": "3 Forbidden Places",
        "hook": "3 places on Earth you are strictly forbidden to visit!",
        "scenes": [
            {
                "visual_prompt": "mysterious foggy tropical island in indian ocean with dense jungle and warning aura, cinematic aerial shot, 8k",
                "narration": "Number three: North Sentinel Island. Home to an uncontacted tribe, approaching within three miles is completely illegal.",
            },
            {
                "visual_prompt": "dramatic volcanic island emerging from dark north atlantic ocean with black cliffs, moody cinematic photography",
                "narration": "Number two: Surtsey Island in Iceland. Born from an underwater volcano, only a handful of scientists are ever allowed to step foot on it.",
            },
            {
                "visual_prompt": "heavily guarded underground concrete vault deep inside snowy arctic mountain, dramatic lighting, cinematic 8k",
                "narration": "And number one: The Svalbard Global Seed Vault, buried deep inside an Arctic mountain to protect humanity's food supply from an apocalypse.",
            },
            {
                "visual_prompt": "dramatic earth from space at night with glowing city lights and mysterious aura, ultra realistic 8k",
                "narration": "Which of these forbidden places surprised you the most? Comment below and follow for more hidden Earth mysteries!",
            },
        ],
    },
    {
        "artist": "Deep Ocean",
        "song_title": "The Bloop Mystery",
        "hook": "Scientists recorded a terrifying sound from the deepest part of the ocean!",
        "scenes": [
            {
                "visual_prompt": "deep dark abyssal ocean underwater with eerie blue light beams and sonar waves, cinematic 8k",
                "narration": "In 1997, underwater microphones picked up one of the loudest sounds ever recorded on Earth, heard from over three thousand miles away.",
            },
            {
                "visual_prompt": "massive shadowy silhouette of a giant unknown sea creature in deep dark ocean abyss, terrifying cinematic lighting",
                "narration": "Known as The Bloop, its frequency looked eerily like a living creature, sparking theories of a monster far larger than any blue whale.",
            },
            {
                "visual_prompt": "giant antarctic iceberg cracking and breaking underwater in freezing dark ocean, dramatic photography, 8k",
                "narration": "Years later, scientists revealed the chilling truth: it was the sound of a massive Antarctic icequake tearing apart miles of ancient glacier.",
            },
            {
                "visual_prompt": "mysterious deep ocean trench with glowing bioluminescent particles, cinematic 8k",
                "narration": "Yet eighty percent of our oceans remain unexplored. What else is hiding down there? Follow for more mysteries!",
            },
        ],
    },
]


def generate_song_story(artist: str = "", song_title: str = "") -> Dict:
    settings = get_settings()
    api_key = settings.get("gemini_api_key", "")
    topic = f"{artist} {song_title}".strip()

    if api_key and topic:
        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            prompt = f"""
You are a viral USA/UK short-form documentary scriptwriter (Science, Space, What If, & Earth Mysteries).
Write a high-retention 35-second Facebook Reels / In-Stream script about: {topic}.
Return ONLY valid JSON:
{{
  "artist": "Short Category (e.g. Space Mystery, What If, Forbidden Earth)",
  "song_title": "Short Punchy Title (max 5 words)",
  "hook": "Scroll-stopping 1-line Facebook caption hook",
  "scenes": [
    {{
      "visual_prompt": "Detailed cinematic 8k visual description for AI image generation (no text in image)",
      "narration": "Punchy, dramatic 1-sentence US/UK English narration"
    }}
  ]
}}
Generate 4 or 5 fast-paced scenes ending with a comment question CTA.
"""
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            parsed = json.loads(resp.text)
            if parsed.get("scenes") and len(parsed["scenes"]) >= 3:
                return parsed
        except Exception:
            pass

    if topic:
        return {
            "artist": artist.strip() or "Mind-Blowing Mystery",
            "song_title": song_title.strip() or topic[:40],
            "hook": f"The jaw-dropping truth about {topic}!",
            "scenes": [
                {
                    "visual_prompt": f"cinematic dramatic scene representing {topic}, ultra realistic lighting, 8k, no text",
                    "narration": f"Have you ever wondered about the real mystery behind {topic}?",
                },
                {
                    "visual_prompt": f"close up scientific cosmic mystery visualization of {topic}, moody atmospheric lighting, 8k",
                    "narration": f"Scientists and explorers have uncovered facts about {topic} that seem almost impossible to believe.",
                },
                {
                    "visual_prompt": f"epic wide angle dramatic reveal of {topic}, glowing cosmic energy, 8k",
                    "narration": f"When you look closer at the numbers, it completely changes how we see our universe.",
                },
                {
                    "visual_prompt": "mysterious starry night sky over earth horizon, cinematic 8k",
                    "narration": "What topic should we explore next? Drop it in the comments and follow for more!",
                },
            ],
        }

    return random.choice(VIRAL_MYSTERY_STORIES)


def build_fb_caption(story: Dict) -> str:
    hook = story["hook"]
    cat = story["artist"]
    return (
        f"🤯 {hook}\n\n"
        f"Wait until you hear the ending... 👀🔥\n\n"
        f"💬 What do you think about this? Comment below! 👇\n"
        f"🔔 Follow for daily mind-blowing Space, Science & Earth Mysteries!\n\n"
        f"#SpaceFacts #ScienceMystery #WhatIf #MindBlowing #{cat.replace(' ', '')}"
    )

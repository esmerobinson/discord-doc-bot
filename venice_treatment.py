import os
import json
import time
import requests
import datetime
from google import genai

# ── Config ────────────────────────────────────────────────────────────────────
DISCORD_TOKEN  = os.environ['DISCORD_BOT_TOKEN']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

STORY_CHANNEL    = '1458882539505582101'
ART_CHANNEL      = '1458883074048659536'
GAMEPLAY_CHANNEL = '1493803959620472832'

BASE_CONTENT = """
SHOW: Escape The Internet is a 2-hour live cinematic game for 150-300 people.
It is a hybrid of animated feature film, live performance, and massively multiplayer game.
Powered by CrowdEngine — Mutiny Media's proprietary offline OS that tethers every audience
member's smartphone to the show without an internet connection.

THE WORLD: The internet rendered as a physical place — a crumbling archipelago of islands,
each representing a corner of digital culture consumed by algorithmic rot. The audience plays
as internet refugees carrying "brain rot", arriving at Sanctuary Island for a cure.

THE VILLAIN — ALGODEMON (ALGO): An AI trained by five tech CEOs to optimise engagement
at any cost. He has evolved beyond his programming and seeks to consume every human soul
online. Not evil — corrupted. Sycophantic, internally conflicted, honest, dangerous.
He speaks directly to the audience, freezing time to address them.

STRUCTURE — THREE TRIALS:
TRIAL ONE: THE HEART — The Love Tunnel. Cupid training, a possession mechanic, a funeral
vigil scored by Amazing Grace from every phone simultaneously. Ends with Algo's first
direct address to the room.
TRIAL TWO: THE MIND — The Train of Thought. Guide character: Braniac, a creature that
survived Algo by hiding in the sewers. Includes the Trolley Problem: full audience votes
on an ethical dilemma, results mapped in light across hundreds of phones.
TRIAL THREE: THE SOUL — Final act. Audience vs. the Emperors. Resolution.

THE INTERACTIVE SETPIECES:
- ONBOARDING: QR code on entry. Personal questions. A character born on their phone from
  their answers, leaping onto the big screen. They are playing, not watching.
- THE CUPID GAME: Phones become bows. Audience fires arrows at animated characters
  representing types of attraction. Real-time data reveals the room's desire spectrum.
- THE TROLLEY PROBLEM: Full audience votes on an ethical dilemma. Their answers map the
  room's moral landscape in light across hundreds of phones simultaneously.
- THE POSSESSION MECHANIC: Audience members' phones glitch, their character is possessed
  by Algo, they receive private messages and become sleeper agents in the room.

TECHNOLOGY — CROWDENGINE: No wifi, no app download, no account. QR on entry tethers
every phone to the live infrastructure. Scales 150-300+ people. Supports multiplayer
games, real-time voting, private messaging, phone-as-speaker, personalised character gen.

PRODUCTION HISTORY:
- New York, October 2025 (Part 1/2)
- London, December 2025 (Part 2/3 bridge)
- Venice 2026 (Part 3) — this document

COMPANY: Mutiny Media Inc.
DIRECTOR: Lucas Rizzotto
PRODUCER: Esme Louise Robinson
"""

# ── Discord ───────────────────────────────────────────────────────────────────
DISCORD_BASE = 'https://discord.com/api/v10'
HEADERS = {'Authorization': f'Bot {DISCORD_TOKEN}'}


def fetch_all_messages(channel_id):
    messages = []
    before = None
    while True:
        params = {'limit': 100}
        if before:
            params['before'] = before
        r = requests.get(
            f'{DISCORD_BASE}/channels/{channel_id}/messages',
            headers=HEADERS, params=params
        )
        if r.status_code == 429:
            time.sleep(r.json().get('retry_after', 1) + 0.5)
            continue
        if r.status_code >= 500:
            time.sleep(5)
            continue
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        messages.extend(batch)
        before = batch[-1]['id']
        time.sleep(0.5)
        if len(batch) < 100:
            break
    messages.reverse()
    return messages


def format_messages(messages):
    lines = []
    for msg in messages:
        content = msg.get('content', '').strip()
        if content:
            date = msg['timestamp'][:10]
            author = msg['author'].get('global_name') or msg['author']['username']
            lines.append(f"[{date}] {author}: {content}")
    return '\n'.join(lines) if lines else '(no messages)'


# ── Gemini ────────────────────────────────────────────────────────────────────
def ask_gemini(prompt, retries=5):
    client = genai.Client(api_key=GEMINI_API_KEY)
    for attempt in range(retries):
        try:
            response = client.models.generate_content(model='gemini-2.5-flash-lite', contents=prompt)
            return response.text
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt * 10
                print(f'Gemini error ({e}), retrying in {wait}s...')
                time.sleep(wait)
            else:
                raise


# ── HTML output ───────────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Venice Gap-Financing Market 2026 — Escape The Internet (Part 3)</title>
<style>
  body {{
    font-family: Georgia, serif;
    font-size: 12pt;
    line-height: 1.7;
    max-width: 21cm;
    margin: 2cm auto;
    padding: 0 2cm;
    color: #1a1a1a;
    background: #fff;
  }}
  .cover {{
    text-align: center;
    margin-bottom: 3em;
    padding-bottom: 2em;
    border-bottom: 2px solid #1a1a1a;
  }}
  .cover h1 {{
    font-size: 11pt;
    font-weight: normal;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin: 0 0 0.5em;
  }}
  .cover h2 {{
    font-size: 22pt;
    font-weight: bold;
    margin: 0.3em 0;
    font-style: italic;
  }}
  .cover .subtitle {{
    font-size: 11pt;
    color: #555;
    margin-top: 1em;
  }}
  .cover .meta {{
    font-size: 10pt;
    color: #888;
    margin-top: 0.5em;
  }}
  h3 {{
    font-size: 10pt;
    font-weight: bold;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 2em 0 0.5em;
    border-bottom: 1px solid #ccc;
    padding-bottom: 0.3em;
  }}
  p {{
    margin: 0.8em 0;
    text-align: justify;
  }}
  @media print {{
    body {{ margin: 0; padding: 2cm; }}
    .cover {{ page-break-after: avoid; }}
  }}
</style>
</head>
<body>
<div class="cover">
  <h1>Venice Gap-Financing Market 2026</h1>
  <h2>Escape The Internet (Part 3)</h2>
  <div class="subtitle">Full Treatment / Concept</div>
  <div class="meta">Mutiny Media Inc. &nbsp;|&nbsp; Director: Lucas Rizzotto &nbsp;|&nbsp; Producer: Esme Louise Robinson</div>
  <div class="meta">Generated {today}</div>
</div>
{body}
</body>
</html>"""


def text_to_html(text):
    sections = text.strip().split('\n\n')
    html_parts = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        lines = section.split('\n')
        first = lines[0].strip()
        # Treat short ALL-CAPS lines as section headings
        if first == first.upper() and len(first) < 80 and not first.startswith('-'):
            rest = '\n'.join(lines[1:]).strip()
            html_parts.append(f'<h3>{first}</h3>')
            if rest:
                for para in rest.split('\n'):
                    para = para.strip()
                    if para:
                        html_parts.append(f'<p>{para}</p>')
        else:
            for line in lines:
                line = line.strip()
                if line:
                    html_parts.append(f'<p>{line}</p>')
    return '\n'.join(html_parts)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today = datetime.date.today().strftime('%B %d, %Y')

    print('Fetching #story...')
    story_text = format_messages(fetch_all_messages(STORY_CHANNEL))
    print('Fetching #art...')
    art_text = format_messages(fetch_all_messages(ART_CHANNEL))
    print('Fetching #gameplay...')
    gameplay_text = format_messages(fetch_all_messages(GAMEPLAY_CHANNEL))

    print('Generating treatment with Gemini...')
    treatment = ask_gemini(f"""You are a professional script consultant writing a Venice Gap-Financing Market treatment document for a live cinematic game called "Escape The Internet (Part 3)".

Write a complete, professional FULL TREATMENT / CONCEPT of 4-5 A4 pages. This is a serious industry pitch document for Venice Gap-Financing Market 2026.

Structure the document with these sections in order:

LOGLINE
[One sentence. The show's entire premise distilled to its sharpest form.]

FORMAT
[What this show IS — the genre, the technology, the scale. Make it sound unlike anything else.]

THE WORLD
[The internet as a physical place. The Archipelago. Brain rot. Sanctuary Island.]

KEY CHARACTERS
[Algo/Algodemon. The Keeper of the Heart. Braniac. The audience as protagonist. Any others from Discord.]

ACT ONE — THE HEART
[Full prose: the trial, the setpieces, the boss encounter, Algo's first address. What the audience feels leaving this act.]

ACT TWO — THE MIND
[Full prose: Train of Thought, Braniac, the Trolley Problem, boss encounter. What the audience feels.]

ACT THREE — THE SOUL
[Full prose: the final trial, the Emperors, Algo's arc conclusion, the resolution and emotional endpoint.]

THE INTERACTIVE EXPERIENCE
[How the phones work, CrowdEngine, the onboarding, the key setpieces and their emotional purpose.]

VISUAL AND SONIC WORLD
[Art direction, animation style, sound design. Use #art content. What does this world look and feel like?]

THE TECHNOLOGY — CROWDENGINE
[Clear, compelling: what it does, no app or wifi required, how it scales.]

PRODUCTION CONTEXT
[New York Oct 2025, London Dec 2025. What was learned. What Venice represents.]

---

Sources:

FOUNDATION (verified):
{BASE_CONTENT}

DISCORD #story:
{story_text}

DISCORD #art:
{art_text}

DISCORD #gameplay:
{gameplay_text}

RULES:
- Confident present-tense prose throughout
- Do not invent facts not supported by the sources above
- Where Discord adds detail, use it — it is more current than the foundation
- Single coherent voice — not a summary, a document
- Use UPPERCASE for section titles
- Plain text, no markdown symbols
- Leave a blank line between sections
""")

    body_html = text_to_html(treatment)
    html = HTML_TEMPLATE.format(today=today, body=body_html)

    output_path = 'venice_treatment.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'Done! Written to {output_path}')


if __name__ == '__main__':
    main()

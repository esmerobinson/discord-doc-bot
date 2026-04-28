import os
import json
import time
import requests
import datetime
from google import genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── Config ────────────────────────────────────────────────────────────────────
DISCORD_TOKEN  = os.environ['DISCORD_BOT_TOKEN']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

STORY_CHANNEL    = '1458882539505582101'
ART_CHANNEL      = '1458883074048659536'
GAMEPLAY_CHANNEL = '1493803959620472832'

SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive',
]

FORMATTING_RULES = """
IMPORTANT FORMATTING RULES:
- Do NOT use markdown (no #, ##, *, **, --- etc.)
- Use UPPERCASE for main section titles
- Use plain dashes (-) for bullet points
- Leave a blank line between sections
- Plain text only, suitable for a Google Doc
"""

BASE_CONTENT = """
KNOWN PROJECT DETAILS (use these as foundation, supplement with Discord content):

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
    return '\n'.join(lines) if lines else '(no messages in this channel)'


# ── Google Docs / Drive ───────────────────────────────────────────────────────
def get_services():
    creds_info = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    docs  = build('docs',  'v1', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)
    return docs, drive


def write_doc(docs_service, doc_id, content):
    doc = docs_service.documents().get(documentId=doc_id).execute()
    end_index = doc['body']['content'][-1]['endIndex'] - 1
    reqs = []
    if end_index > 1:
        reqs.append({'deleteContentRange': {'range': {'startIndex': 1, 'endIndex': end_index}}})
    reqs.append({'insertText': {'location': {'index': 1}, 'text': content}})
    docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': reqs}).execute()


PRODUCER_EMAIL = 'esmerobinson15@gmail.com'

def share_doc(drive_service, doc_id):
    # Anyone with link can view
    drive_service.permissions().create(
        fileId=doc_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()
    # Also share directly to producer so it appears in their Drive
    drive_service.permissions().create(
        fileId=doc_id,
        body={'type': 'user', 'role': 'writer', 'emailAddress': PRODUCER_EMAIL},
        sendNotificationEmail=False
    ).execute()


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


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today = datetime.date.today().strftime('%B %d, %Y')
    docs_service, drive_service = get_services()

    # Fetch Discord content
    print('Fetching #story...')
    story_text = format_messages(fetch_all_messages(STORY_CHANNEL))

    print('Fetching #art...')
    art_text = format_messages(fetch_all_messages(ART_CHANNEL))

    print('Fetching #gameplay...')
    gameplay_text = format_messages(fetch_all_messages(GAMEPLAY_CHANNEL))

    # Generate treatment
    print('Generating treatment with Gemini...')
    treatment = ask_gemini(f"""You are a professional script consultant writing a Venice Gap-Financing Market treatment document for a live cinematic game called "Escape The Internet (Part 3)".

Write a complete, professional FULL TREATMENT / CONCEPT document of 4-5 A4 pages. This will be submitted to Venice Gap-Financing Market 2026. It must be compelling, precise, and read as a serious industry pitch document.

The document must follow this structure:

VENICE GAP-FINANCING MARKET 2026
FULL TREATMENT / CONCEPT

ESCAPE THE INTERNET (PART 3)
Mutiny Media Inc. | Director: Lucas Rizzotto | Producer: Esme Louise Robinson

LOGLINE
[One sentence. The show's entire premise distilled to its sharpest form.]

FORMAT
[What this show IS — the genre, the technology, the scale. Make it sound unlike anything else.]

THE WORLD
[The internet as a physical place. The Archipelago. Brain rot. Sanctuary Island. Why this setting is the right one for this moment.]

KEY CHARACTERS
[Algo/Algodemon — full character description. The Keeper of the Heart. Braniac. The audience as protagonist. Any other characters found in the Discord content.]

ACT ONE — THE HEART
[Full prose description of Trial One. The Love Tunnel. The Cupid Game. The Possession Mechanic. The Funeral Vigil. The boss encounter. Algo's first direct address. What the audience feels leaving this act.]

ACT TWO — THE MIND
[Full prose description of Trial Two. The Train of Thought. Braniac. The Trolley Problem. Games, mechanics, boss encounter. What the audience feels leaving this act.]

ACT THREE — THE SOUL
[Full prose description of Trial Three. The final trial. The Emperors. Algo's arc conclusion. The resolution. What the audience feels at the end of the show.]

THE INTERACTIVE EXPERIENCE
[How the audience's phones work. What CrowdEngine enables. The onboarding sequence. The key interactive setpieces and their emotional purpose — not just what they do, but why they matter.]

VISUAL AND SONIC WORLD
[Art direction, animation style, sound design. Use the #art Discord content. What does this world look and feel like?]

THE TECHNOLOGY — CROWDENGINE
[Brief, clear, compelling description of the technology — what it does, that it requires no app or wifi, how it scales. This is a competitive advantage.]

PRODUCTION CONTEXT
[Previous productions: New York October 2025, London December 2025. What was learned. What Part 3 / Venice represents in the show's development arc.]

---

Use the following sources:

FOUNDATION CONTENT (verified project details):
{BASE_CONTENT}

DISCORD #story channel (narrative, characters, plot developments):
{story_text}

DISCORD #art channel (visual style, art direction, design decisions):
{art_text}

DISCORD #gameplay channel (interactive mechanics, game design):
{gameplay_text}

CRITICAL RULES:
- Write in confident, present-tense prose — this is a description of the show as it will exist, not as it might
- Do NOT invent facts not supported by the content above
- Where Discord content adds detail to the foundation, use it — it is more current
- Where Discord content is absent (channel skipped), use the foundation content and write [TO BE EXPANDED] only if genuinely unknown
- The document should read as a single coherent voice, not a stitched-together summary
- 4-5 A4 pages when printed — substantial but tight

{FORMATTING_RULES}

Generated from Discord channels on {today}.
""")

    # Print service account email so user can share a doc with it
    creds_info = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
    sa_email = creds_info.get('client_email', 'unknown')
    print(f'Service account email: {sa_email}')

    doc_id = os.environ.get('VENICE_DOC_ID', '')
    if not doc_id:
        print(f'\nERROR: No VENICE_DOC_ID set.')
        print(f'Steps:')
        print(f'  1. Create a blank Google Doc in your Drive')
        print(f'  2. Share it with {sa_email} (Editor)')
        print(f'  3. Add VENICE_DOC_ID secret to GitHub with the doc ID from its URL')
        print(f'     (the long string between /d/ and /edit in the URL)')
        raise SystemExit(1)

    header = (
        f"VENICE GAP-FINANCING MARKET 2026\n"
        f"FULL TREATMENT / CONCEPT\n\n"
        f"Generated from Discord channels: #story, #art, #gameplay\n"
        f"Last updated: {today}\n\n"
    )
    print('Writing to Google Doc...')
    write_doc(docs_service, doc_id, header + treatment)

    doc_url = f"https://docs.google.com/document/d/{doc_id}"
    print(f"\nDone!\n{doc_url}")
    return doc_url


if __name__ == '__main__':
    main()

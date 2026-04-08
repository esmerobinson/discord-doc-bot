import os
import json
import time
import requests
import datetime
from google import genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── Config ────────────────────────────────────────────────────────────────────
DISCORD_TOKEN     = os.environ['DISCORD_BOT_TOKEN']
GEMINI_API_KEY    = os.environ['GEMINI_API_KEY']

STORY_CHANNEL     = '1458882539505582101'
BOSSES_CHANNEL    = '1488229566588784660'
LOGISTICS_CHANNEL = '1458881996779552855'

DOC_CURRENT_STORY = '1K6CCXHKBRZLaSw-mujlZlEV2nCRxnCyMyjTaGJUn-go'
DOC_STORY_UPDATES = '195406QQnLdvfhhXqG8VUI2rLFzTRlsZerKpsIb2aKPE'
DOC_LOGISTICS     = '1I7idtV5BmUjvDymUdBj5nmXzsoKu0oJM0PCSgxsgsJE'

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

# ── Discord ───────────────────────────────────────────────────────────────────
DISCORD_BASE = 'https://discord.com/api/v10'
HEADERS = {'Authorization': f'Bot {DISCORD_TOKEN}'}


def fetch_all_messages(channel_id):
    """Fetch every message from a channel, returned oldest first."""
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
            retry_after = r.json().get('retry_after', 1)
            time.sleep(retry_after + 0.5)
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
    messages.reverse()  # oldest first
    return messages


def fetch_today_messages(channel_id):
    """Fetch messages posted in the last 24 hours."""
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    all_msgs = fetch_all_messages(channel_id)
    return [
        m for m in all_msgs
        if datetime.datetime.fromisoformat(m['timestamp'].replace('Z', '+00:00')) >= cutoff
    ]


def format_messages(messages):
    """Turn a list of Discord messages into readable plain text, extracting [CUT] tags."""
    lines = []
    for msg in messages:
        content = msg.get('content', '').strip()
        if content:
            date = msg['timestamp'][:10]
            author = msg['author'].get('global_name') or msg['author']['username']
            lines.append(f"[{date}] {author}: {content}")
    return '\n'.join(lines) if lines else '(no messages)'


def extract_cuts(messages):
    """Find all [CUT] instructions from messages."""
    cuts = []
    for msg in messages:
        content = msg.get('content', '').strip()
        if content.upper().startswith('[CUT]'):
            cuts.append(content[5:].strip())
    return cuts


# ── Google Docs ───────────────────────────────────────────────────────────────
def get_docs_service():
    creds_info = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build('docs', 'v1', credentials=creds)


def get_doc_text(service, doc_id):
    """Read the plain text content of a Google Doc."""
    doc = service.documents().get(documentId=doc_id).execute()
    text = ''
    for element in doc['body']['content']:
        if 'paragraph' in element:
            for pe in element['paragraph']['elements']:
                if 'textRun' in pe:
                    text += pe['textRun']['content']
    return text


def clear_and_write_doc(service, doc_id, content):
    """Overwrite an entire Google Doc with new content."""
    doc = service.documents().get(documentId=doc_id).execute()
    end_index = doc['body']['content'][-1]['endIndex'] - 1
    reqs = []
    if end_index > 1:
        reqs.append({'deleteContentRange': {'range': {'startIndex': 1, 'endIndex': end_index}}})
    reqs.append({'insertText': {'location': {'index': 1}, 'text': content}})
    service.documents().batchUpdate(documentId=doc_id, body={'requests': reqs}).execute()


def append_to_doc(service, doc_id, content):
    """Append text to the end of a Google Doc."""
    doc = service.documents().get(documentId=doc_id).execute()
    end_index = doc['body']['content'][-1]['endIndex'] - 1
    service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': [{'insertText': {'location': {'index': end_index}, 'text': '\n' + content}}]}
    ).execute()


# ── Gemini ────────────────────────────────────────────────────────────────────
def ask_gemini(prompt, retries=5):
    client = genai.Client(api_key=GEMINI_API_KEY)
    for attempt in range(retries):
        try:
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            return response.text
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt * 10  # 10s, 20s, 40s, 80s...
                print(f'Gemini error ({e}), retrying in {wait}s...')
                time.sleep(wait)
            else:
                raise


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today = datetime.date.today().strftime('%B %d, %Y')
    docs  = get_docs_service()

    # 1. CURRENT STORY — full megadoc rewritten from all history
    print('Fetching #story and #bosses...')
    story_msgs  = fetch_all_messages(STORY_CHANNEL)
    bosses_msgs = fetch_all_messages(BOSSES_CHANNEL)

    story_text  = format_messages(story_msgs)
    bosses_text = format_messages(bosses_msgs)

    # Collect [CUT] instructions from all story channels
    all_cuts = extract_cuts(story_msgs) + extract_cuts(bosses_msgs)
    cuts_section = ''
    if all_cuts:
        cuts_list = '\n'.join(f'- {c}' for c in all_cuts)
        cuts_section = f"""
The following items have been explicitly marked as CUT or outdated by the team.
Do NOT include these in the document:
{cuts_list}
"""

    story_summary = ask_gemini(f"""You are a story documentation assistant for a film production team.
Below are all messages from the #story and #bosses Discord channels for a film project.
Write a comprehensive, well-structured document describing THE CURRENT STATE of the story.
Cover all key plot points, characters, story beats, and world details.
If a topic was discussed but later reversed or changed, only reflect the FINAL/CURRENT version.
If something was scrapped or changed, do not include the old version.
Write it as a reference document, not a chat summary.
{cuts_section}
{FORMATTING_RULES}

#story channel:
{story_text}

#bosses channel (story details about boss characters/encounters):
{bosses_text}
""")

    print('Writing Current Story doc...')
    clear_and_write_doc(docs, DOC_CURRENT_STORY,
                        f"CURRENT STORY\nLast updated: {today}\n\n{story_summary}")

    # 2. STORY UPDATES — append today's changes, but only once per day
    print("Fetching today's story messages...")
    today_story  = fetch_today_messages(STORY_CHANNEL)
    today_bosses = fetch_today_messages(BOSSES_CHANNEL)

    if today_story or today_bosses:
        # Check if we already logged today to avoid duplicates
        existing = get_doc_text(docs, DOC_STORY_UPDATES)
        if today in existing:
            print(f'Already logged updates for {today}, skipping duplicate.')
        else:
            today_text = format_messages(today_story + today_bosses)
            update_summary = ask_gemini(f"""You are a story documentation assistant for a film production team.
Below are today's Discord messages about the story.
Write a brief, clear summary of what was discussed or changed today.
Pay special attention to:
- Things that were CHANGED or REVERSED from before (flag these clearly)
- New ideas or additions
- Things that were scrapped or cut
Be concise. Do not write an introduction, just list what changed.
{FORMATTING_RULES}

Messages from today ({today}):
{today_text}
""")
            print('Appending to Story Updates doc...')
            append_to_doc(docs, DOC_STORY_UPDATES,
                          f"────────────────────────────────────────\n{today}\n────────────────────────────────────────\n{update_summary}\n")
    else:
        print('No story messages today, skipping Story Updates.')

    # 3. LOGISTICS TO DO — rewritten from all logistics history
    print('Fetching #logistics...')
    logistics_msgs = fetch_all_messages(LOGISTICS_CHANNEL)
    logistics_text = format_messages(logistics_msgs)
    logistics_cuts = extract_cuts(logistics_msgs)
    logistics_cuts_section = ''
    if logistics_cuts:
        cuts_list = '\n'.join(f'- {c}' for c in logistics_cuts)
        logistics_cuts_section = f"""
The following items have been explicitly marked as CUT or no longer needed:
{cuts_list}
"""

    todo_list = ask_gemini(f"""You are a production coordinator assistant for a film team.
Below are all messages from the #logistics Discord channel.
Extract and organise ALL tasks, to-dos, and action items mentioned across the entire history.
Group them by category (e.g. EQUIPMENT, LOCATIONS, CREW, SCHEDULING, BUDGET).
For each item, note whether it appears completed or still outstanding based on context.
If a task was changed or updated, only show the current version.
Use [ ] for outstanding items and [x] for completed items.
Do not include conversational filler — only actionable items.
{logistics_cuts_section}
{FORMATTING_RULES}
- Use UPPERCASE for category titles
- Use plain [ ] and [x] for task checkboxes

Messages:
{logistics_text}
""")

    print('Writing Logistics To Do doc...')
    clear_and_write_doc(docs, DOC_LOGISTICS,
                        f"LOGISTICS TO DO\nLast updated: {today}\n\n{todo_list}")

    print('All done!')


if __name__ == '__main__':
    main()

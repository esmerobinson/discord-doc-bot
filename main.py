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
        time.sleep(0.5)  # be polite to Discord's API
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
    """Turn a list of Discord messages into readable plain text."""
    lines = []
    for msg in messages:
        if msg.get('content', '').strip():
            date = msg['timestamp'][:10]
            author = msg['author'].get('global_name') or msg['author']['username']
            lines.append(f"[{date}] {author}: {msg['content']}")
    return '\n'.join(lines) if lines else '(no messages)'


# ── Google Docs ───────────────────────────────────────────────────────────────
def get_docs_service():
    creds_info = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build('docs', 'v1', credentials=creds)


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
def ask_gemini(prompt):
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(model='gemini-2.0-flash-lite', contents=prompt)
    return response.text


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today = datetime.date.today().strftime('%B %d, %Y')
    docs  = get_docs_service()

    # 1. CURRENT STORY — full megadoc rewritten from all history
    print('Fetching #story and #bosses...')
    story_text  = format_messages(fetch_all_messages(STORY_CHANNEL))
    bosses_text = format_messages(fetch_all_messages(BOSSES_CHANNEL))

    story_summary = ask_gemini(f"""You are a story documentation assistant for a film production team.
Below are all messages from the #story and #bosses Discord channels for a film project.
Write a comprehensive, well-structured document describing THE CURRENT STATE of the story.
Cover all key plot points, characters, story beats, and world details.
Use clear headings and subheadings. Write it as a reference document, not a chat summary.

#story channel:
{story_text}

#bosses channel (story details about boss characters/encounters):
{bosses_text}
""")

    print('Writing Current Story doc...')
    clear_and_write_doc(docs, DOC_CURRENT_STORY,
                        f"CURRENT STORY\nLast updated: {today}\n\n{story_summary}")

    # 2. STORY UPDATES — append today's changes
    print('Fetching today\'s story messages...')
    today_story  = fetch_today_messages(STORY_CHANNEL)
    today_bosses = fetch_today_messages(BOSSES_CHANNEL)

    if today_story or today_bosses:
        today_text = format_messages(today_story + today_bosses)
        update_summary = ask_gemini(f"""You are a story documentation assistant for a film production team.
Below are today's Discord messages about the story. Write a brief, clear summary of what was discussed or changed today.
Be concise — bullet points are fine. Do not write an introduction, just list what changed.

Messages from today ({today}):
{today_text}
""")
        print('Appending to Story Updates doc...')
        append_to_doc(docs, DOC_STORY_UPDATES,
                      f"{'─' * 40}\n{today}\n{'─' * 40}\n{update_summary}\n")
    else:
        print('No story messages today, skipping Story Updates.')

    # 3. LOGISTICS TO DO — rewritten from all logistics history
    print('Fetching #logistics...')
    logistics_text = format_messages(fetch_all_messages(LOGISTICS_CHANNEL))

    todo_list = ask_gemini(f"""You are a production coordinator assistant for a film team.
Below are all messages from the #logistics Discord channel.
Extract and organise ALL tasks, to-dos, and action items mentioned across the entire history.
Group them by category (e.g. Equipment, Locations, Crew, Scheduling, Budget, etc.).
For each item, note whether it appears completed or still outstanding based on context in the messages.
Use checkboxes: [ ] for outstanding, [x] for completed.
Do not include conversational filler — only actionable items.

Messages:
{logistics_text}
""")

    print('Writing Logistics To Do doc...')
    clear_and_write_doc(docs, DOC_LOGISTICS,
                        f"LOGISTICS TO DO\nLast updated: {today}\n\n{todo_list}")

    print('All done!')


if __name__ == '__main__':
    main()

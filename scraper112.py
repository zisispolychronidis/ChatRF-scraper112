import snscrape.modules.twitter as sntwitter
import re
import time
import json
from datetime import timezone, datetime
from pathlib import Path

USER = "112Greece"
LOGFILE = Path("alerts_log.jsonl")

URL_RE = re.compile(r'https?://\S+')
HASHTAG_SYMBOL_RE = re.compile(r'#')
MULTISPACE_RE = re.compile(r'\s+')
EMOJI_RE = re.compile(
    "[" 
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]+", flags=re.UNICODE)

TRUNCATE_MARKERS = ['Προσοχή', '‼', '‼️', '⚠', '🔴']

def extract_core_message(raw_text):
    """ Αποσπάει το κύριο μήνυμα από το post """
    text = raw_text.strip()
    if 'Ενεργοποίηση' in text:
        _, after = text.split('Ενεργοποίηση', 1)
        text = after.strip()
    text = URL_RE.sub('', text)
    text = EMOJI_RE.sub('', text)
    text = HASHTAG_SYMBOL_RE.sub('', text)
    text = MULTISPACE_RE.sub(' ', text).strip()
    lines = [ln.strip() for ln in re.split(r'[\r\n]+', text) if ln.strip()]
    core_lines = []
    for ln in lines:
        if any(marker in ln for marker in TRUNCATE_MARKERS):
            break
        core_lines.append(ln)
    return ' '.join(core_lines).strip()

def fetch_new_messages(seen_ids, max_tweets=30):
    """ Τραβάει τα νέα post """
    results = []
    query = f"from:{USER}"
    for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
        if i >= max_tweets:
            break
        if 'Ενεργοποίηση' not in tweet.content:
            continue
        if tweet.id in seen_ids:
            continue
        core = extract_core_message(tweet.content)
        if core:
            msg = {
                "id": tweet.id,
                "date": tweet.date.astimezone(timezone.utc).isoformat(),
                "core_message": core
            }
            results.append(msg)
            seen_ids.add(tweet.id)
    return results

def log_message(msg):
    """ Αποθηκεύει κάθε νέο alert σε JSONL """
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

def run_loop(callback, interval=600):
    seen = set()
    while True:
        try:
            new_msgs = fetch_new_messages(seen)
            for msg in new_msgs:
                # callback = TTS ή άλλο function
                callback(msg)
                # αποθήκευση στο log
                log_message(msg)
        except Exception as e:
            print("Error:", e)
        time.sleep(interval)

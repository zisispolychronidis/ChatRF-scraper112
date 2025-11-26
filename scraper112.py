import time
import json
import re
from datetime import timezone, datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging
import sys

# ANSI colors
class LogColors:
    RESET = "\033[0m"
    GRAY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"

class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: LogColors.GRAY,
        logging.INFO: LogColors.BLUE,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.RED,
    }

    def format(self, record):
        level_color = self.LEVEL_COLORS.get(record.levelno, LogColors.RESET)
        message = super().format(record)
        return f"{level_color}{message}{LogColors.RESET}"

def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    formatter = ColorFormatter(
        "[%(asctime)s] %(levelname)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)

    return logger

TWITTER_HANDLE = "112Greece"  # Twitter/X username
TWITTER_URL = f"https://twitter.com/{TWITTER_HANDLE}"
LOGFILE = Path("alerts_log.jsonl")
COOKIES_FILE = Path("twitter_cookies.json")

# Regex για καθάρισμα
# URLs πλήρη (http/https)
URL_FULL_RE = re.compile(r'https?://\S+', re.UNICODE)

# Short URLs χωρίς http (π.χ. bit.ly/abc123)
URL_SHORT_RE = re.compile(
    r'\b(?:bit\.ly|tinyurl\.com|goo\.gl|rb\.gy|t\.co|ow\.ly|buff\.ly)/\S+',
    re.IGNORECASE
)

# Αφαίρεση hashtags (#word) και απλό "tagging" όπως " #Πυρκαγιά"
HASHTAG_RE = re.compile(r'#\S+', re.UNICODE)

# Mentions @username
MENTION_RE = re.compile(r'@\S+', re.UNICODE)

# Emojis
EMOJI_RE = re.compile(
    "[" 
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]+",
    re.UNICODE
)

TRUNCATE_MARKERS = ['Προσοχή', '‼', '⚠', '🔴']


def extract_core_message(raw_text):
    """Παίρνει raw tweet text και επιστρέφει καθαρό core message."""
    if not raw_text:
        return ""

    text = raw_text.strip()

    if "Ενεργοποίηση" not in text:
        return ""

    _, after = text.split("Ενεργοποίηση", 1)
    text = after.strip()

    # ΑΦΑΙΡΕΣΕ ΤΑ ΠΑΝΤΑ
    text = URL_FULL_RE.sub('', text)
    text = URL_SHORT_RE.sub('', text)
    text = HASHTAG_RE.sub('', text)
    text = MENTION_RE.sub('', text)
    text = EMOJI_RE.sub('', text)

    lines = [ln.strip() for ln in re.split(r'[\r\n]+', text) if ln.strip()]
    core_lines = []
    for ln in lines:
        if any(marker in ln for marker in TRUNCATE_MARKERS):
            break
        core_lines.append(ln)

    return " ".join(core_lines).strip()


def setup_driver(headless=True):
    """Δημιουργεί Selenium WebDriver με Chrome."""
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless=new")
    
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    chrome_options.add_argument("--lang=el-GR")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Remove webdriver flag
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def save_cookies(driver, filepath):
    """Αποθηκεύει cookies από τον browser."""
    cookies = driver.get_cookies()
    with open(filepath, 'w') as f:
        json.dump(cookies, f)


def load_cookies(driver, filepath):
    """Φορτώνει cookies στον browser."""
    if not filepath.exists():
        return False
    
    with open(filepath, 'r') as f:
        cookies = json.load(f)
    
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
        except:
            pass
    
    return True


def login_to_twitter(driver, logger):
    """Κάνει login στο Twitter/X (manual - για πρώτη φορά)."""
    logger.info("Please log in to Twitter/X manually in the browser window...")
    logger.info("After logging in, press Enter in the terminal to continue...")
    
    driver.get("https://twitter.com/login")
    input("Press Enter after you've logged in...")
    
    # Save cookies for next time
    save_cookies(driver, COOKIES_FILE)
    logger.info(f"Cookies saved to {COOKIES_FILE}")


def fetch_new_messages(driver, seen_ids, logger, max_tweets=20):
    """Φέρνει νέα tweets από το Twitter profile με Selenium."""
    new_alerts = []
    
    try:
        driver.get(TWITTER_URL)
        
        # Wait for tweets to load
        time.sleep(5)
        
        # Scroll down to load more tweets
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        # Find all tweet elements
        # Twitter uses article tags for tweets
        tweets = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
        
        if not tweets:
            logger.warning("No tweets found on page")
            # Try alternative selector
            tweets = driver.find_elements(By.TAG_NAME, "article")
        
        if not tweets:
            logger.error("Still no tweets found. May need to log in or Twitter changed structure.")
            return new_alerts
        
        logger.info(f"Processing {len(tweets)} tweets...")
        
        for idx, tweet in enumerate(tweets[:max_tweets]):
            try:
                # Get tweet text - try multiple selectors
                text_element = None
                
                # Try common Twitter text selectors
                selectors = [
                    "div[data-testid='tweetText']",
                    "div[lang]",
                    "div.css-1rynq56",
                ]
                
                for selector in selectors:
                    try:
                        text_element = tweet.find_element(By.CSS_SELECTOR, selector)
                        if text_element:
                            break
                    except:
                        continue
                
                if not text_element:
                    # Fallback: get all text from tweet
                    text = tweet.text
                else:
                    text = text_element.text
                
                if not text or "Ενεργοποίηση" not in text:
                    continue
                
                # Try to get tweet ID from link
                try:
                    tweet_link = tweet.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
                    tweet_url = tweet_link.get_attribute("href")
                    tweet_id = tweet_url.split("/status/")[1].split("?")[0]
                except:
                    # Fallback: use hash of text
                    tweet_id = str(hash(text[:100]))
                
                if tweet_id in seen_ids:
                    logger.debug(f"Skipping tweet {idx} - already seen")
                    continue
                
                core = extract_core_message(text)
                if not core:
                    logger.debug(f"Skipping tweet {idx} - empty core message")
                    continue
                
                msg = {
                    "id": tweet_id,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "core_message": core,
                    "source": "twitter"
                }
                
                new_alerts.append(msg)
                seen_ids.add(tweet_id)
                logger.info(f"✓ New alert found: {core[:80]}...")
                
                if len(new_alerts) >= max_tweets:
                    break
                    
            except Exception as e:
                logger.debug(f"Error processing tweet {idx}: {e}")
                continue
        
        logger.info(f"Found {len(new_alerts)} new alerts from Twitter")
        
    except Exception as e:
        logger.error(f"Error fetching tweets: {e}", exc_info=True)
    
    return new_alerts


def log_message(msg):
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")


def run_loop(callback, interval=300, headless=True):
    """
    Loop που ψάχνει νέα 112 alerts από Twitter και καλεί callback(msg) όταν βρεθούν.
    Shorter interval since Twitter updates faster (default 5 mins)
    """
    logger = setup_logger()
    logger.info(f"Starting 112 Greece Twitter scraper (interval: {interval}s)")
    
    driver = setup_driver(headless=headless)
    
    try:
        # Load cookies or login
        driver.get("https://twitter.com")
        time.sleep(2)
        
        if COOKIES_FILE.exists():
            logger.info("Loading saved cookies...")
            load_cookies(driver, COOKIES_FILE)
            driver.refresh()
            time.sleep(3)
        else:
            logger.info("No cookies found. Manual login required.")
            login_to_twitter(driver, logger)
        
        seen = set()
        
        # φόρτωσε υπάρχον log
        if LOGFILE.exists():
            with open(LOGFILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        seen.add(entry["id"])
                    except:
                        pass
            logger.info(f"Loaded {len(seen)} previously seen alerts")
        
        while True:
            try:
                new_msgs = fetch_new_messages(driver, seen, logger)
                for msg in new_msgs:
                    callback(msg)
                    log_message(msg)
            except Exception as e:
                logger.error(f"112 scraper error: {e}", exc_info=True)
            
            logger.debug(f"Sleeping for {interval} seconds...")
            time.sleep(interval)
            
    finally:
        driver.quit()


# Test function
if __name__ == "__main__":
    logger = setup_logger()
    
    def test_callback(msg):
        logger.info(f"[ALERT] {msg['core_message']}")
    
    logger.info("Testing Twitter scraper (single run)...")
    logger.info("Browser will open - log in if needed, then check console...")
    
    # Run with visible browser for testing
    # For production, change headless=True and increase interval as needed
    run_loop(test_callback, interval=3600, headless=False)

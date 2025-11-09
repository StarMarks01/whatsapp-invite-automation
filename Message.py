import os
import time
import random
import pandas as pd
import pyperclip
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------- CONFIG ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(SCRIPT_DIR, "Numbers.xlsx")
# You can include a "name" column in the spreadsheet to personalize messages.
MESSAGE_TEMPLATE = "You are invited to the wedding, {name}!"  # use {name} or leave as-is
SENDER_PROFILE = "Profile1"

# Rate-limiting / anti-detection tuning
MIN_DELAY = 6         # base min delay after opening chat (seconds)
MAX_DELAY = 12        # base max delay after opening chat (seconds)
TYPING_PAUSE = 0.4    # small pause after paste before sending
JITTER = 2.5          # additional random jitter seconds
LONG_BREAK_AFTER = 25 # take a long break after this many messages
LONG_BREAK_SECONDS = 300  # long break duration (5 minutes)
MAX_PER_HOUR = 150    # do not exceed this many messages per hour (adjust downward for safety)
CHAT_BOX_WAIT = 25    # how long to wait for message box to appear (seconds)
BATCH_SLEEP_RANGE = (1.5, 3.5)  # small sleep between each message cycle
# -----------------------------

df = pd.read_excel(EXCEL_FILE)
df.columns = df.columns.str.strip()

possible_cols = [c for c in df.columns if "number" in c.lower()]
if not possible_cols:
    raise ValueError(f"No 'number' column found. Columns: {df.columns.tolist()}")
COLUMN_NAME = possible_cols[0]

numbers = df[COLUMN_NAME].dropna().astype(str).tolist()
# optional names for personalization
name_col = None
for c in df.columns:
    if "name" in c.lower():
        name_col = c
        break
names = df[name_col].fillna("").astype(str).tolist() if name_col else [""] * len(numbers)

# normalize numbers (simple)
def normalize(n):
    n = n.strip().replace(" ", "").replace("+", "")
    if not n.startswith("#Changes"):      #Change To country code specific
        return "#Changes" + n             #Change To country code specific
    return n

numbers = [normalize(n) for n in numbers]

# Configure Chrome
options = webdriver.ChromeOptions()
options.add_argument(
    f"user-data-dir=C:/Users/EMPEROR/AppData/Local/Google/Chrome/User Data/{SENDER_PROFILE}"
)
driver = webdriver.Chrome(options=options)

driver.get("https://web.whatsapp.com/")
input("Press ENTER once WhatsApp Web is fully loaded and logged in...")

sent_count = 0
hour_start = time.time()
for idx, num in enumerate(numbers):
    # enforce per-hour limit
    elapsed_hour = time.time() - hour_start
    if sent_count >= MAX_PER_HOUR and elapsed_hour < 3600:
        sleep_time = 3600 - elapsed_hour + 5
        print(f"[throttle] reached {MAX_PER_HOUR} in the last hour. Sleeping {int(sleep_time)}s.")
        time.sleep(sleep_time)
        hour_start = time.time()
        sent_count = 0

    # open chat
    driver.get(f"https://web.whatsapp.com/send?phone={num}")
    # wait a randomized amount before searching for box
    open_wait = random.uniform(MIN_DELAY, MAX_DELAY) + random.uniform(0, JITTER)
    time.sleep(open_wait)

    # determine message (personalize if possible)
    name = names[idx] if idx < len(names) else ""
    if "{name}" in MESSAGE_TEMPLATE and name:
        MESSAGE = MESSAGE_TEMPLATE.format(name=name)
    else:
        MESSAGE = MESSAGE_TEMPLATE.format(name="")

    try:
        # Wait for editable message box to appear using WebDriverWait
        msg_box = None
        wait = WebDriverWait(driver, CHAT_BOX_WAIT)
        for tab in ["6", "10", "15", "7", "8"]:
            try:
                msg_box = wait.until(
                    EC.presence_of_element_located((By.XPATH, f'//div[@contenteditable="true"][@data-tab="{tab}"]'))
                )
                if msg_box:
                    break
            except Exception:
                # try next data-tab value
                continue

        if not msg_box:
            raise Exception("Message box not found after waiting")

        # simulate paste and send
        msg_box.click()
        pyperclip.copy(MESSAGE)
        # small random pre-paste pause to mimic human
        time.sleep(random.uniform(0.2, 0.7))
        msg_box.send_keys(Keys.CONTROL, 'v')
        time.sleep(TYPING_PAUSE + random.uniform(0, 0.6))
        msg_box.send_keys(Keys.ENTER)
        print(f"✅ Message sent to {num}")
        sent_count += 1

    except Exception as e:
        # exponential backoff on failure
        backoff = random.uniform(8, 18)
        print(f"❌ Failed for {num}: {e}. Backing off {int(backoff)}s.")
        time.sleep(backoff)

    # small randomized pause between cycles
    time.sleep(random.uniform(*BATCH_SLEEP_RANGE))

    # long break after batches
    if sent_count > 0 and sent_count % LONG_BREAK_AFTER == 0:
        long_break = LONG_BREAK_SECONDS + random.uniform(0, 60)
        print(f"[break] took a long break of {int(long_break)}s after {sent_count} messages.")
        time.sleep(long_break)

driver.quit()

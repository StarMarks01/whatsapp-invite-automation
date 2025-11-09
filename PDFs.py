import time, os, random, platform
from pathlib import Path
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# ---------- CONFIG ----------
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

EXCEL_FILE = ASSETS_DIR / "Numbers.xlsx"
ATTACHMENT_PATH = ASSETS_DIR / "Invitation - 2.pdf"
SENDER_PROFILE = "Profile1"
COUNTRY_PREFIX = "91"
OPEN_CHAT_WAIT = 8
CLICK_RETRY = 6

MAX_CONSECUTIVE_FAILURES = 8
BATCH_SIZE = 120
BATCH_COOLDOWN_MIN = 60 * 10
BATCH_COOLDOWN_MAX = 60 * 25
LONG_COOLDOWN_ON_FAIL = 60 * 45
# -----------------------------

def get_chrome_user_data_dir(profile_name: str) -> str:
    home = Path.home()
    system = platform.system().lower()
    if "windows" in system:
        base = home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    elif "darwin" in system:
        base = home / "Library" / "Application Support" / "Google" / "Chrome"
    else:
        base = home / ".config" / "google-chrome"
        if not base.exists():
            base = home / ".config" / "chromium"
    return str(base / profile_name)

def rand_sleep(a, b):
    time.sleep(random.uniform(a, b))

def load_numbers(path, country_prefix):
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip()
    col = next((c for c in df.columns if "number" in c.lower()), None)
    if not col:
        raise ValueError(f"No 'number' column found. Columns: {df.columns.tolist()}")
    nums = (
        df[col]
        .dropna()
        .astype(str)
        .str.replace(r"\D", "", regex=True)
        .str.lstrip("0")
        .tolist()
    )
    nums = [n if n.startswith(country_prefix) else country_prefix + n for n in nums]
    seen, out = set(), []
    for n in nums:
        if n not in seen:
            out.append(n)
            seen.add(n)
    return out

def wait_for_chat_ready(driver):
    wait = WebDriverWait(driver, 30)
    selectors = [
        (By.CSS_SELECTOR, "div[contenteditable='true'][data-tab]"),
        (By.XPATH, "//div[@contenteditable='true' and @role='textbox']"),
    ]
    for by, sel in selectors:
        try:
            wait.until(EC.presence_of_element_located((by, sel)))
            return
        except:
            pass
    rand_sleep(1.5, 4.0)

def click_attach(driver):
    wait = WebDriverWait(driver, 10)
    selectors = [
        "div[aria-label='Attach']",
        "button[aria-label='Attach']",
        "span[data-icon='clip']",
        "span[data-icon='attach-menu']",
        "span[data-icon='attach-menu-plus']",
        "div[title='Attach']",
    ]
    for _ in range(CLICK_RETRY + random.randint(-2, 2)):
        for sel in selectors:
            try:
                el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                if el.is_displayed():
                    try:
                        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                    except:
                        pass
                    rand_sleep(0.4, 1.05)
                    el.click()
                    rand_sleep(0.9, 1.6)
                    return True
            except:
                continue
        rand_sleep(0.8, 1.8)
    return False

def send_pdf(driver, pdf_path):
    wait = WebDriverWait(driver, 20)
    inputs = wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "input[type='file']"))
    target = None
    for inp in inputs:
        try:
            accept = inp.get_attribute("accept") or ""
            if accept.strip() in ("", "*") or "document" in accept.lower() or "pdf" in accept.lower():
                target = inp
                break
        except:
            continue
    if not target:
        target = inputs[0]

    driver.execute_script(
        "arguments[0].style.display='block'; arguments[0].style.visibility='visible';", target
    )
    target.send_keys(str(Path(pdf_path).resolve()))
    rand_sleep(1.2, 3.2)

    try:
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "span[data-icon='send'], div[aria-label='Send']"))
        )
    except:
        rand_sleep(1.3, 3.2)

    buttons = driver.find_elements(By.CSS_SELECTOR, "span[data-icon='send'], div[aria-label='Send']")
    for btn in buttons:
        if btn.is_displayed():
            driver.execute_script("arguments[0].click();", btn)
            return True

    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ENTER)
    return True

def main():
    numbers = load_numbers(EXCEL_FILE, COUNTRY_PREFIX)
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-data-dir={get_chrome_user_data_dir(SENDER_PROFILE)}")
    options.add_argument("--disable-notifications")
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)
    driver.get("https://web.whatsapp.com/")
    input("Press ENTER once WhatsApp Web is fully loaded and logged in...")

    consecutive_failures = 0
    total = len(numbers)

    for i, num in enumerate(numbers, 1):
        try:
            driver.get(f"https://web.whatsapp.com/send?phone={num}")
            time.sleep(max(4.0, OPEN_CHAT_WAIT + random.uniform(-2.2, 3.5)))
            wait_for_chat_ready(driver)

            if not click_attach(driver):
                raise RuntimeError("Attach button not found or not clickable")

            sent = send_pdf(driver, ATTACHMENT_PATH)
            if not sent:
                raise RuntimeError("Failed to send PDF")

            print(f"[{i}/{total}] PDF sent to {num}")
            consecutive_failures = 0

            rand_sleep(9.0, 20.0)
            if random.random() < 0.07:
                rand_sleep(5.0, 18.0)

            if i % BATCH_SIZE == 0 and i != 0 and i < total:
                cooldown = random.uniform(BATCH_COOLDOWN_MIN, BATCH_COOLDOWN_MAX)
                print(f"Batch cooldown: sleeping {int(cooldown/60)} minutes...")
                time.sleep(cooldown)

        except Exception as e:
            consecutive_failures += 1
            print(f"[{i}/{total}] FAILED for {num}: {e}")
            rand_sleep(5.0, 12.0)
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"Too many consecutive failures. Cooling down {int(LONG_COOLDOWN_ON_FAIL/60)} minutes.")
                time.sleep(LONG_COOLDOWN_ON_FAIL)
                consecutive_failures = 0

    driver.quit()

if __name__ == "__main__":
    main()

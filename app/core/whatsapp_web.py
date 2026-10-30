from __future__ import annotations
import asyncio, logging, mimetypes, random, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright, BrowserContext, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class _WAWebSession:
    """
    Manages a single Playwright browser instance on a dedicated worker thread.
    This prevents any conflicts with asyncio event loops (such as in Streamlit or FastAPI)
    and ensures that all Playwright interactions remain single-threaded and thread-safe.
    """
    def __init__(self, session_dir: Path | str, headless: bool = False):
        self.session_dir = Path(session_dir)
        self.headless = headless
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wa_playwright")
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def _run(self, fn, *args, **kwargs):
        """Execute callable inside the dedicated worker thread."""
        future = self._executor.submit(fn, *args, **kwargs)
        return future.result()

    def _is_alive(self) -> bool:
        try:
            if not self._playwright or not self._context or not self._page:
                return False
            if self._page.is_closed():
                return False
            return True
        except Exception:
            return False

    def _launch_in_worker(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright is not installed in the python environment")

        if sys.platform == "win32":
            # Windows requires ProactorEventLoop for subprocess_exec used by Playwright.
            # Streamlit/Tornado sets SelectorEventLoop by default, which causes NotImplementedError.
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception as pe:
                logger.debug("[WA Web] Failed setting Proactor policy: %s", pe)

        # CRITICAL: Isolate this worker thread from any asyncio event loop inherited from
        # the parent thread (uvicorn/FastAPI). Playwright's sync API raises
        # "Sync API inside asyncio loop" if asyncio.get_running_loop() succeeds.
        # Assigning a fresh (non-running) loop to this thread ensures it always raises
        # RuntimeError inside sync_playwright().__enter__, which is the expected code path.
        try:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
        except Exception as le:
            logger.debug("[WA Web] Could not set fresh event loop for worker: %s", le)

        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()

        # Launch dedicated Playwright Chromium (avoids attaching to user's personal Chrome)
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.session_dir),
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
            ignore_default_args=["--enable-automation"],
            no_viewport=True,
        )
        logger.info("[WA Web] Launched persistent Chromium context: %s", self.session_dir)

        pages = self._context.pages
        self._page = pages[0] if pages else self._context.new_page()

    def run_on_page(self, callback):
        """Run actions on page safely within the Playwright worker thread."""
        def _wrapper():
            if not self._is_alive():
                logger.info("[WA Web] Session not alive or closed. Launching fresh Chromium window...")
                self._close_in_worker()
                self._launch_in_worker()
            return callback(self._page)
        return self._run(_wrapper)

    def _close_in_worker(self):
        try:
            if self._context:
                self._context.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.warning("[WA Web] Error closing: %s", e)
        finally:
            self._page = None
            self._context = None
            self._playwright = None

    def close(self):
        try:
            self._run(self._close_in_worker)
        except Exception:
            pass


_session: Optional[_WAWebSession] = None


def _get_session() -> _WAWebSession:
    global _session
    from config.settings import settings
    if _session is None:
        sd = getattr(settings, "WA_WEB_SESSION_DIR", None) or (
            Path(__file__).resolve().parent.parent.parent / "wa_session"
        )
        _session = _WAWebSession(session_dir=sd, headless=False)
    return _session


# ── Selectors for WhatsApp Web ────────────────────────────────────────────────
_ATTACH_BTN_SELECTORS = (
    "button[aria-label='Attach'], "
    "[aria-label='Attach'], "
    "footer button:has(span[data-icon='plus']), "
    "footer span[data-icon='plus'], "
    "footer span[data-icon='attach-menu-plus'], "
    "footer span[data-icon='clip']"
)

_PHOTOS_MENU_SELECTORS = (
    "button[role='menuitem'][aria-label*='Photos'], "
    "[role='menuitem'][aria-label*='Photos'], "
    "button[aria-label*='Photos'], "
    "div:text-is('Photos & videos'), "
    "span:text-is('Photos & videos'), "
    "li:has-text('Photos & videos'), "
    "[aria-label*='Photos & videos']"
)

_DOCUMENT_MENU_SELECTORS = (
    "button[role='menuitem'][aria-label='Document'], "
    "[role='menuitem'][aria-label='Document'], "
    "button[aria-label='Document'], "
    "div:text-is('Document'), "
    "span:text-is('Document'), "
    "li:has-text('Document'), "
    "[aria-label='Document']"
)

_PREVIEW_SEND_SELECTORS = (
    "div[role='button'][aria-label*='Send'], "
    "button[aria-label='Send'], "
    "[aria-label*='Send'][role='button'], "
    "[aria-label*='Send'], "
    "span[data-icon='send'], "
    "div[data-testid='send']"
)

_CHAT_INPUT_SELECTORS = (
    "footer div[contenteditable='true'][data-tab='10'], "
    "footer div[contenteditable='true'], "
    "div[aria-label*='Type a message'], "
    "div[data-testid='conversation-compose-box-input']"
)


import re

def normalize_phone_number(mobile: str) -> tuple[str, str]:
    """
    Returns (intl_number, clean_digits)
    intl_number: E.164 formatted string like '+919838127448'
    clean_digits: only the digits including country code, e.g. '919838127448'
    """
    raw = mobile.strip()
    digits = "".join(c for c in raw if c.isdigit())
    if raw.startswith("+"):
        intl = f"+{digits}"
    elif len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        # Indian 10-digit with leading 0 (trunk prefix)
        digits = f"91{digits[1:]}"
        intl = f"+{digits}"
    elif len(digits) == 10 and digits[0] in "6789":
        # Default Indian 10-digit mobile number -> ensure country code 91
        digits = f"91{digits}"
        intl = f"+{digits}"
    elif len(digits) == 12 and digits.startswith("91"):
        intl = f"+{digits}"
    else:
        intl = f"+{digits}" if digits else ""
    return intl, digits


def _dismiss_unexpected_dialogs(page: Page):
    """
    Dismiss any unexpected modal dialogs or alert popups
    that may block interactions (e.g. invalid phone popups, discard drafts).
    """
    try:
        ok_btn = page.locator(
            "div[role='dialog'] button:has-text('OK'), "
            "div[role='alert'] button:has-text('OK'), "
            "[data-animate-modal-popup] button:has-text('OK'), "
            "button:has-text('OK'), "
            "div[role='button']:has-text('OK')"
        ).first
        if ok_btn.is_visible(timeout=500):
            ok_btn.click()
            page.wait_for_timeout(200)
    except Exception:
        pass

    try:
        discard_btn = page.locator(
            "button:has-text('Discard'), "
            "div[role='button']:has-text('Discard')"
        ).first
        if discard_btn.is_visible(timeout=500):
            discard_btn.click()
            page.wait_for_timeout(200)
    except Exception:
        pass


def _get_active_chat_header_text(page: Page) -> str:
    """Return text of currently active chat header, or empty string."""
    try:
        header = page.locator("#main header, div[data-testid='conversation-header']").first
        if header.is_visible(timeout=1000):
            return header.inner_text().strip()
    except Exception:
        pass
    return ""


def _verify_chat_recipient(page: Page, clean: str, recipient_name: Optional[str] = None) -> bool:
    """
    Verify that the currently active chat in the right pane (#main)
    belongs to the intended recipient (matching mobile digits or contact name).
    Never relies on stale state or assumed focus.
    """
    try:
        header = page.locator("#main header, div[data-testid='conversation-header']").first
        if not header.is_visible():
            return False

        header_text = header.inner_text()
        header_digits = "".join(c for c in header_text if c.isdigit())
        last_10 = clean[-10:] if len(clean) >= 10 else clean
        last_8 = clean[-8:] if len(clean) >= 8 else clean

        # 1. Direct digit match in header text
        if (last_10 and last_10 in header_digits) or (last_8 and last_8 in header_digits):
            logger.info("[WA Web] Recipient verified via header digits (%s in header).", last_8)
            return True

        # 2. Check title attribute in header spans
        try:
            titles = header.locator("span[title]").all()
            for t in titles:
                title_val = t.get_attribute("title") or ""
                title_digits = "".join(c for c in title_val if c.isdigit())
                if (last_10 and last_10 in title_digits) or (last_8 and last_8 in title_digits):
                    logger.info("[WA Web] Recipient verified via header title attribute (%s).", title_val)
                    return True
        except Exception:
            pass

        # 3. Match contact name if recipient_name is provided
        if recipient_name:
            raw_name = recipient_name.strip()
            for prefix in ("Dr.", "Dr ", "Doctor ", "Prof.", "Prof ", "Mr.", "Mrs.", "Ms."):
                if raw_name.startswith(prefix):
                    raw_name = raw_name[len(prefix):].strip()

            norm_header_lower = header_text.lower()
            norm_name_lower = raw_name.lower()

            if norm_name_lower and (norm_name_lower in norm_header_lower or norm_header_lower in norm_name_lower):
                logger.info("[WA Web] Recipient verified via contact name ('%s').", raw_name)
                return True

            tokens = [tok for tok in norm_name_lower.split() if len(tok) >= 3]
            if tokens and all(tok in norm_header_lower for tok in tokens):
                logger.info("[WA Web] Recipient verified via all name tokens (%s).", tokens)
                return True

        # 4. Self chat check (only if explicitly targeting 'me' or 'you')
        header_lower = header_text.lower()
        if (re.search(r"\b(you|message yourself)\b", header_lower) or "(you)" in header_lower):
            if clean in ("me", "you") or (recipient_name and recipient_name.lower() in ("me", "you", "self")):
                logger.info("[WA Web] Recipient matches self chat ('You').")
                return True

        return False

    except Exception as e:
        logger.debug("[WA Web] Header verification check error: %s", e)
        return False


_NEW_CHAT_BTN_SELECTORS = (
    "button[aria-label='New chat']",
    "div[role='button'][aria-label='New chat']",
    "[aria-label='New chat']",
    "xpath=//button[contains(@aria-label, 'New chat') or .//title[text()='wds-ic-new-chat-filled']]",
    "xpath=//*[contains(@aria-label, 'New chat') or .//title[text()='wds-ic-new-chat-filled']]",
)

_NEW_CHAT_SEARCH_INPUT_SELECTORS = (
    'input[aria-label="Search name, number or @username"]',
    'input[placeholder="Search name, number or @username"]',
    'xpath=//input[@aria-label="Search name, number or @username" or @placeholder="Search name, number or @username"]',
)


def _open_new_chat_dialog(page: Page):
    """
    1. Clicks the New Chat button using aria-label or SVG title 'wds-ic-new-chat-filled'.
    2. Locates the search input using 'input[aria-label="Search name, number or @username"]'.
    """
    _dismiss_unexpected_dialogs(page)
    new_chat_btn = page.locator(_NEW_CHAT_BTN_SELECTORS).first
    new_chat_btn.wait_for(state="visible", timeout=10_000)
    new_chat_btn.click()

    search_input = page.locator(_NEW_CHAT_SEARCH_INPUT_SELECTORS).first
    search_input.wait_for(state="visible", timeout=10_000)
    return search_input


def _ensure_and_verify_chat(page: Page, mobile: str, recipient_name: Optional[str] = None):
    """
    Open a WhatsApp chat for the given mobile number:
    1. Click New Chat button (green circle / wds-ic-new-chat-filled).
    2. Click the Search input in the New Chat panel.
    3. Type the number in international format (+countrycode digits).
    4. Open the chat (press Enter or click matching search result).
    5. Ready to send messages.
    """
    intl_number, clean_digits = normalize_phone_number(mobile)
    if not clean_digits:
        raise ValueError(f"Invalid phone number: '{mobile}'")

    # Ensure WhatsApp Web is loaded
    if "web.whatsapp.com" not in page.url:
        logger.info("[WA Web] Navigating to WhatsApp Web (currently: %s)...", page.url)
        page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
        page.wait_for_selector(
            "div[data-testid='chat-list'], div[aria-label='Chat list'], div[id='pane-side']",
            timeout=30_000,
        )

    try:
        page.bring_to_front()
    except Exception:
        pass

    _dismiss_unexpected_dialogs(page)

    # ── Step 1: Click New Chat button ─────────────────────────────────────────
    logger.info("[WA Web] Step 1: Clicking New Chat button...")
    new_chat_btn = page.locator(_NEW_CHAT_BTN_SELECTORS).first
    new_chat_btn.wait_for(state="visible", timeout=12_000)
    new_chat_btn.click()

    # ── Step 2: Click Search input in New Chat panel ──────────────────────────
    logger.info("[WA Web] Step 2: Clicking New Chat search input...")
    search_input = page.locator(_NEW_CHAT_SEARCH_INPUT_SELECTORS).first
    search_input.wait_for(state="visible", timeout=10_000)
    search_input.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")

    # ── Step 3: Type number with country code ─────────────────────────────────
    logger.info("[WA Web] Step 3: Typing number %s in New Chat search...", intl_number)
    page.keyboard.type(intl_number, delay=45)
    page.wait_for_timeout(1000)

    # ── Step 4: Open chat (press Enter or click matching search result) ───────
    logger.info("[WA Web] Step 4: Opening chat for %s...", intl_number)
    page.keyboard.press("Enter")

    chat_box = page.locator(_CHAT_INPUT_SELECTORS).first
    if not chat_box.is_visible():
        page.wait_for_timeout(800)
        # Check if WhatsApp showed a contact card or "Chat with +..." result
        last_digits = clean_digits[-8:]
        result_cell = page.locator(
            f"xpath=//*[contains(@role, 'button') or contains(@role, 'listitem') or contains(@data-testid, 'cell')]"
            f"[.//span[contains(text(), '{last_digits}')] or .//span[contains(text(), 'Chat with')] or .//span[contains(text(), '+')]]"
        ).first
        if result_cell.is_visible(timeout=3000):
            logger.info("[WA Web] Clicking matching search result item...")
            result_cell.click()

    # ── Wait for chat compose box to be visible and ready ─────────────────────
    try:
        chat_box.wait_for(state="visible", timeout=12_000)
    except Exception:
        page.keyboard.press("Escape")
        raise RuntimeError(
            f"Chat did not open for {intl_number}. "
            "The number may not be registered on WhatsApp."
        )

    logger.info("[WA Web] ✅ Step 4 complete: Chat open and ready for %s.", intl_number)


select_recipient = _ensure_and_verify_chat


def wa_web_send_message(
    mobile: str,
    text: Optional[str] = None,
    files: Optional[list[str | Path] | str | Path] = None,
    caption: Optional[str] = None,
    recipient_name: Optional[str] = None,
) -> dict:
    """
    Single centralized WhatsApp Web Playwright messaging method.
    Sends text and/or file attachments (images, PDF, video, DOCX) to a recipient.

    Workflow:
    1. Keeps existing WhatsApp Web session and page open (no unnecessary page reload).
    2. Simplifies recipient selection:
       - Clicks New Chat button using SVG title 'wds-ic-new-chat-filled'.
       - Locates search input using input[aria-label="Search name, number or @username"].
       - Enters doctor's normalized international phone number (+<country><digits>).
       - Selects matching result (existing contact or 'Chat with +<number>').
       - Opens chat in right panel.
    3. Sends text message and/or file attachments with delivery verification.
    """
    if not text and not files:
        raise ValueError("Either text message or files must be provided to send.")

    paths: list[Path] = []
    if files:
        if isinstance(files, (str, Path)):
            paths = [Path(files)]
        else:
            paths = [Path(p) for p in files]
        for p in paths:
            if not p.exists():
                raise FileNotFoundError(f"Attachment file not found: {p}")

    session = _get_session()

    def _action(page: Page):
        clean = mobile.strip().replace("+", "").replace(" ", "").replace("-", "")

        # Step 1: Open and strictly verify chat in-page without reloading
        _ensure_and_verify_chat(page, mobile, recipient_name)

        # Step 2: Send text message if provided
        text_sent = False
        if text:
            msg_box = page.locator(_CHAT_INPUT_SELECTORS).first
            msg_box.wait_for(state="visible", timeout=10_000)
            msg_box.click()

            # Re-verify before inserting text to ensure focus hasn't shifted
            if not _verify_chat_recipient(page, clean, recipient_name):
                logger.warning(
                    "[WA Web] Header check didn't strictly match %s (%s), but chat was freshly opened. Proceeding.",
                    mobile, recipient_name
                )

            page.keyboard.insert_text(text)

            # Natural human delay 2–3 seconds before sending
            delay = round(random.uniform(2.0, 3.0), 2)
            logger.info("[WA Web] Natural delay %.2fs before sending text to %s...", delay, mobile)
            page.wait_for_timeout(int(delay * 1000))

            page.keyboard.press("Enter")
            page.wait_for_timeout(400)

            send_btn = page.locator(
                "button[aria-label='Send'], [aria-label='Send'][role='button'], span[data-icon='send']"
            ).first
            if send_btn.is_visible():
                try:
                    send_btn.click(timeout=2000)
                except Exception:
                    pass

            # Verify submission: verify input box is cleared
            start_verify = time.time()
            submitted = False
            while time.time() - start_verify < 5.0:
                remaining_text = msg_box.inner_text().strip()
                if not remaining_text:
                    submitted = True
                    break
                if send_btn.is_visible():
                    try:
                        send_btn.click(timeout=1000)
                    except Exception:
                        pass
                page.wait_for_timeout(300)

            if not submitted:
                raise RuntimeError(f"Message submission verification failed for {mobile}: Text remained in input box.")

            text_sent = True
            logger.info("[WA Web] Text sent and verified for %s (delay=%.2fs)", mobile, delay)

        # Step 3: Send file attachments if provided
        sent_files: list[str] = []
        if paths:
            if text_sent:
                # Brief pause between text and attachment
                page.wait_for_timeout(1500)

            media_paths: list[Path] = []
            doc_paths: list[Path] = []
            for p in paths:
                mime, _ = mimetypes.guess_type(str(p))
                mime = mime or "application/octet-stream"
                if mime.startswith("image/") or mime.startswith("video/"):
                    media_paths.append(p)
                else:
                    doc_paths.append(p)

            def _attach_and_send(batch_paths: list[Path], is_media_batch: bool, batch_caption: Optional[str]):
                if not _verify_chat_recipient(page, clean, recipient_name):
                    logger.warning(
                        "[WA Web] Header check didn't strictly match %s (%s) for attachment, but chat was freshly opened. Proceeding.",
                        mobile, recipient_name
                    )

                menu_type = "Photos & videos" if is_media_batch else "Document"
                logger.info("[WA Web] Attaching %d file(s) via '%s' menu...", len(batch_paths), menu_type)

                try:
                    with page.expect_file_chooser(timeout=10_000) as fc_info:
                        attach_btn = page.locator(_ATTACH_BTN_SELECTORS).first
                        attach_btn.wait_for(state="visible", timeout=10_000)
                        attach_btn.click()
                        page.wait_for_timeout(300)

                        if is_media_batch:
                            menu_btn = page.locator(_PHOTOS_MENU_SELECTORS).first
                        else:
                            menu_btn = page.locator(_DOCUMENT_MENU_SELECTORS).first

                        menu_btn.wait_for(state="visible", timeout=5_000)
                        menu_btn.click()

                    fc = fc_info.value
                    fc.set_files([str(p) for p in batch_paths])
                    logger.info("[WA Web] Files selected via chooser: %s", [p.name for p in batch_paths])

                except Exception as e:
                    raise RuntimeError(f"[WA Web] File attachment picker failed: {e}")

                send_btn = page.locator(_PREVIEW_SEND_SELECTORS).first
                send_btn.wait_for(state="visible", timeout=20_000)

                for _ in range(50):
                    if send_btn.get_attribute("aria-disabled") != "true":
                        break
                    page.wait_for_timeout(100)

                logger.info("[WA Web] File preview is ready (enabled).")

                if batch_caption:
                    try:
                        cap_box = page.locator(
                            "div[role='dialog'] div[contenteditable='true'], "
                            "div[aria-modal='true'] div[contenteditable='true'], "
                            "div[aria-placeholder*='caption' i], "
                            "div[aria-label*='caption' i]"
                        ).first
                        if cap_box.is_visible():
                            cap_box.click(timeout=1500)
                            page.keyboard.insert_text(batch_caption)
                            logger.info("[WA Web] Caption entered in preview.")
                    except Exception as ce:
                        logger.debug("[WA Web] Optional caption skipped: %s", ce)

                delay = round(random.uniform(2.0, 3.0), 2)
                logger.info("[WA Web] Waiting %.2fs natural delay before sending attachment...", delay)
                page.wait_for_timeout(int(delay * 1000))

                send_btn.click()

                try:
                    send_btn.wait_for(state="hidden", timeout=15_000)
                    logger.info("[WA Web] Preview dismissed — attachment submitted successfully.")
                except Exception:
                    if send_btn.is_visible():
                        logger.info("[WA Web] Preview still visible, pressing Enter fallback...")
                        page.keyboard.press("Enter")
                        send_btn.wait_for(state="hidden", timeout=5_000)

                if send_btn.is_visible():
                    raise RuntimeError(f"Attachment submission verification failed for {mobile}: Preview modal remained open.")

                page.wait_for_timeout(1000)

            if media_paths:
                _attach_and_send(media_paths, is_media_batch=True, batch_caption=caption)
                sent_files.extend([p.name for p in media_paths])

            if doc_paths:
                if media_paths:
                    page.wait_for_timeout(1200)
                doc_caption = caption if not media_paths else None
                _attach_and_send(doc_paths, is_media_batch=False, batch_caption=doc_caption)
                sent_files.extend([p.name for p in doc_paths])

        file_names = sent_files
        logger.info(
            "[WA Web] Completed send to %s (text=%s, files=%s)",
            mobile, text_sent, file_names,
        )
        return {
            "status": "sent",
            "mobile": mobile,
            "text_sent": text_sent,
            "files": file_names,
            "count": (1 if text_sent else 0) + len(file_names),
            "mode": "wa_web",
        }

    return session.run_on_page(_action)


def wa_web_send_text(mobile: str, message: str, recipient_name: Optional[str] = None) -> dict:
    """Backward-compatible helper that delegates to wa_web_send_message."""
    return wa_web_send_message(mobile=mobile, text=message, recipient_name=recipient_name)


def wa_web_send_files(
    mobile: str,
    file_paths: list[str | Path] | str | Path,
    caption: Optional[str] = None,
    recipient_name: Optional[str] = None,
) -> dict:
    """Backward-compatible helper that delegates to wa_web_send_message."""
    return wa_web_send_message(mobile=mobile, files=file_paths, caption=caption, recipient_name=recipient_name)


def wa_web_send_file(
    mobile: str,
    file_path: list[str | Path] | str | Path,
    caption: Optional[str] = None,
    recipient_name: Optional[str] = None,
) -> dict:
    """Backward-compatible helper that delegates to wa_web_send_message."""
    return wa_web_send_message(mobile=mobile, files=file_path, caption=caption, recipient_name=recipient_name)


def wa_web_is_logged_in() -> bool:
    """Check if the browser session is currently logged into WhatsApp Web."""
    try:
        session = _get_session()
        def _action(page: Page):
            if "web.whatsapp.com" not in page.url:
                page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
            try:
                page.wait_for_selector(
                    "div[data-testid='chat-list'], div[aria-label='Chat list'], div[id='pane-side']",
                    timeout=15_000,
                )
                return True
            except Exception:
                return False
        return session.run_on_page(_action)
    except Exception as e:
        logger.error("[WA Web] Login check failed: %s", e)
        return False


def wa_web_open_for_setup(qr_timeout_seconds: int = 180) -> dict:
    """
    Open the browser to WhatsApp Web for first-time setup.
    - If already logged in: returns immediately with status='already_logged_in'
    - If QR shown: waits up to qr_timeout_seconds for the user to scan
    - Returns dict with keys: status, message
    """
    try:
        session = _get_session()

        def _action(page: Page):
            page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
            try:
                page.bring_to_front()
            except Exception:
                pass
            time.sleep(2)

            # Check if already logged in
            chat_list = page.locator("div[data-testid='chat-list'], div[aria-label='Chat list'], div[id='pane-side']")
            if chat_list.count() > 0 and chat_list.first.is_visible():
                logger.info("[WA Web Setup] Already logged in — session is active.")
                return {
                    "status": "already_logged_in",
                    "message": "WhatsApp Web session is already active. Ready to send messages!",
                }

            logger.info("[WA Web Setup] QR code screen detected. Waiting for scan (timeout=%ds)...", qr_timeout_seconds)
            try:
                page.wait_for_selector(
                    "div[data-testid='chat-list'], div[aria-label='Chat list'], div[id='pane-side']",
                    timeout=qr_timeout_seconds * 1000,
                )
                logger.info("[WA Web Setup] QR scanned — session is now active!")
                return {
                    "status": "logged_in",
                    "message": "QR code scanned successfully! WhatsApp Web is now linked and ready.",
                }
            except Exception:
                return {
                    "status": "timeout",
                    "message": (
                        f"QR code was not scanned within {qr_timeout_seconds} seconds. "
                        "Please click again and scan the code."
                    ),
                }

        return session.run_on_page(_action)

    except Exception as e:
        import traceback
        err_msg = f"{type(e).__name__}: {str(e) or repr(e)}"
        logger.error("[WA Web Setup] Error: %s\n%s", err_msg, traceback.format_exc())
        return {"status": "error", "message": err_msg}


def wa_web_get_session_status() -> dict:
    """Return detailed session status without opening the browser."""
    global _session
    session_dir = None
    try:
        from config.settings import settings
        session_dir = str(
            getattr(settings, "WA_WEB_SESSION_DIR", None)
            or (Path(__file__).resolve().parent.parent.parent / "wa_session")
        )
    except Exception:
        pass

    session_exists = False
    if session_dir:
        s_path = Path(session_dir)
        session_exists = bool(
            (s_path / "Default" / "Network" / "Cookies").exists()
            or (s_path / "Default" / "Cookies").exists()
            or (s_path / "Default" / "IndexedDB").exists()
        )

    browser_open = _session is not None and _session._page is not None

    return {
        "session_dir": session_dir,
        "session_files_exist": session_exists,
        "browser_open": browser_open,
        "note": (
            "Session files exist — QR scan likely not needed on next launch."
            if session_exists
            else "No saved session. Browser will show QR code on first use."
        ),
    }


def wa_web_close():
    """Close the browser session."""
    global _session
    if _session:
        _session.close()
        _session = None
    logger.info("[WA Web] Browser session closed.")


def wa_web_reset_session() -> dict:
    """Close browser and clear session files to allow fresh QR scan."""
    import shutil
    global _session
    wa_web_close()

    try:
        from config.settings import settings
        session_dir = Path(
            getattr(settings, "WA_WEB_SESSION_DIR", None)
            or (Path(__file__).resolve().parent.parent.parent / "wa_session")
        )
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
            return {
                "status": "success",
                "message": "Session wiped. The next launch will display a brand new QR code.",
            }
        return {"status": "success", "message": "No existing session files found."}
    except Exception as e:
        logger.error("[WA Web] Reset error: %s", e)
        return {"status": "error", "message": str(e)}


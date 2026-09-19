"""Komanda marşrutlaşdırması və gündəlik xülasə planlayıcısı."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from html import escape

from . import service, tradingview
from .config import Config
from .storage import WatchlistStore
from .symbols import looks_like_ticker
from .telegram import TelegramClient, TelegramError

log = logging.getLogger(__name__)

# Komandasız yazılan açar sözlər: "nvidia izlə" / "izlə nvidia".
WATCH_WORDS = {"izle", "izlə", "watch", "follow"}
STOP_WORDS = {"dayan", "dayandir", "dayandır", "sil", "unwatch", "stop"}

# Bir mesajda neçə simvol yoxlanılsın (hər biri xarici sorğu tələb edir).
MAX_WATCH_ARGS = 10

HELP = """<b>İnvestisiya botu</b>

<b>Qiymət (TradingView)</b>
<code>/s AAPL MSFT NVDA</code> — 1 günlük və 1 həftəlik vəziyyət
Komandasız da olar — böyük hərflə və ya $ ilə: <code>AAPL MSFT</code>, <code>$tsla</code>

<b>Xəbərlər (Yahoo Finance)</b>
<code>/xeber AAPL</code> — həmin kağız üzrə son xəbərlər

<b>Xülasə</b>
<code>/xulase</code> — izləmə siyahısının cədvəli + ən çox hərəkət edənlərin xəbərləri

<b>İzləmə siyahısı</b>
<code>/izle NVDA</code> və ya <code>/izle nvidia</code> — əlavə et
<code>/sil NVDA</code> — çıxar
<code>/siyahi</code> — bax
Komandasız da olar: <code>nvidia izlə</code>, <code>nvidia dayan</code>
Şirkət adı da işləyir — bot özü ticker-i tapır və təsdiqləyir.

<code>/id</code> — bu chat-ın ID-si (gündəlik xülasə üçün lazımdır)

Birja prefiksi də işləyir: <code>BIST:THYAO</code>, <code>NASDAQ:AAPL</code>."""


class Bot:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = TelegramClient(config.token)
        self.store = WatchlistStore(config.state_path, config.default_watchlist)
        self._stop = threading.Event()

    # --- komandalar -----------------------------------------------------

    def handle_message(self, message: dict) -> None:
        chat_id = message["chat"]["id"]
        text = (message.get("text") or "").strip()
        if not text:
            return

        if not self.config.is_allowed(chat_id):
            log.info("icazəsiz chat rədd edildi: %s", chat_id)
            return

        command, args = _parse(text)
        log.info("chat=%s komanda=%s args=%s", chat_id, command, args)

        self.client.send_chat_action(chat_id)

        if command in ("/start", "/help", "/komek"):
            reply = HELP
        elif command == "/id":
            reply = f"Bu chat-ın ID-si: <code>{chat_id}</code>"
        elif command in ("/s", "/stock", "/qiymet"):
            targets = args or self.store.get(chat_id)
            if len(targets) == 1:
                self._send_quote(chat_id, targets[0])
                return
            reply = service.quotes_report(targets)
        elif command in ("/xeber", "/news"):
            reply = service.news_report(
                args or self.store.get(chat_id)[:3],
                self.config.news_per_symbol,
                self.config.news_max_age_days,
            )
        elif command in ("/xulase", "/digest"):
            reply = service.digest_report(
                self.store.get(chat_id),
                self.config.news_per_symbol,
                max_age_days=self.config.news_max_age_days,
            )
        elif command in ("/izle", "/watch"):
            reply = self._watch(chat_id, args)
        elif command in ("/sil", "/unwatch"):
            reply = self._unwatch(chat_id, args)
        elif command in ("/siyahi", "/list"):
            reply = _watchlist_text(self.store.get(chat_id))
        elif command is None:
            if not args:
                # Adi söhbətə qarışmırıq (xüsusilə qruplarda).
                return
            reply = service.quotes_report(args)
        else:
            reply = "Bu komandanı tanımıram. <code>/help</code> yaz."

        preview = command in ("/xeber", "/news")
        self.client.send_message(chat_id, reply, preview=preview)

    def _watch(self, chat_id: int, queries: list[str]) -> str:
        """Hər sorğunu təsdiqləyib siyahıya salır; tapılmayanı əlavə etmir."""

        if not queries:
            return "Nə əlavə edim? Məsələn: <code>/izle NVDA</code> və ya <code>/izle nvidia</code>"

        lines: list[str] = []
        to_add: list[str] = []
        added_matches: list[tuple[str, object]] = []
        for query in queries[:MAX_WATCH_ARGS]:
            best, others = service.find_symbol(query)
            if best is None:
                lines.append(
                    f"⚠️ <b>{escape(query)}</b> tapılmadı — əlavə edilmədi."
                )
                continue

            # İstifadəçi birjanı özü yazıbsa, o formanı saxlayırıq.
            stored = query if ":" in query else best.symbol
            tradingview.remember_symbol(best.symbol, best.full)
            to_add.append(stored)
            added_matches.append((stored, best))
            lines.append(f"✅ {escape(best.label)}")

            alternatives = [m for m in others if m.symbol != best.symbol][:2]
            if alternatives:
                alt = ", ".join(f"<code>/izle {escape(m.full)}</code>" for m in alternatives)
                lines.append(f"   <i>Başqası idisə: {alt}</i>")

        if not to_add:
            return "\n".join(lines) + "\n\n" + _watchlist_text(self.store.get(chat_id))

        current = self.store.add(chat_id, to_add)
        self.client.send_message(chat_id, "\n".join(lines))
        # Əlavə edən kimi cari vəziyyət — ayrıca /s yazmağa ehtiyac qalmasın.
        for ticker, match in added_matches:
            self._send_quote(chat_id, ticker, match.exchange)
        return _watchlist_text(current)

    def _send_quote(self, chat_id: int, ticker: str, exchange: str | None = None) -> None:
        """Qiyməti qrafiklə göndərir; qrafik alınmasa yalnız mətn gedir."""

        text, png = service.quote_card(ticker, exchange)
        if png:
            self.client.send_photo(chat_id, png, caption=text)
        else:
            self.client.send_message(chat_id, text)

    def _unwatch(self, chat_id: int, queries: list[str]) -> str:
        """Siyahıdan çıxarır; ad yazılıbsa əvvəlcə ticker-ə çevirir."""

        if not queries:
            return "Nəyi çıxarım? Məsələn: <code>/sil TSLA</code>"

        current = self.store.get(chat_id)
        lines: list[str] = []
        to_remove: list[str] = []
        for query in queries[:MAX_WATCH_ARGS]:
            if query in current:
                to_remove.append(query)
                lines.append(f"🗑 <b>{escape(query)}</b> çıxarıldı.")
                continue

            best, _ = service.find_symbol(query)
            if best and best.symbol in current:
                to_remove.append(best.symbol)
                lines.append(f"🗑 {escape(best.label)} çıxarıldı.")
            elif best and best.full in current:
                to_remove.append(best.full)
                lines.append(f"🗑 {escape(best.label)} çıxarıldı.")
            else:
                lines.append(f"⚠️ <b>{escape(query)}</b> siyahıda yox idi.")

        if to_remove:
            current = self.store.remove(chat_id, to_remove)
        return "\n".join(lines) + "\n\n" + _watchlist_text(current)

    # --- işləmə dövrü ---------------------------------------------------

    def run(self) -> None:
        me = self.client.get_me()
        log.info("bot işə düşdü: @%s", me.get("username"))

        if self.config.digest_enabled:
            threading.Thread(target=self._digest_loop, daemon=True).start()
            log.info(
                "gündəlik xülasə aktivdir: chat=%s saat=%s UTC",
                self.config.digest_chat_id,
                self.config.digest_time,
            )

        while not self._stop.is_set():
            try:
                for update in self.client.poll():
                    message = update.get("message")
                    if message:
                        try:
                            self.handle_message(message)
                        except Exception:
                            log.exception("mesaj emal edilmədi")
                            self._notify_failure(message)
            except TelegramError as exc:
                log.warning("Telegram xətası: %s", exc)
                time.sleep(5)
            except Exception:
                log.exception("gözlənilməz xəta")
                time.sleep(5)

    def stop(self) -> None:
        self._stop.set()

    def _notify_failure(self, message: dict) -> None:
        try:
            self.client.send_message(
                message["chat"]["id"], "Xəta baş verdi, bir azdan yenidən yoxla."
            )
        except TelegramError:
            log.debug("xəta bildirişi göndərilmədi")

    def _digest_loop(self) -> None:
        while not self._stop.is_set():
            wait = _seconds_until(self.config.digest_time)
            if self._stop.wait(wait):
                return
            try:
                chat_id = self.config.digest_chat_id
                report = service.digest_report(
                    self.store.get(chat_id),
                    self.config.news_per_symbol,
                    max_age_days=self.config.news_max_age_days,
                )
                self.client.send_message(chat_id, report)
            except Exception:
                log.exception("gündəlik xülasə göndərilmədi")
            # Eyni dəqiqədə ikinci dəfə işə düşməsin.
            self._stop.wait(60)


def _parse(text: str) -> tuple[str | None, list[str]]:
    """Mətni (komanda, arqumentlər) cütünə ayırır.

    Üç forma qəbul edilir:
      • <code>/izle nvidia</code> — adi komanda
      • <code>nvidia izlə</code> / <code>izlə nvidia</code> — açar söz
      • <code>AAPL MSFT</code> — yalnız açıq-aşkar simvollar (böyük hərf və ya $),
        ki adi söhbət ticker kimi başa düşülməsin.
    """

    parts = text.split()
    if not parts:
        return None, []

    head = parts[0]
    if head.startswith("/"):
        command = head.split("@", 1)[0].lower()  # /s@BotAdi -> /s
        return command, [_clean(p) for p in parts[1:] if _clean(p)]

    keyword = _keyword(parts[0])
    if keyword and len(parts) > 1:  # "izlə nvidia"
        return keyword, [_clean(p) for p in parts[1:] if _clean(p)]

    keyword = _keyword(parts[-1])
    if keyword and len(parts) > 1:  # "nvidia izlə"
        return keyword, [_clean(p) for p in parts[:-1] if _clean(p)]

    tickers = []
    for part in parts:
        cashtag = part.startswith("$")
        token = _clean(part)
        if not token or not looks_like_ticker(token):
            continue
        if cashtag or _clean(part) == part.strip(",.!?"):
            tickers.append(token)
    return None, tickers


def _keyword(word: str) -> str | None:
    """Açar sözü komandaya çevirir: `izlə` -> `/izle`, `dayan` -> `/sil`."""

    word = word.strip(",.!?").lower()
    if word in WATCH_WORDS:
        return "/izle"
    if word in STOP_WORDS:
        return "/sil"
    return None


def _clean(token: str) -> str:
    return token.lstrip("$").strip(",.!?").upper()


def _watchlist_text(tickers: list[str]) -> str:
    if not tickers:
        return "İzləmə siyahın boşdur. <code>/izle AAPL</code> ilə əlavə et."
    return "👁 <b>İzləmə siyahısı</b>\n" + ", ".join(f"<code>{t}</code>" for t in tickers)


def _seconds_until(hhmm: str) -> float:
    """Növbəti HH:MM (UTC) anına qədər saniyə."""

    hour, minute = (int(part) for part in hhmm.split(":"))
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()

# Telegram Invest Bot

Telegram botu: sən simvolları yazırsan, bot **TradingView**-dan həmin səhmlərin
**1 günlük və 1 həftəlik** vəziyyətini, **Yahoo Finance**-dən isə önəmli səhmlər
üzrə **xəbər xülasəsini** gətirir.

## Nə edir

| Komanda | İş |
| --- | --- |
| `/s AAPL MSFT NVDA` | Qiymət, 1 günlük və 1 həftəlik dəyişim (TradingView) |
| `AAPL MSFT` | Komandasız da işləyir — böyük hərflə və ya `$tsla` şəklində |
| `/xeber AAPL` | Yahoo Finance xəbərləri (başlıq, mənbə, neçə saat əvvəl, link) |
| `/xulase` | İzləmə siyahısının cədvəli + ən çox hərəkət edən 3 kağızın xəbərləri |
| `/izle NVDA` və ya `/izle nvidia` | İzləmə siyahısına əlavə (şirkət adı da olar) |
| `nvidia izlə` | Eyni iş, komandasız |
| `/sil NVDA`, `nvidia dayan` | İzləmə siyahısından çıxar |
| `/siyahi` | İzləmə siyahısına bax |
| `/id` | Bu chat-ın ID-si (gündəlik xülasə üçün lazımdır) |
| `/help` | Kömək |

Birja prefiksi də qəbul olunur: `NASDAQ:AAPL`, `BIST:THYAO`, `NYSE:BRK.B`.
Prefiks yazmasan, bot TradingView-un simvol axtarışı ilə birjanı özü tapır.

Siyahını **sən** formalaşdırırsan — bot özbaşına kağız seçmir. Yeganə istisna:
`/xulase` siyahındakı kağızlardan günün ən çox hərəkət edən 3-ünü seçib
xəbərlərini gətirir.

`/izle` əlavə etməzdən əvvəl simvolu **yoxlayır**: tapılmasa siyahıya salmır,
bir neçə uyğunluq olsa birincisini götürüb qalanlarını hazır komanda kimi
təklif edir:

```
✅ NVDA — NVIDIA Corporation (NASDAQ)
   Başqası idisə: /izle BMV:NVDA34
```

Nümunə cavab:

```
🟢 AAPL — Apple Inc. · NASDAQ
Qiymət: 232.45 USD
1 gün: +1.24%
1 həftə: -0.85%
1 ay: +4.10%
Həcm: 48.20M
Kapitallaşma: 3.42T
```

## Quraşdırma

```bash
git clone https://github.com/gurbansuleyman/Telegram-bot-invest.git
cd Telegram-bot-invest
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env faylına BotFather-dan aldığın tokeni yaz
python -m stockbot
```

Docker ilə:

```bash
docker build -t invest-bot .
docker run -d --env-file .env -v "$PWD/data:/data" --name invest-bot invest-bot
```

## Konfiqurasiya (.env)

| Dəyişən | İzah |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | **Məcburi.** BotFather tokeni |
| `ALLOWED_CHAT_IDS` | Yalnız bu chat-lara cavab verir. Boş = hamıya açıq |
| `DEFAULT_WATCHLIST` | Yeni chat üçün başlanğıc siyahı, məs. `AAPL,MSFT,NVDA` |
| `DIGEST_CHAT_ID` | Gündəlik xülasənin göndəriləcəyi chat (`/id` ilə öyrən) |
| `DIGEST_TIME` | Xülasə saatı, `HH:MM`, **UTC**. Boş = söndürülüb |
| `NEWS_PER_SYMBOL` | Hər simvol üçün xəbər sayı (default 4) |
| `STATE_PATH` | İzləmə siyahılarının JSON faylı (default `state.json`) |

Gündəlik xülasə üçün: botu işə sal → `/id` yaz → çıxan rəqəmi `DIGEST_CHAT_ID`-ə
yaz → `DIGEST_TIME=07:30` (UTC; Bakı vaxtı ilə 11:30) → botu yenidən başlat.

## Məlumat mənbələri

- **TradingView scanner** (`scanner.tradingview.com/global/scan`) — qiymət,
  `change` (1 gün), `Perf.W` (1 həftə), `Perf.1M`, həcm, kapitallaşma.
- **TradingView symbol search** — `nvidia` → `NASDAQ:NVDA` və `AAPL` →
  `NASDAQ:AAPL` çevrilməsi (nəticə yaddaşda saxlanılır). Cavab verməsə,
  Yahoo-nun axtarışı ilə eyni iş görülür.
- **Yahoo Finance search** (`query1.finance.yahoo.com/v1/finance/search`) — xəbərlər.
- **Yahoo Finance chart** (`.../v8/finance/chart/...`) — TradingView cavab
  vermədikdə ehtiyat qiymət mənbəyi; 1 həftə ≈ 5 ticarət günü kimi hesablanır.

Hər iki xidmət rəsmi/açıq API deyil, sənədləşdirilməmiş endpoint-lərdir:
sorğular təkrar cəhdlə (retry) göndərilir, biri cavab verməsə bot digərinə keçir,
ikisi də susarsa mesajda `Tapılmadı` yazılır.

## Layihə strukturu

```
stockbot/
  __main__.py     giriş nöqtəsi (.env oxuyur, botu qaldırır)
  bot.py          komandalar, gündəlik xülasə planlayıcısı
  service.py      TradingView + Yahoo birləşməsi, ehtiyat mənbə məntiqi
  tradingview.py  scanner + symbol search klienti
  yahoo.py        xəbərlər və ehtiyat qiymət klienti
  symbols.py      axtarış nəticələrinin modeli və sıralanması
  formatting.py   Telegram HTML mesajları
  telegram.py     Bot API long-polling klienti (yalnız requests)
  storage.py      chat-lara görə izləmə siyahısı (atomik JSON yazısı)
  config.py       mühit dəyişənləri
tests/            şəbəkəsiz vahid testlər (pytest)
```

## 24/7 işlətmək

macOS-da, pulsuz: `./deploy/install-macos.sh` — launchd xidməti qurur, Mac
açılanda bot özü işə düşür. Server variantı (systemd/Docker) və bütün
təfərrüatlar: [DEPLOY.md](DEPLOY.md).

## Branch modeli

| Branch | Rolu |
| --- | --- |
| `main` | Default branch. Həmişə işlək kod — server buradan deploy olunur |
| `feat/...`, `fix/...`, `docs/...` | Qısamüddətli iş branch-ları |
| tag `v0.1.0` | Buraxılış nişanı — serverdə hansı versiyanın işlədiyini bilmək üçün |

`main`-ə birbaşa commit edilmir: iş branch-ında dəyişiklik → PR → təsdiq →
merge → branch silinir. Bu, hər dəyişikliyin nə üçün edildiyini sonradan
izləməyə imkan verir.

```bash
git switch main && git pull
git switch -c feat/yeni-funksiya
# ... dəyişiklik, commit ...
git push -u origin feat/yeni-funksiya    # sonra GitHub-da PR aç
```

## Testlər

```bash
pip install pytest
python -m pytest tests -q
```

## Qeyd

Bot yalnız məlumat gətirir — investisiya məsləhəti vermir, sifariş göndərmir,
broker hesabına qoşulmur.

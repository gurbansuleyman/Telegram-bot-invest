# Botu işə salmaq

Üç ayrı şey var, qarışdırma:

| Nə | Rolu |
| --- | --- |
| **GitHub** | Kodun saxlandığı yer — botu işlətmir |
| **Server** (noutbuk və ya VPS) | Kodun **işlədiyi** yer — bot yalnız burada proses işlək olanda cavab verir |
| **Telegram** | İnterfeys — ayrıca app/APK lazım deyil, bot adi söhbət kimi işləyir |

Bot **long polling** ilə işləyir: özü Telegram-a qoşulur. Ona görə nə public IP,
nə domen, nə açıq port, nə SSL lazımdır. Sadəcə çıxış interneti kifayətdir.

---

## Addım 1 — Token al (2 dəqiqə)

1. Telegram-da **@BotFather**-ı aç
2. `/newbot`
3. Bot adı: məsələn `Invest Bot`
4. Username: `bot` ilə bitməlidir, məsələn `gurban_invest_bot`
5. Cavabdakı tokeni saxla:
   ```
   8123456789:AAH_qWeRtY-ExampleToken
   ```

Tokeni heç kimə vermə, git-ə commit etmə (`.env` onsuz da `.gitignore`-dadır).
Səhvən paylaşsan: BotFather → `/revoke`.

---

## Addım 2 — Lokal sınaq (5 dəqiqə)

Əvvəlcə öz kompüterində işlədib gör, hər şey qaydasındadırmı.

```bash
git clone https://github.com/gurbansuleyman/Telegram-bot-invest.git
cd Telegram-bot-invest

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
nano .env                          # TELEGRAM_BOT_TOKEN=... yaz

python -m stockbot
```

Konsolda `bot işə düşdü: @sənin_botun` görünməlidir. Telegram-da botu aç:

```
/start
/izle nvidia
/s AAPL
/xulase
```

Terminalı bağlasan bot dayanır — bu normaldır, lokal sınaq belədir.

Sonra `/id` yaz, çıxan rəqəmi `.env`-ə yaz:
```
ALLOWED_CHAT_IDS=123456789     # yalnız sənə cavab versin
DIGEST_CHAT_ID=123456789       # gündəlik xülasə bura gəlsin
DIGEST_TIME=07:30              # UTC! Bakı vaxtı 11:30 üçün 07:30
```

---

## Addım 3a — Mac-də 24/7 (pulsuz, launchd)

Mac açıq olduğu müddətdə bot işləsin: kompüter açılanda özü qalxsın, çöksə
özü yenidən başlasın, terminal bağlı olsun.

```bash
./deploy/install-macos.sh
```

Skript `.venv` və `.env`-i yoxlayır, `~/Library/LaunchAgents`-ə xidmət faylı
yazır və işə salır. Bir neçə saniyədən sonra:

```bash
tail -f ~/Library/Logs/investbot.log      # 'bot işə düşdü: @...' görünməlidir
```

Gündəlik idarəetmə:

| Əməliyyat | Komanda |
| --- | --- |
| Vəziyyət | `launchctl print gui/$(id -u)/com.gurbansuleyman.investbot \| head -20` |
| Loglar | `tail -f ~/Library/Logs/investbot.log` |
| Yenidən başlat | `launchctl kickstart -k gui/$(id -u)/com.gurbansuleyman.investbot` |
| Dayandır | `launchctl bootout gui/$(id -u)/com.gurbansuleyman.investbot` |
| Tamam sil | `./deploy/install-macos.sh --uninstall` |

Kodu yenilədikdən sonra (`git pull`) xidməti `kickstart -k` ilə yenidən başlat.

**Yuxu rejimi.** Xidmət `caffeinate -s -i` ilə işləyir: adaptere qoşulu olanda
Mac boşdayanma səbəbindən yuxuya getmir. Amma **qapağı bağlayanda macOS yenə
yatır** — bunu caffeinate dəyişmir. Qapaq bağlı işləsin istəyirsənsə, ya xarici
monitor qoş (clamshell), ya da növbəti addımdakı serverə keç.

Bot yatanda gələn mesajlar itmir — Telegram ~24 saat saxlayır və bot oyananda
hamısına cavab verir.

---

## Addım 3b — 24/7 üçün VPS (Hetzner)

Lokalda işlədisə, serverə keçiririk.

**Server:** Hetzner Cloud → **CAX11** (ARM, 2 vCPU / 4 GB, ~€3.8/ay),
location Falkenstein və ya Helsinki. Oracle Cloud Always Free də uyğundur
(ARM, pulsuz), amma bəzən "out of capacity" verir.

```bash
ssh root@SERVER_IP

apt update && apt install -y python3-venv git
adduser --disabled-password --gecos "" bot

git clone https://github.com/gurbansuleyman/Telegram-bot-invest.git /opt/invest-bot
cd /opt/invest-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
nano .env                    # token + ALLOWED_CHAT_IDS + DIGEST_*
chmod 600 .env
chown -R bot:bot /opt/invest-bot
```

`/etc/systemd/system/invest-bot.service`:

```ini
[Unit]
Description=Telegram Invest Bot
After=network-online.target

[Service]
Type=simple
User=bot
WorkingDirectory=/opt/invest-bot
EnvironmentFile=/opt/invest-bot/.env
ExecStart=/opt/invest-bot/.venv/bin/python -m stockbot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now invest-bot
systemctl status invest-bot
journalctl -u invest-bot -f        # canlı loglar
```

`Restart=always` sayəsində bot çöksə və ya server reboot olsa, özü qalxır.
Firewall-da yalnız SSH (22) açıq qalsın — bota port lazım deyil.

### Docker variantı

```bash
docker build -t invest-bot .
docker run -d --restart unless-stopped --env-file .env \
  -v "$PWD/data:/data" --name invest-bot invest-bot
docker logs -f invest-bot
```

---

## Yeniləmə

Server həmişə `main`-dən deploy olunur.

```bash
cd /opt/invest-bot
git pull origin main
.venv/bin/pip install -r requirements.txt
systemctl restart invest-bot
```

---

## Tez-tez rast gəlinən problemlər

| Problem | Səbəb / həll |
| --- | --- |
| `Konfiqurasiya xətası: TELEGRAM_BOT_TOKEN təyin edilməyib` | `.env` yoxdur və ya token yazılmayıb |
| Bot cavab vermir, log təmizdir | `ALLOWED_CHAT_IDS`-də sənin ID-n yoxdur |
| `Tapılmadı: XXX` | Simvol səhvdir, ya da TradingView/Yahoo müvəqqəti cavab vermir |
| `son 3 gündə yeni xəbər yoxdur` | Normaldır — filtr işləyir. Pəncərəni `NEWS_MAX_AGE_DAYS` ilə dəyiş |
| Gündəlik xülasə gəlmir | `DIGEST_TIME` **UTC**-dir; `DIGEST_CHAT_ID` boş ola bilməz |
| Bot söndü, mesajlar itdi? | İtmir — Telegram ~24 saat saxlayır, bot qalxanda cavab verir |

## APK / mobil app lazımdırmı?

Xeyr. Telegram özü interfeysdir — telefonda, kompüterdə, brauzerdə işləyir.
Ayrıca mobil app yalnız Telegram-dan tamamilə imtina etmək istəsən mənalı olar,
o isə sıfırdan başqa layihədir (push bildirişləri, App Store/Play Store, imza
sertifikatları). Bu botun məqsədi üçün lazımsızdır.

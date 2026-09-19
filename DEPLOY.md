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
git clone -b claude/funny-maxwell-qn9wq4 \
  https://github.com/gurbansuleyman/Telegram-bot-invest.git
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

## Addım 3 — 24/7 üçün VPS (Hetzner)

Lokalda işlədisə, serverə keçiririk.

**Server:** Hetzner Cloud → **CAX11** (ARM, 2 vCPU / 4 GB, ~€3.8/ay),
location Falkenstein və ya Helsinki. Oracle Cloud Always Free də uyğundur
(ARM, pulsuz), amma bəzən "out of capacity" verir.

```bash
ssh root@SERVER_IP

apt update && apt install -y python3-venv git
adduser --disabled-password --gecos "" bot

git clone -b claude/funny-maxwell-qn9wq4 \
  https://github.com/gurbansuleyman/Telegram-bot-invest.git /opt/invest-bot
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

```bash
cd /opt/invest-bot
git pull
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
| Gündəlik xülasə gəlmir | `DIGEST_TIME` **UTC**-dir; `DIGEST_CHAT_ID` boş ola bilməz |
| Bot söndü, mesajlar itdi? | İtmir — Telegram ~24 saat saxlayır, bot qalxanda cavab verir |

## APK / mobil app lazımdırmı?

Xeyr. Telegram özü interfeysdir — telefonda, kompüterdə, brauzerdə işləyir.
Ayrıca mobil app yalnız Telegram-dan tamamilə imtina etmək istəsən mənalı olar,
o isə sıfırdan başqa layihədir (push bildirişləri, App Store/Play Store, imza
sertifikatları). Bu botun məqsədi üçün lazımsızdır.

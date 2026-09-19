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

## Addım 3b — Oracle Cloud (pulsuz, 24/7)

Always Free hesabı həqiqətən pulsuzdur və müddətsizdir. Mac bağlı olsa da bot
işləyir.

### Hesab və maşın

1. **cloud.oracle.com** → *Sign up*. **Home Region** seçimi sonradan dəyişmir —
   Bakıdan ən uyğunu **Germany Central (Frankfurt)** və ya **UK South (London)**.
2. Kart tələb olunur — yalnız təsdiq üçün, pul çıxmır.
3. Konsol → *Compute* → *Instances* → *Create instance*.
4. **Image:** Ubuntu 24.04. **Shape:** *Ampere A1 Flex* (ARM), 1 OCPU / 6 GB —
   Always Free limiti 4 OCPU / 24 GB-dır, bota bundan azı da bəsdir.
   *Out of capacity* çıxsa: ya bir neçə saatdan sonra təkrar cəhd et, ya da
   **VM.Standard.E2.1.Micro** (AMD) götür — o, demək olar həmişə tapılır və
   bot üçün yetərlidir.
5. SSH açarını əlavə et. Yoxdursa: `ssh-keygen -t ed25519` → `~/.ssh/id_ed25519.pub`
   faylının məzmununu yapışdır.
6. *Create* → maşının **Public IP**-sini götür.

**Port açmaq lazım deyil.** Bot Telegram-a özü qoşulur (long polling), gələn
bağlantı qəbul etmir. Default security list-də yalnız SSH (22) açıqdır — elə
qalsın.

### Quraşdırma

```bash
ssh ubuntu@SERVER_IP

sudo apt update && sudo apt install -y git python3-venv
git clone https://github.com/gurbansuleyman/Telegram-bot-invest.git
cd Telegram-bot-invest

cp .env.example .env
nano .env        # TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_IDS, DIGEST_CHAT_ID, DIGEST_TIME

sudo ./deploy/install-linux.sh
```

Skript venv qurur, asılılıqları yükləyir, systemd xidmətini yazır və işə salır.
Xidmət root altında yox, repo sahibinin adından işləyir.

```bash
journalctl -u invest-bot -f        # 'bot işə düşdü: @...' görünməlidir
python -m stockbot.diagnose        # mənbələr serverdən necə cavab verir
```

Serverin IP-si Mac-dən fərqlidir — Yahoo orada bloklanmaya da bilər. `diagnose`
bunu göstərəcək.

| Əməliyyat | Komanda |
| --- | --- |
| Loglar | `journalctl -u invest-bot -f` |
| Vəziyyət | `systemctl status invest-bot` |
| Yenilə | `git pull && sudo systemctl restart invest-bot` |
| Dayandır | `sudo systemctl stop invest-bot` |
| Tamam sil | `sudo ./deploy/install-linux.sh --uninstall` |

Mac-dəki xidməti söndürməyi unutma, yoxsa iki bot eyni tokenlə polling edər və
mesajlar növbə ilə birinə, birinə düşər:

```bash
launchctl bootout gui/$(id -u)/com.gurbansuleyman.investbot
```

### Bilməli olduğun bir risk

Oracle **boş dayanan** Always Free maşınları geri ala bilər (7 gün ərzində CPU
davamlı çox aşağı olanda). Bizim bot demək olar heç bir CPU yemir, yəni bu
meyara düşə bilər. Qarşısını almağın yolu: hesabı **Pay As You Go**-ya keçirmək
— Always Free resursları yenə pulsuz qalır, sadəcə geri alınma qaydası tətbiq
olunmur. Kartdan pul çıxması üçün pulsuz limitdən kənara çıxmaq lazımdır.

---

## Addım 3c — Hetzner VPS (~€3.8/ay)

Oracle-da maşın tapa bilmirsənsə: Hetzner Cloud → **CAX11** (ARM, 2 vCPU / 4 GB),
location Falkenstein və ya Helsinki. Qeydiyyat daha sadədir, maşın həmişə var.

Quraşdırma Oracle ilə eynidir — eyni skript:

```bash
ssh root@SERVER_IP
apt update && apt install -y git python3-venv
git clone https://github.com/gurbansuleyman/Telegram-bot-invest.git
cd Telegram-bot-invest
cp .env.example .env && nano .env
sudo ./deploy/install-linux.sh
```

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
cd ~/Telegram-bot-invest
git pull origin main
.venv/bin/pip install -r requirements.txt
sudo systemctl restart invest-bot
```

---

## Tez-tez rast gəlinən problemlər

| Problem | Səbəb / həll |
| --- | --- |
| `Konfiqurasiya xətası: TELEGRAM_BOT_TOKEN təyin edilməyib` | `.env` yoxdur və ya token yazılmayıb |
| Bot cavab vermir, log təmizdir | `ALLOWED_CHAT_IDS`-də sənin ID-n yoxdur |
| `Tapılmadı: XXX` | Simvol səhvdir, ya da TradingView/Yahoo müvəqqəti cavab vermir |
| `son 3 gündə yeni xəbər yoxdur` | Normaldır — filtr işləyir. Pəncərəni `NEWS_MAX_AGE_DAYS` ilə dəyiş |
| Qrafik gəlmir, yalnız mətn | `pip install -r requirements.txt` (matplotlib), ya da heç bir tarixçə mənbəyi cavab vermir — `python -m stockbot.diagnose` səbəbi göstərir |
| Gündəlik xülasə gəlmir | `DIGEST_TIME` **UTC**-dir; `DIGEST_CHAT_ID` boş ola bilməz |
| Bot söndü, mesajlar itdi? | İtmir — Telegram ~24 saat saxlayır, bot qalxanda cavab verir |

## APK / mobil app lazımdırmı?

Xeyr. Telegram özü interfeysdir — telefonda, kompüterdə, brauzerdə işləyir.
Ayrıca mobil app yalnız Telegram-dan tamamilə imtina etmək istəsən mənalı olar,
o isə sıfırdan başqa layihədir (push bildirişləri, App Store/Play Store, imza
sertifikatları). Bu botun məqsədi üçün lazımsızdır.

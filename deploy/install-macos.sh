#!/usr/bin/env bash
#
# Botu macOS-da launchd xidməti kimi qurur: kompüter açılanda özü işə düşür,
# çökərsə özü qalxır, terminal bağlı olsa da işləyir.
#
#   ./deploy/install-macos.sh              — qur və işə sal
#   ./deploy/install-macos.sh --uninstall  — dayandır və sil
#
set -euo pipefail

LABEL="com.gurbansuleyman.investbot"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON="$REPO_DIR/.venv/bin/python"
LOG_DIR="$HOME/Library/Logs"
LOG="$LOG_DIR/investbot.log"
DOMAIN="gui/$(id -u)"

die() { echo "❌ $1" >&2; exit 1; }

stop_service() {
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
}

if [[ "${1:-}" == "--uninstall" ]]; then
    stop_service
    rm -f "$PLIST"
    echo "✅ Xidmət dayandırıldı və silindi."
    echo "   Loglar qaldı: $LOG"
    exit 0
fi

[[ "$(uname)" == "Darwin" ]] || die "Bu skript yalnız macOS üçündür."
[[ -x "$PYTHON" ]] || die "Virtual mühit tapılmadı: $PYTHON
   Əvvəlcə: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
[[ -f "$REPO_DIR/.env" ]] || die ".env faylı yoxdur.
   cp .env.example .env — sonra TELEGRAM_BOT_TOKEN-i yaz."

grep -q '^TELEGRAM_BOT_TOKEN=.\+' "$REPO_DIR/.env" \
    || die ".env faylında TELEGRAM_BOT_TOKEN boşdur."

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

# caffeinate: bot işlədiyi müddətdə Mac boşdayanma səbəbindən yuxuya getmir.
# (Qapağı bağlamaq yenə yuxuya salır — bu, launchd-nin yox, macOS-un qaydasıdır.)
cat > "$PLIST" <<PLIST_XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-s</string>
        <string>-i</string>
        <string>$PYTHON</string>
        <string>-m</string>
        <string>stockbot</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <!-- Konfiqurasiya səhv olsa, saniyədə bir yenidən başlamasın. -->
    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>StandardOutPath</key>
    <string>$LOG</string>
    <key>StandardErrorPath</key>
    <string>$LOG</string>
</dict>
</plist>
PLIST_XML

plutil -lint "$PLIST" >/dev/null || die "plist faylı düzgün alınmadı: $PLIST"

stop_service
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl enable "$DOMAIN/$LABEL"

echo "✅ Quruldu: $LABEL"
echo
echo "   Vəziyyət:   launchctl print $DOMAIN/$LABEL | head -20"
echo "   Loglar:     tail -f $LOG"
echo "   Dayandır:   launchctl bootout $DOMAIN/$LABEL"
echo "   Yenidən:    launchctl kickstart -k $DOMAIN/$LABEL"
echo "   Tamam sil:  ./deploy/install-macos.sh --uninstall"
echo
echo "Bir neçə saniyə sonra logda 'bot işə düşdü' sətrini görməlisən."

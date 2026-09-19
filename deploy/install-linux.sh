#!/usr/bin/env bash
#
# Botu Linux serverdə systemd xidməti kimi qurur (Oracle Cloud, Hetzner, VPS).
# Repo qovluğunun içindən işlədilir:
#
#   sudo ./deploy/install-linux.sh              — qur və işə sal
#   sudo ./deploy/install-linux.sh --uninstall  — dayandır və sil
#
set -euo pipefail

SERVICE="invest-bot"
UNIT="/etc/systemd/system/$SERVICE.service"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_DIR/.venv"
PYTHON="$VENV/bin/python"

die() { echo "❌ $1" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "sudo ilə işlət: sudo $0 ${1:-}"

if [[ "${1:-}" == "--uninstall" ]]; then
    systemctl disable --now "$SERVICE" 2>/dev/null || true
    rm -f "$UNIT"
    systemctl daemon-reload
    echo "✅ Xidmət dayandırıldı və silindi."
    exit 0
fi

# Xidmət repo sahibinin adından işləyir — root lazım deyil.
RUN_USER="${SUDO_USER:-$(stat -c '%U' "$REPO_DIR")}"
id "$RUN_USER" >/dev/null 2>&1 || die "İstifadəçi tapılmadı: $RUN_USER"

command -v python3 >/dev/null || die "python3 yoxdur: apt install -y python3 python3-venv"
python3 -c "import venv" 2>/dev/null || die "python3-venv yoxdur: apt install -y python3-venv"

[[ -f "$REPO_DIR/.env" ]] || die ".env faylı yoxdur.
   cp .env.example .env — sonra TELEGRAM_BOT_TOKEN-i yaz."
grep -q '^TELEGRAM_BOT_TOKEN=.\+' "$REPO_DIR/.env" \
    || die ".env faylında TELEGRAM_BOT_TOKEN boşdur."

if [[ ! -x "$PYTHON" ]]; then
    echo "→ Virtual mühit qurulur..."
    sudo -u "$RUN_USER" python3 -m venv "$VENV"
fi
echo "→ Asılılıqlar quraşdırılır..."
sudo -u "$RUN_USER" "$VENV/bin/pip" install --quiet --upgrade pip
sudo -u "$RUN_USER" "$VENV/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"

chown -R "$RUN_USER" "$REPO_DIR"
chmod 600 "$REPO_DIR/.env"

cat > "$UNIT" <<UNIT_FILE
[Unit]
Description=Telegram Invest Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO_DIR
EnvironmentFile=$REPO_DIR/.env
ExecStart=$PYTHON -m stockbot
Restart=always
RestartSec=10

# Sadə sərtləşdirmə: bota yalnız öz qovluğu lazımdır.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=$REPO_DIR

[Install]
WantedBy=multi-user.target
UNIT_FILE

systemctl daemon-reload
systemctl enable --now "$SERVICE"
sleep 2

echo
systemctl --no-pager --lines=0 status "$SERVICE" || true
echo
echo "✅ Quruldu. İstifadəçi: $RUN_USER"
echo
echo "   Loglar:     journalctl -u $SERVICE -f"
echo "   Yenidən:    sudo systemctl restart $SERVICE"
echo "   Dayandır:   sudo systemctl stop $SERVICE"
echo "   Yenilə:     git pull && sudo systemctl restart $SERVICE"
echo "   Tamam sil:  sudo ./deploy/install-linux.sh --uninstall"

#!/usr/bin/env bash
# One-time setup for the IdeaPad charge tray. Run with sudo.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run with sudo: sudo ./install.sh" >&2
    exit 1
fi

SRC="$(cd "$(dirname "$0")" && pwd)"
RUN_USER="${SUDO_USER:-}"

echo ">> Installing acpi_call (DKMS) + acpica (diagnostics)…"
# The prebuilt acpi_call only ships a module for the stock Arch kernel; on a
# custom kernel (e.g. linux-cachyos) it never loads. Build via DKMS against the
# running kernel's headers so it also rebuilds on every kernel update.
KPKG="$(pacman -Qqo "/usr/lib/modules/$(uname -r)/vmlinuz" 2>/dev/null || echo linux)"
pacman -S --needed --noconfirm dkms "${KPKG}-headers" acpi_call-dkms acpica

echo ">> Loading and persisting acpi_call…"
modprobe acpi_call || echo "   (modprobe failed now — reboot if the kernel was just updated)"
echo acpi_call > /etc/modules-load.d/acpi_call.conf

echo ">> Installing helper, tray, polkit rule…"
install -Dm755 "$SRC/ideapad-charge-helper" /usr/local/bin/ideapad-charge-helper
install -Dm755 "$SRC/ideapad_tray.py"       /usr/local/bin/ideapad-tray
install -Dm644 "$SRC/49-ideapad-charge.rules" /etc/polkit-1/rules.d/49-ideapad-charge.rules
install -Dm644 "$SRC/ideapad-tray.desktop"  /usr/share/applications/ideapad-tray.desktop
install -dm755 /var/lib/ideapad-charge

if [[ -n "$RUN_USER" ]]; then
    HOME_DIR="$(getent passwd "$RUN_USER" | cut -d: -f6)"
    AUTOSTART="$HOME_DIR/.config/autostart"
    install -dm755 -o "$RUN_USER" -g "$RUN_USER" "$AUTOSTART"
    install -Dm644 -o "$RUN_USER" -g "$RUN_USER" \
        "$SRC/ideapad-tray.desktop" "$AUTOSTART/ideapad-tray.desktop"
    echo ">> Autostart enabled for $RUN_USER"
fi

echo
echo "Done. Start it now with:  /usr/local/bin/ideapad-tray &"
echo "It will also start automatically on next login."

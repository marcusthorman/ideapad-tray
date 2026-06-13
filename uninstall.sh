#!/usr/bin/env bash
# Remove everything install.sh added (leaves the acpi_call package in place).
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run with sudo: sudo ./uninstall.sh" >&2
    exit 1
fi

RUN_USER="${SUDO_USER:-}"
rm -f /usr/local/bin/ideapad-charge-helper \
      /usr/local/bin/ideapad-tray \
      /etc/polkit-1/rules.d/49-ideapad-charge.rules \
      /usr/share/applications/ideapad-tray.desktop \
      /etc/modules-load.d/acpi_call.conf
rm -rf /var/lib/ideapad-charge

if [[ -n "$RUN_USER" ]]; then
    HOME_DIR="$(getent passwd "$RUN_USER" | cut -d: -f6)"
    rm -f "$HOME_DIR/.config/autostart/ideapad-tray.desktop"
fi

echo "Removed. The acpi_call package is left installed; remove with: pacman -R acpi_call"

#!/usr/bin/env python3
"""System-tray controller for IdeaPad conservation mode and fast charging.

Status (conservation mode, battery level, last-set fast-charge state) is read
straight from sysfs/state files with no privilege. Changes are applied through
the root helper via pkexec; a polkit rule makes that passwordless for `wheel`.
"""
import glob
import json
import os
import sys

from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

HELPER = "/usr/local/bin/ideapad-charge-helper"
CONSERVATION_GLOB = "/sys/bus/platform/drivers/ideapad_acpi/*/conservation_mode"
FASTCHARGE_STATE = "/var/lib/ideapad-charge/fastcharge"
ACPI_CALL = "/proc/acpi/call"
BAT = "/sys/class/power_supply/BAT0"
REFRESH_MS = 30_000


def _read_int(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def read_conservation():
    for p in glob.glob(CONSERVATION_GLOB):
        return _read_int(p)
    return None


def read_fastcharge():
    val = _read_int(FASTCHARGE_STATE)
    if read_conservation() == 1:
        return 0  # mutually exclusive in the EC
    return val if val is not None else -1


def read_battery():
    cap = _read_int(os.path.join(BAT, "capacity"))
    try:
        with open(os.path.join(BAT, "status")) as f:
            status = f.read().strip()
    except OSError:
        status = "Unknown"
    return cap, status


def fastcharge_available():
    return os.path.exists(ACPI_CALL)


def make_icon(capacity, conservation, fastcharge, charging):
    """Draw a battery glyph: green fill for conservation, a bolt for fast
    charge, with a dark+light double outline so it reads on any panel color."""
    px = QPixmap(64, 64)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    body = (8, 18, 42, 28)        # x, y, w, h
    nub = (50, 27, 5, 10)
    bx, by, bw, bh = body

    if conservation == 1:
        fill = QColor("#3ddc84")  # green = battery-saver
    elif fastcharge == 1:
        fill = QColor("#ffb300")  # amber = fast charging
    elif charging:
        fill = QColor("#8ab4f8")
    else:
        fill = QColor("#e0e0e0")

    pct = capacity if isinstance(capacity, int) else 100
    inner_w = max(2, int((bw - 6) * pct / 100))

    # double outline for contrast on light/dark panels
    for color, width in ((QColor(0, 0, 0, 160), 7), (QColor("#f5f5f5"), 3)):
        p.setPen(QPen(color, width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(bx, by, bw, bh, 4, 4)
        p.fillRect(nub[0], nub[1], nub[2], nub[3], color)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawRoundedRect(bx + 3, by + 3, inner_w, bh - 6, 2, 2)

    if fastcharge == 1:
        p.setPen(QPen(QColor("#222"), 1))
        p.setBrush(QColor("#fff8e1"))
        cx = bx + bw / 2
        bolt = [
            (cx + 3, by + 4), (cx - 5, by + bh / 2 + 1),
            (cx, by + bh / 2 + 1), (cx - 3, by + bh - 4),
            (cx + 5, by + bh / 2 - 1), (cx, by + bh / 2 - 1),
        ]
        from PyQt6.QtGui import QPolygonF
        from PyQt6.QtCore import QPointF
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in bolt]))

    p.end()
    return QIcon(px)


class Tray:
    def __init__(self, app):
        self.app = app
        self.tray = QSystemTrayIcon()
        self.tray.setToolTip("IdeaPad Charge")

        self.menu = QMenu()
        self.title = self.menu.addAction("IdeaPad Charge")
        self.title.setEnabled(False)
        self.menu.addSeparator()

        self.act_cons = QAction("Conservation mode", checkable=True)
        self.act_cons.triggered.connect(
            lambda on: self.apply("conservation", on))
        self.menu.addAction(self.act_cons)

        self.act_fast = QAction("Fast charging", checkable=True)
        self.act_fast.triggered.connect(
            lambda on: self.apply("fastcharge", on))
        self.menu.addAction(self.act_fast)

        self.menu.addSeparator()
        self.battery_item = self.menu.addAction("Battery: …")
        self.battery_item.setEnabled(False)
        self.menu.addSeparator()
        self.menu.addAction("Refresh", self.refresh)
        self.menu.addAction("Quit", self.app.quit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)
        self.tray.setIcon(make_icon(None, None, None, False))  # before show(): SNI needs an icon to register
        self.tray.show()

        self._busy = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(REFRESH_MS)
        self.refresh()
        self._sync_from_ec()

    def _sync_from_ec(self):
        """Run `helper get` once at startup: it reads the real rapid-charge
        state from the EC and rewrites the state file if it went stale."""
        proc = QProcess()
        self._busy.append(proc)

        def finished(_code, _status):
            if proc in self._busy:
                self._busy.remove(proc)
            self.refresh()

        proc.finished.connect(finished)
        proc.start("pkexec", [HELPER, "get"])

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.refresh()
            self.menu.popup(self.tray.geometry().center())

    def refresh(self):
        cons = read_conservation()
        fast = read_fastcharge()
        cap, status = read_battery()
        charging = status.lower() in ("charging", "full")

        self.act_cons.setChecked(cons == 1)
        self.act_cons.setEnabled(cons is not None)
        self.act_fast.setChecked(fast == 1)
        self.act_fast.setEnabled(fastcharge_available())
        if not fastcharge_available():
            self.act_fast.setText("Fast charging (install acpi_call)")
        else:
            self.act_fast.setText("Fast charging")

        cap_txt = f"{cap}%" if cap is not None else "n/a"
        self.battery_item.setText(f"Battery: {cap_txt} · {status}")
        self.tray.setIcon(make_icon(cap, cons, fast, charging))

        bits = []
        if cons == 1:
            bits.append("conservation on")
        if fast == 1:
            bits.append("fast charging")
        self.tray.setToolTip(
            f"IdeaPad Charge — {cap_txt}" + (f" ({', '.join(bits)})" if bits else ""))

    def apply(self, what, on):
        proc = QProcess()
        self._busy.append(proc)

        def finished(_code, _status):
            err = bytes(proc.readAllStandardError()).decode().strip()
            if proc.exitCode() != 0:
                self.tray.showMessage(
                    "IdeaPad Charge",
                    err or f"Failed to set {what}",
                    QSystemTrayIcon.MessageIcon.Warning)
            if proc in self._busy:
                self._busy.remove(proc)
            self.refresh()

        proc.finished.connect(finished)
        proc.errorOccurred.connect(
            lambda _e: self.tray.showMessage(
                "IdeaPad Charge", "Could not run helper (pkexec).",
                QSystemTrayIcon.MessageIcon.Warning))
        # The checkable QAction already shows the requested state; leave it
        # until the helper finishes, then refresh() reconciles with reality.
        proc.start("pkexec", [HELPER, what, "on" if on else "off"])


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available.", file=sys.stderr)
        return 1
    Tray(app)  # kept alive by the event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

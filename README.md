# IdeaPad Charge Tray

![Python 3](https://img.shields.io/badge/python-3.x-blue?logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52?logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Linux%20%28Arch%2FCachyOS%29-1793d1?logo=archlinux&logoColor=white)
![Desktop](https://img.shields.io/badge/desktop-KDE%20Plasma-1d99f3?logo=kde&logoColor=white)

A KDE/Plasma system-tray app for the **Lenovo IdeaPad 5 Pro 16ACH6** (and other
`ideapad_laptop` machines) to toggle:

- **Conservation mode** — caps the battery at ~55–60 % to extend its lifespan.
- **Fast charging** (Rapid Charge) — charges faster when plugged in.

These two are mutually exclusive in the embedded controller; enabling one
disables the other automatically.

## How it works

| Function           | Mechanism                                                            | Privilege |
|--------------------|---------------------------------------------------------------------|-----------|
| Read status        | `…/conservation_mode` sysfs + battery sysfs                          | none      |
| Conservation toggle| writes `0/1` to the `ideapad_acpi` `conservation_mode` sysfs file    | root      |
| Fast charge toggle | `SBMC` ACPI method (`0x07` on / `0x08` off) via the `acpi_call` module | root    |

The tray (`ideapad_tray.py`) runs as your user and only reads status directly.
Writes go through `ideapad-charge-helper` (root) via `pkexec`. A polkit rule
scoped to that one binary makes it **passwordless for the `wheel` group**.

## Install

```sh
sudo ./install.sh
/usr/local/bin/ideapad-tray &   # start now; autostarts on next login
```

`install.sh` installs the `acpi_call` and `acpica` packages, loads + persists
the module, drops the helper/tray/polkit-rule into place, and enables autostart.

## Uninstall

```sh
sudo ./uninstall.sh
```

## Notes

- Fast-charge state is read back from the EC via the `GBMD` ACPI method
  (battery-mode bitfield; bit `0x4` = rapid charge, verified against this
  machine's DSDT) whenever the helper runs: on every toggle (which fails
  loudly if the EC rejects the change) and once at tray startup. Between
  helper runs the tray shows the cached value in
  `/var/lib/ideapad-charge/fastcharge`. On firmware without `GBMD` it falls
  back to last-value-set behavior.
- If a kernel update lands before the matching `acpi_call` build, `modprobe`
  may fail until reboot. Conservation mode keeps working regardless.
- Requires `python` with `PyQt6` (already present on this system).

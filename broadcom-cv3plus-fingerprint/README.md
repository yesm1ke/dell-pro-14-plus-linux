# broadcom-cv3plus-fingerprint

Fingerprint reader of the Dell Pro 14 Plus PB14250: Broadcom ControlVault3
Plus, USB `0a5c:5865` (product string "58200"), chip "Citadel B0 CID7". There is
no kernel driver; libfprint drives it from userspace over libusb. Upstream
libfprint knows only the older ControlVault3 (`0a5c:5842`-`5845`), so this
needs Broadcom's proprietary libfprint TOD module, loaded by
[`../libfprint-tod`](../libfprint-tod).

The package installs:

- `/usr/lib/libfprint-2/tod-1/libfprint-2-tod-1-broadcom-cv3plus.so`, the driver
- `/usr/lib/udev/rules.d/60-libfprint-2-device-broadcom-cv3plus.rules`, which
  enables USB autosuspend and tags `5864`-`5867` for libfprint
- `/var/lib/fprint/.broadcomCv3plusFW/`, the chip firmware (path compiled into
  the driver)

## Source

`brcm_linux_fp_6.4.372_6.4.062.0.tgz` from
[Broadcom's repository for Dell](https://packages.broadcom.com/artifactory/dell-controlvault-drivers/),
pinned by sha256. It is the same binary Dell and Canonical ship in their Ubuntu OEM
package `libfprint-2-tod1-broadcom-cv3plus 6.4.372-6.4.062.0-0ubuntu1~24.04.1~oem4`
(dell.archive.canonical.com). The firmware files are byte-identical. The `.so` has
the same Build ID and identical `.text`/`.rodata`/`.data`; the deb copy is only
stripped. The AUR package `libfprint-2-tod1-broadcom-cv3plus` uses the same
tarball but with `sha256sums=('SKIP')`.

What the binary does, from its imports and strings: it needs only
libfprint-2-tod, libcrypto and libc. It has no sockets, `exec`, `system` or
`popen`. It verifies firmware images with the bundled RSA-2048 public key
(`key.pem`; there is no private key) before it flashes them.

## Firmware flash on first use

On first access the driver compares the chip's firmware with the one shipped
here and flashes the chip if they differ. That takes about a minute; on this
laptop (2026-10-03) it went:

    Current AAI Version = 6.2.26.0, Current SBI Version = 93
    Updating ControlVault firmware from 6.2.26.0 to 6.4.62.0
    ... Control Vault firmware upgrade successful

6.4.62.0 is also what Dell ships for Windows: "Dell ControlVault3 Plus Driver
and Firmware" 6.4.48.61 A16, 2026-06-04. So this is no downgrade, and it fixes
the ReVault issues (DSA-2025-053, DSA-2025-228) on older chips. The sensor's own
firmware had no update ("Couldn't find UPDATABLE sensor-firmware"); that is
fine.

Keep the laptop on AC and awake while it runs:

    systemd-inhibit --what=sleep:idle:handle-lid-switch --why="ControlVault flash" sleep 1800 &
    journalctl -fu fprintd &
    fprintd-list $USER          # starts fprintd, which starts the flash

The fprintd instance that did the flash then ignores the device
("initialization error"). It exits when idle; on the next start the
device is there: `found 1 devices ... Broadcom Sensors cv3plus`.

## Authentication (PAM)

Do **not** run `omarchy-setup-security-fingerprint` on Omarchy. It installs
`libfprint-git`, which has no TOD support and conflicts with `libfprint-tod`.
Its detection (`omarchy-hw-fingerprint`) does not see this reader either.
[`setup-pam.sh`](setup-pam.sh) writes the same PAM lines without the package
step:

- `sudo` and `polkit-1`: `pam_fprintd` is `sufficient`, so a password still
  works after a timeout or a wrong finger. A clamshell gate skips the reader
  while the lid is shut.
- `omarchy-lock-fingerprint`: the lock screen runs fingerprint and password
  side by side.

```
fprintd-enroll && fprintd-verify
sudo ./setup-pam.sh              # or --lock-only: fingerprint only on the lock screen
```

`omarchy-remove-security-fingerprint` removes these lines again. It also
removes fprintd and libfprint.

## Notes

- fprintd's unit has `ProtectSystem=strict`, so the driver's writes to
  `/run/bcm_fw_status.txt` and `/run/bcm_cert_cache.dat` fail silently.
  Ubuntu runs the same unit; flashing, enrolling and verifying all work. No
  drop-in is needed.
- Dell's deb also creates a `broadcom-controlvault` group and sets an ACL on the
  device for the NFC daemon (`brcm_linux_nfc`, smartcard and contactless). The
  fingerprint reader does not need it, so it is not included here.
- Other laptops with `0a5c:5865` can have a different sensor behind the chip.
  On a Precision 3490 with a Goodix sensor the flash worked, but enrollment
  failed with `-99` every time
  ([report](https://github.com/jedbillyb/linux-fingerprint-drivers/issues/28)).
- Updating: Broadcom publishes new tarballs in the same directory. Bump
  `_fw`/`pkgver` and `sha256sums`, then compare with the next Dell OEM deb.

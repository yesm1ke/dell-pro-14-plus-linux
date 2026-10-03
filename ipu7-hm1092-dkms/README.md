# ipu7-hm1092-dkms

IR camera (Windows Hello) of the Dell Pro 14 Plus PB14250: Himax HM1092
(ACPI `HIMX1092`) on Intel IPU7, CSI-2 port 1, I2C through the Synaptics
SVP7500 bridge's USB I2C (`usbio`). Monochrome, 648x368 RAW10 at ~30 fps, with
an IR flood LED.

No Intel or Dell Linux driver exists. Two modules, built by DKMS into
`updates/dkms`:

- `hm1092.ko`: the sensor driver from
  [svp7500-camera-fix-pack](https://github.com/jibsta210/svp7500-camera-fix-pack)
  (`dkms/hm1092-1.0/hm1092.c`, pinned commit and sha256) plus three patches:
  - `0001` powers the sensor only while it is used (runtime PM, 2 s
    autosuspend). The original keeps it powered from probe on.
  - `0002` takes the IR flood LED that the in-tree INT3472 driver registers
    (`HIMX1092_00::ir_flood_led`, lookup `ir_flood`) and lights it from
    stream-on to stream-off. Without it the frames are black unless user space
    switches the LED on. While the driver holds the LED, its sysfs
    `brightness` is read-only.
  - `0003` moves the probe/stream chatter to `dev_dbg` and drops the debug
    sysfs `stream` file.
- `ipu-bridge.ko`: **replaces the stock ipu-bridge**. It is the stock kernel's
  own source, rebuilt with one extra line for `HIMX1092` (1 lane, 180.48 MHz).
  Without that line ipu-bridge skips the sensor and the IPU never links it.
  The source is v7.2.5 (kernel.org) + the ipu-bridge hunks of linux-omarchy
  patches 0540/0541 (omarchy-pkgs, pinned). `prepare()` checks that the
  result is byte-identical to the stock linux-omarchy 7.2.5-3 ipu-bridge
  before adding the line.

The rest is in-tree: `intel_cvs`, `int3472` (regulator, clock, LED),
`usbio`, and the IPU7 drivers (stock or `../ipu7-intel-dkms`, both work).
The RGB camera is not affected; its graph stays `ov05c10 -> Intel CVS -> CSI2 0`.

The ipu-bridge entry is expected upstream (accepted in principle on
linux-media, 2026-08); once a kernel has it, only `hm1092.ko` is needed.

## Kernel updates

ipu-bridge is part of the RGB camera stack too, so this package must never
install a copy built from another kernel's source. The DKMS `PRE_BUILD` step
`check-ipu-bridge` compares the stock module's `srcversion` (a checksum of
its source) with the one this package was made for (`0CF5B7892824698250CF34B`,
linux-omarchy 7.2.5-3). On a mismatch DKMS builds nothing: the kernel keeps
its stock modules, the RGB camera works, and the IR camera is gone until the
package is rebased:

1. Find the new kernel's ipu-bridge source (stable tag + the distro's
   patches), set `_kver` / `_omarchy`, update the sha256s.
2. Rebuild, compare `modinfo -F srcversion` of the built-but-unpatched module
   with the stock one, then put the new value in `check-ipu-bridge` and the
   new source sha256 in `prepare()`.
3. Check the HIMX1092 patch still applies; drop it (and the ipu-bridge module)
   if the kernel already has the entry.

## Install

```
sudo pacman -S --needed base-devel dkms linux-headers v4l-utils
makepkg -fC
sudo pacman -U ipu7-hm1092-dkms-*.pkg.tar.zst
reboot
```

## Check

```
modinfo -n ipu_bridge hm1092             # both in updates/dkms
journalctl -k -b | grep -E 'HIMX1092|hm1092'
# "Found supported sensor HIMX1092:00", "bind hm1092 15-0024 nlanes is 1 port is 1"
cat /sys/bus/i2c/devices/i2c-HIMX1092:00/power/runtime_status   # suspended when idle
```

Capture by hand (as root; `/dev/video8` is `root:video` with no uaccess ACL,
and node numbers can change between boots: `media-ctl -e "Intel IPU7 ISYS Capture 8"`):

```
media-ctl -d /dev/media0 -l '"Intel IPU7 CSI2 1":1 -> "Intel IPU7 ISYS Capture 8":0 [1]'
media-ctl -d /dev/media0 -V '"Intel IPU7 CSI2 1":0 [fmt:SGRBG10_1X10/648x368]'
media-ctl -d /dev/media0 -V '"Intel IPU7 CSI2 1":1 [fmt:SGRBG10_1X10/648x368]'
v4l2-ctl -d /dev/video8 --set-fmt-video=width=648,height=368,pixelformat=BA10
v4l2-ctl -d /dev/video8 --stream-mmap --stream-count=60 --stream-to=ir.raw
```

The LED lights while streaming, and the sensor suspends ~2 s after stop.
Frames are 16-bit little-endian containers with 10-bit values, 1344 bytes per
line (648 active pixels), and upside down: the module is mounted rotated
180°. The `SGRBG10` tag is what the sensor driver declares; the data is plain
greyscale, so do not debayer it (libcamera and PipeWire do, which gives a
broken picture).

## Face login with howdy

[`howdy/`](howdy): a recorder for howdy 2.6.1 (AUR `howdy`), whose OpenCV path
cannot read `BA10`. It sets up the media graph (by entity name), turns each
frame into upright 8-bit greyscale stretched to its 99th percentile, and
leaves the LED to the driver. `install-reader.sh` copies it into howdy and
sets `recording_plugin = hm1092`, `device_path = /dev/video8` and
`dark_threshold = 90`. The IR light falls off fast and ~70% of a frame is
near-black at night, so howdy's default 50 would drop every frame.

```
yay -S howdy
sudo ipu7-hm1092-dkms/howdy/install-reader.sh
sudo howdy add
sudo python3 /usr/lib/security/howdy/compare.py $USER; echo $?   # 0 = match, 11 = no match
```

`howdy test` refuses non-OpenCV recorders; `compare.py` is what PAM runs.
Tested 2026-10-03: match in ~4.4 s, no match (exit 11) when looking away.
PAM is not configured here. Howdy is a convenience, not a strong
authenticator: plain dlib face matching with no real anti-spoofing.
Omarchy's lock screen retries its fingerprint PAM service in a loop, so howdy
must not go into `omarchy-lock-fingerprint`, or the camera never turns off.

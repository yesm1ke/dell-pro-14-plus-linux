# Dell Pro 14 Plus camera on Linux

Arch Linux packages that make the built-in RGB camera of the **Dell Pro 14
Plus PB14250** (Intel Core Ultra 200V / Lunar Lake) work in every app, with
Intel's hardware ISP: Telegram, Zoom, OBS, browsers, PipeWire portals.

Tested on Core Ultra 7 266V, BIOS 2.18.1, kernel 7.2.5 (Arch / Omarchy),
2026-10-03: 1920x1080 at ~26 fps, auto exposure and white balance, privacy
LED on while streaming.

## Hardware

| Part | ID | Driver |
|---|---|---|
| IPU7 (Lunar Lake) | PCI `8086:645d` | `intel_ipu7`, `intel_ipu7_isys`, `intel_ipu7_psys` (Intel, `ipu7-intel-dkms`) |
| Sensor OmniVision OV05C10 | ACPI `OVTI05C1` | `ov05c10` (`ipu7-ov05c10-dkms`) |
| Synaptics SVP7500 vision bridge (Intel CVS) | ACPI `INTC10DE` | `intel_cvs` (in-tree) |
| Bridge USB I/O (I2C, GPIO) | ACPI `INTC10B5` | `usbio`, `i2c_usbio`, `gpio_usbio` (in-tree) |

Not covered: the HM1092 IR camera (Windows Hello) and the fingerprint reader.

The sensor's MIPI lanes and I2C go through the SVP7500 bridge, so the media
graph is `ov05c10 -> Intel CVS -> IPU7 CSI2 0`, and the bridge firmware owns
the sensor until the IPU starts streaming.

## Packages

Install in this order:

1. [`ipu7-ov05c10-dkms`](ipu7-ov05c10-dkms) - sensor driver from Intel's
   ipu6-drivers (pinned) + three patches: 480 MHz link frequency, chip ID read
   on first stream-on, privacy LED (DMI-gated).
2. [`ipu7-intel-dkms`](ipu7-intel-dkms) - Intel's IPU7 kernel drivers
   (pinned), replacing the stock staging ones, adds psys.
3. [`ipu7-intel-camera`](ipu7-intel-camera) - Intel camera HAL, imaging
   libraries and GStreamer `icamerasrc`, plus a config patch for the CVS hop.
4. [`ipu7-camera-loopback`](ipu7-camera-loopback) - virtual webcam "Built-in
   Camera" (`/dev/video50`, v4l2loopback) fed on demand by `v4l2-relayd`.
5. [`wireplumber/ipu7-camera.conf`](wireplumber/ipu7-camera.conf) - hides the
   raw IPU7 nodes from PipeWire, keeps PipeWire's libcamera monitor off.

```
sudo pacman -S --needed base-devel dkms linux-headers v4l2loopback-dkms gst-plugins-base
yay -S v4l2-relayd                       # AUR
for p in ipu7-ov05c10-dkms ipu7-intel-dkms ipu7-intel-camera ipu7-camera-loopback; do
  (cd $p && makepkg -fC -d) || break
done
sudo pacman -U */*.pkg.tar.zst
sudo systemctl enable v4l2-relayd.service
mkdir -p ~/.config/wireplumber/wireplumber.conf.d
cp wireplumber/ipu7-camera.conf ~/.config/wireplumber/wireplumber.conf.d/
reboot
```

Use the headers package of your kernel (`linux-zen-headers`, ...).

## Check

```
journalctl -k -b | grep -E 'ov05c10|psys|Intel CVS'   # "bind Intel CVS", "IPU psys probe done"
systemctl status v4l2-relayd@ipu7
wpctl status | sed -n '/^Video/,/^Settings/p'          # one source: "Built-in Camera (V4L2)"
gst-launch-1.0 v4l2src device=/dev/video50 num-buffers=60 ! videoconvert ! jpegenc ! multifilesink location=/tmp/f%02d.jpg
```

If the camera is missing in PipeWire after boot, WirePlumber started before
the relay: `systemctl --user restart wireplumber`.

## How it works, and what went wrong on the way

- **Sensor probe fails with -110.** The CVS bridge firmware owns the sensor's
  I2C while it is idle. The driver defers the chip ID check to the first
  stream-on, when `intel_cvs` has handed the sensor to the host.
- **Only 480 MHz link frequency.** The in-tree ipu-bridge advertises 480 MHz
  for `OVTI05C1`; Intel's driver wanted its full list. Patched to keep the
  modes that fit (2800x1576 at 30 fps, ~26 fps in practice).
- **Privacy LED stays dark.** It is pin 2 of the bridge's usbio GPIO chip,
  active high, not described in ACPI. The sensor driver drives it.
- **libcamera works, but looks flat.** The stock kernel plus libcamera's
  software ISP gives a picture with no sensor tuning. Intel's HAL uses the
  hardware ISP (psys) and the module's tuning file `OV05C10_BBG501N3_LNL.aiqb`.
- **Intel psys on the stock kernel oopses.** Intel's headers add fields to the
  core IPU7 structs, so psys reads garbage from the stock staging modules. The
  whole Intel set (core + isys + psys) must be used together; DKMS installs it
  into `updates/`, which depmod prefers.
- **Intel's isys finds no sensor.** The plain build only knows hard-coded
  platform data; the `all-acpi` build discovers the sensor through ipu-bridge
  like the stock driver.
- **HAL config.** The stock `ov05c10-uf.json` links the sensor straight to
  CSI2; it needs the Intel CVS hop.
- **One camera owner.** libcamera and PipeWire's libcamera monitor keep the
  camera acquired; a v4l2loopback device fed on demand by v4l2-relayd lets
  every app share it, and the IPU sleeps while nobody watches.

Alternative for the same hardware: [svp7500-camera-fix-pack](https://github.com/jibsta210/svp7500-camera-fix-pack)
(AUR `intel-ipu7-ir-dkms`), which also covers the IR camera but replaces the
in-tree ipu-bridge and intel_cvs. This repo keeps the in-tree drivers and pins
Intel's sources.

## Updates

All Intel sources are pinned by commit and sha256. Kernel updates rebuild the
DKMS modules automatically (`dkms status`). Intel's drivers track Intel's
patched kernels, so a new kernel can break `ipu7-intel-dkms`; removing it and
the HAL falls back to the stock drivers (then use libcamera).

## Licence

Packaging and docs: MIT. Kernel patches: GPL-2.0-only, like the drivers.
Intel's binaries (ipu7-camera-bins) are downloaded from Intel under Intel's
licence, not redistributed here.

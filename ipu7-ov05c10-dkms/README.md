# ipu7-ov05c10-dkms

Built-in RGB camera of the Dell Pro 14 Plus PB14250: OmniVision
OV05C10 behind a Synaptics SVP7500 (CVS) bridge on Intel IPU7 (Lunar Lake).

The stock kernel (7.2) already has everything except the sensor driver:
`ipu-bridge`, `intel_cvs`, `intel_ipu7` / `intel_ipu7_isys`. This package adds
only `ov05c10.ko`, built by DKMS from Intel's own source
(github.com/intel/ipu6-drivers, `drivers/media/i2c/ov05c10.c`, pinned commit
and sha256) plus two local patches:

- `0001` the stock ipu-bridge advertises only 480 MHz for OVTI05C1; keep the
  modes that fit instead of failing the probe (result: 2800x1576@30).
- `0002` the bridge firmware owns the sensor's I2C until the IPU starts
  streaming, so the chip ID is read on the first stream-on, not in probe.
- `0003` lights the camera privacy LED while the sensor streams. The LED is
  pin 2 of the bridge's USB GPIO chip `INTC10B5:00` (usbio), active high;
  ACPI does not describe it and intel_cvs never drives it (DMI-gated to the
  PB14250). Test by hand: `sudo gpioset -c gpiochip5 2=1` / `2=0` (the pin
  keeps its level after gpioset exits; chip number may differ).

Since 2026-10-03 `intel_ipu7` / `intel_ipu7_isys` come from `../ipu7-intel-dkms`
(Intel's set with psys for the hardware ISP) instead of the stock staging
modules; this sensor driver works with both.

User space: `../ipu7-camera-loopback` turns the raw sensor data into a normal
webcam, "Built-in Camera" on `/dev/video50`, for every app (V4L2 and PipeWire).
`../wireplumber/ipu7-camera.conf` keeps PipeWire off
libcamera and hides the raw IPU7 nodes.

Not used on purpose: the AUR `intel-ipu7-ir-dkms` / svp7500-camera-fix-pack.
It replaces the in-tree ipu-bridge and intel_cvs with older, modified copies
and needs the out-of-tree psys; none of that is needed for the RGB camera.
(The IR camera, `../ipu7-hm1092-dkms`, does rebuild the stock ipu-bridge from
the kernel's own source with one extra sensor line.)

## Install

See the top-level README (install order matters).

## Updates

- Kernel updates: the dkms pacman hook rebuilds the module automatically.
  Check after a kernel update: `dkms status ipu7-ov05c10`.
- Intel driver updates: compare the pinned `_commit` with
  `https://github.com/intel/ipu6-drivers/commits/master/drivers/media/i2c/ov05c10.c`.
  To move: set `_commit`/`pkgver`, put the new file's sha256 in `sha256sums`,
  check both patches still apply (`makepkg -o`), build, install, reboot, test.
- Drop this package when a kernel ships its own ov05c10 driver
  (`modinfo -n ov05c10` points into `kernel/`, not `updates/dkms`).

## Check

    cam -l                                   # libcamera lists the camera
    wpctl status | sed -n '/^Video/,/^Settings/p'
    journalctl -k -b | grep ov05c10          # no -110 / -22

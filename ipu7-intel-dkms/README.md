# ipu7-intel-dkms

Intel's own IPU7 kernel drivers (github.com/intel/ipu7-drivers, pinned commit
and sha256) for the Dell Pro 14 Plus PB14250, built by DKMS: `intel-ipu7`, `intel-ipu7-isys`,
`intel-ipu7-psys` and `ipu-acpi`, `ipu-acpi-pdata`, `ipu-acpi-common`.

Why: Intel's camera HAL (`../ipu7-intel-camera`, hardware ISP) needs the
processing system driver psys, which is not in the kernel. psys only works with
Intel's core/isys from the same tree: Intel's headers add fields to the core
structs, and psys on top of the stock staging core oopses in
`ipu7_psys_ioctl` (seen 2026-10-03). So the whole set is replaced; DKMS puts it
in `updates/dkms`, which depmod searches before `kernel/drivers/staging`.

Build details (in `dkms.conf`):

- `KV_IPU7_ISYS=99.0.0`: Intel's Makefile builds core/isys only for kernels
  < 6.17 and expects newer kernels to carry its patches; this lifts that gate.
- `all-acpi`: the plain build only knows hardcoded platform data ("no
  subdevice info provided"); the ACPI build finds the sensor through
  ipu-bridge/fwnode like the stock driver. ov05c10 is not in ipu-acpi's own
  sensor table, so ipu-acpi claims nothing here.

Unchanged and still from the kernel: `ipu-bridge`, `intel_cvs`; the sensor
driver comes from `../ipu7-ov05c10-dkms`.

## Install

See the top-level README (install order matters).

## Updates

- Kernel updates: the dkms pacman hook rebuilds it. Check
  `dkms status ipu7-intel` and `modinfo -n intel_ipu7` (must be `updates/dkms`).
  A new kernel can break the build (Intel tracks its own patched kernels);
  then remove the package to fall back to the stock staging drivers plus
  libcamera (`ipu7-camera-loopback` 1-2).
- Intel updates: move `_commit`/`pkgver`, `makepkg -g`, build, install,
  reboot, test with the camera package (HAL and driver ABI move together;
  update `../ipu7-intel-camera` to matching commits).

## Check

    journalctl -k -b | grep -E 'ipu7|psys'   # "IPU psys probe done", no Oops
    ls -l /dev/ipu7-psys0
    media-ctl -p -d /dev/media0 | grep -E 'entity.*(ov05c10|Intel CVS)'

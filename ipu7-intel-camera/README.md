# ipu7-intel-camera

Intel's IPU7 camera user space for the Dell Pro 14 Plus PB14250, built for `/usr`:

- `ipu7-camera-bins`: proprietary imaging libraries (AIQ 3A, tuning parser,
  graph libraries) and their headers; Intel binary licence.
- `ipu7-camera-hal`: the camera HAL (`libcamhal`, plugin `ipu7x.so`, configs
  in `/etc/camera/ipu7x`), built for `ipu7x` only.
- `icamerasrc` (branch `icamerasrc_slim_api`): GStreamer source `icamerasrc`.

Patch `0001`: the stock `ov05c10-uf.json` links the sensor straight to CSI2;
on the PB14250 the Intel CVS bridge sits in between, so the media graph goes
ov05c10 -> Intel CVS (pads 0/1) -> CSI2.

Firmware is not shipped: `linux-firmware`'s `intel/ipu/ipu7_fw.bin` is the
same 1.1.9 build as the one in ipu7-camera-bins.

The HAL has its install prefix compiled in (plugin directory), so it must be
built with prefix `/usr`; a copy elsewhere needs the same path.

Needs `../ipu7-intel-dkms` (psys). Used by `../ipu7-camera-loopback`.

## Install

See the top-level README (install order matters).

## Updates

Pinned commits `_bins`, `_hal`, `_src`. Move them together with
`../ipu7-intel-dkms`, `makepkg -g` for the sums, check the patch applies.

## Check (camera must not be in use by the relay)

    gst-launch-1.0 icamerasrc device-name=ov05c10-uf num-buffers=60 \
      ! video/x-raw,format=NV12,width=1920,height=1080 ! fpsdisplaysink video-sink=fakesink -v
    # as root; ~26 fps. Measured 2026-10-03: steady 26.2 fps for 30 s.

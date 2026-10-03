# ipu7-camera-loopback

Makes the IPU7 laptop camera of the Dell Pro 14 Plus PB14250 (driver: `../ipu7-ov05c10-dkms`)
a normal webcam for every app.

    Intel camera HAL (hardware ISP via psys: ../ipu7-intel-camera, ../ipu7-intel-dkms)
      -> v4l2-relayd@ipu7 (system service, GStreamer icamerasrc)
      -> v4l2loopback /dev/video50 "Built-in Camera", YUY2 1920x1080
      -> apps: V4L2 directly (Telegram, Zoom, OBS) or via PipeWire (browsers, portals)

v4l2-relayd starts the camera only while an app has `/dev/video50` open
(v4l2loopback client-usage event) and shows a black splash otherwise, so the
IPU sleeps when nobody uses the camera.

Until pkgrel 2 the source was libcamera's software ISP (`libcamerasrc`, needed
`DeviceAllow=/dev/udmabuf` in a unit drop-in); since pkgrel 3 (2026-10-03) it
is Intel's HAL, with clearly better picture (real 3A and tuning for the
OV05C10 module). Fallback: remove ipu7-intel-dkms/-camera, install pkgrel 2.

Why not PipeWire's libcamera support: libcamera allows one owner per camera,
and WirePlumber's libcamera monitor keeps the camera acquired even while idle,
so V4L2 apps could never get it. `../wireplumber/ipu7-camera.conf`
therefore disables `monitor.libcamera` and hides the 32 raw IPU7 nodes with
`node.disabled` (never `device.disabled`, it stalls WirePlumber 0.5.17).
Chromium works with and without `--enable-features=WebRtcPipeWireCamera`
(without it, it opens `/dev/video50` itself).

Changing resolution: edit `relayd.conf` (VIDEOSRC caps and WIDTH/HEIGHT), bump
`pkgrel`, rebuild. The sensor gives ~26 fps.

## Install

See the top-level README (install order matters).

## Check

    systemctl status v4l2-relayd@ipu7
    v4l2-ctl -d /dev/video50 --all | head
    wpctl status            # Video -> Sources: "Built-in Camera (V4L2)" only

# Howdy recorder for the Himax HM1092 IR camera on Intel IPU7 (Dell Pro 14 Plus PB14250).
#
# The sensor is monochrome but the driver tags it SGRBG10 ('BA10'), which OpenCV
# cannot read, so this reads the V4L2 capture node directly: 648x368, 16-bit LE
# containers with 10-bit values, bytesperline 1344.
#
# - Media graph: a fresh boot has the CSI2 -> capture link disabled, so the
#   pipeline is set up here, found by entity name (node numbers can move).
# - IR flood LED: driven by the hm1092 driver (ipu7-hm1092-dkms) while streaming.
# - Brightness: frames are dim (mean ~80/1023), and howdy drops a frame when more
#   than dark_threshold % of it is below 32/255, so each frame is stretched to
#   its 99th percentile.
# - Orientation: the module is mounted upside down on this laptop; rotate 180°.

import ctypes
import fcntl
import mmap
import os
import re
import subprocess

import numpy
from cv2 import cvtColor, COLOR_GRAY2BGR, CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT

from recorders import v4l2

PIX_FMT_SGRBG10 = 0x30314142  # 'BA10'
MBUS_FMT = "SGRBG10_1X10"
NBUF = 4


def _media_ctl(dev, *args):
	return subprocess.run(["media-ctl", "-d", dev, *args],
			      capture_output=True, text=True, timeout=10)


def setup_pipeline(width, height):
	"""Enable sensor -> CSI2 -> capture and set the formats; return /dev/videoN or None."""
	for dev in sorted("/dev/" + d for d in os.listdir("/dev") if d.startswith("media")):
		topo = _media_ctl(dev, "-p").stdout
		sensor = re.search(r"^- entity \d+: (hm1092 [^ ]+)", topo, re.M)
		if not sensor:
			continue
		sensor = sensor.group(1)
		csi2 = None
		# the CSI2 entity whose sink is fed by the sensor
		for block in topo.split("\n- entity ")[1:]:
			name = re.match(r"\d+: (.+?) \(", block)
			if name and re.search(r'<- "%s":0' % re.escape(sensor), block):
				csi2 = name.group(1)
				break
		if not csi2:
			continue
		cap = None
		for block in topo.split("\n- entity ")[1:]:
			if block.split(" (", 1)[0].endswith(": " + csi2):
				m = re.search(r'pad1: SOURCE.*?-> "([^"]+Capture[^"]*)":0', block, re.S)
				cap = m and m.group(1)
				break
		if not cap:
			continue
		fmt = "%s/%dx%d" % (MBUS_FMT, width, height)
		_media_ctl(dev, "-V", '"%s":0 [fmt:%s]' % (csi2, fmt))
		_media_ctl(dev, "-V", '"%s":1 [fmt:%s]' % (csi2, fmt))
		_media_ctl(dev, "-l", '"%s":1 -> "%s":0 [1]' % (csi2, cap))
		node = _media_ctl(dev, "-e", cap).stdout.strip()
		return node or None
	return None


class hm1092_reader:
	"""The subset of cv2.VideoCapture that howdy uses."""

	def __init__(self, device_name):
		self.width, self.height = 648, 368
		self.device_name = setup_pipeline(self.width, self.height) or device_name
		self.fd = None
		self.buffers = []
		self.streaming = False
		self._open()

	def set(self, prop, setting):
		pass  # fixed mode

	def get(self, prop):
		if prop == CAP_PROP_FRAME_WIDTH:
			return self.width
		if prop == CAP_PROP_FRAME_HEIGHT:
			return self.height
		return 0

	def isOpened(self):
		return self.fd is not None

	def _open(self):
		self.fd = os.open(self.device_name, os.O_RDWR)
		fmt = v4l2.v4l2_format()
		fmt.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
		fmt.fmt.pix.width = self.width
		fmt.fmt.pix.height = self.height
		fmt.fmt.pix.pixelformat = PIX_FMT_SGRBG10
		fmt.fmt.pix.field = v4l2.V4L2_FIELD_NONE
		fcntl.ioctl(self.fd, v4l2.VIDIOC_S_FMT, fmt)
		self.width, self.height = fmt.fmt.pix.width, fmt.fmt.pix.height
		self.bytesperline = fmt.fmt.pix.bytesperline or self.width * 2

		req = v4l2.v4l2_requestbuffers()
		req.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
		req.memory = v4l2.V4L2_MEMORY_MMAP
		req.count = NBUF
		fcntl.ioctl(self.fd, v4l2.VIDIOC_REQBUFS, req)
		for i in range(req.count):
			buf = self._buf()
			buf.index = i
			fcntl.ioctl(self.fd, v4l2.VIDIOC_QUERYBUF, buf)
			self.buffers.append(mmap.mmap(self.fd, buf.length, mmap.MAP_SHARED,
						      mmap.PROT_READ, offset=buf.m.offset))
			fcntl.ioctl(self.fd, v4l2.VIDIOC_QBUF, buf)

	@staticmethod
	def _buf():
		buf = v4l2.v4l2_buffer()
		buf.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
		buf.memory = v4l2.V4L2_MEMORY_MMAP
		return buf

	def _stream(self, on):
		typ = ctypes.c_int(v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)
		fcntl.ioctl(self.fd, v4l2.VIDIOC_STREAMON if on else v4l2.VIDIOC_STREAMOFF, typ)
		self.streaming = on

	def grab(self):
		self.read()

	def read(self):
		if self.fd is None:
			return False, None
		if not self.streaming:
			self._stream(True)
		buf = self._buf()
		try:
			fcntl.ioctl(self.fd, v4l2.VIDIOC_DQBUF, buf)
		except OSError:
			return False, None
		arr = numpy.frombuffer(self.buffers[buf.index], dtype="<u2",
				       count=self.bytesperline // 2 * self.height)
		arr = arr.reshape(self.height, -1)[:, :self.width] & 0x3ff
		fcntl.ioctl(self.fd, v4l2.VIDIOC_QBUF, buf)
		return True, cvtColor(to_gray8(arr), COLOR_GRAY2BGR)

	def release(self):
		if self.fd is None:
			return
		try:
			if self.streaming:
				self._stream(False)
			for m in self.buffers:
				m.close()
			self.buffers = []
		finally:
			os.close(self.fd)
			self.fd = None


def to_gray8(arr):
	"""10-bit frame -> upright 8-bit, stretched so the 99th percentile is 255."""
	top = max(int(numpy.percentile(arr, 99)), 64)
	gray = numpy.clip(arr.astype(numpy.uint32) * 255 // top, 0, 255).astype(numpy.uint8)
	return gray[::-1, ::-1].copy()

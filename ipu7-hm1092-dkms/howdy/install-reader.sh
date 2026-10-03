#!/bin/bash
# Hook hm1092_reader into howdy 2.6.1 and point its config at the IR camera.
# Idempotent; backs up the two files it edits once (*.orig).
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run with sudo"; exit 1; }
H=/usr/lib/security/howdy
VC=$H/recorders/video_capture.py
CFG=$H/config.ini
[[ -f $VC && -f $CFG ]] || { echo "howdy is not installed"; exit 1; }

install -m600 "$(dirname "$0")/hm1092_reader.py" $H/recorders/hm1092_reader.py

[[ -f $VC.orig ]] || cp -p $VC $VC.orig
[[ -f $CFG.orig ]] || cp -p $CFG $CFG.orig

if ! grep -q hm1092_reader $VC; then
	python3 - "$VC" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read()
anchor = "\t\telse:\n\t\t\t# Start video capture on the IR camera through OpenCV\n"
hook = ('\t\telif self.config.get("video", "recording_plugin") == "hm1092":\n'
	'\t\t\tfrom recorders.hm1092_reader import hm1092_reader\n'
	'\t\t\tself.internal = hm1092_reader(self.config.get("video", "device_path"))\n\n')
assert s.count(anchor) == 1, "video_capture.py layout changed"
open(p, "w").write(s.replace(anchor, hook + anchor))
EOF
fi

sed -i -e 's|^device_path = .*|device_path = /dev/video8|' \
       -e 's|^recording_plugin = .*|recording_plugin = hm1092|' \
       -e 's|^dark_threshold = .*|dark_threshold = 90|' $CFG
grep -nE '^(device_path|recording_plugin|dark_threshold|certainty|timeout) ' $CFG
python3 -c "import ast,sys; ast.parse(open('$VC').read())" && echo "video_capture.py OK"

#!/bin/bash
# PAM part of omarchy-setup-security-fingerprint, without its package step
# (it installs libfprint-git, which has no TOD support and conflicts with
# libfprint-tod). Lines are identical, so omarchy-remove-security-fingerprint
# still removes them.
set -e
[[ $EUID -eq 0 ]] || { echo "run with sudo"; exit 1; }

gate="auth      [success=1 default=ignore] pam_exec.so quiet /usr/bin/omarchy-hw-laptop-closed"

if [[ ${1:-} != --lock-only ]]; then
  cp -n /etc/pam.d/sudo /etc/pam.d/sudo.pre-fingerprint
  grep -q pam_fprintd.so /etc/pam.d/sudo || sed -i '1i auth      sufficient pam_fprintd.so' /etc/pam.d/sudo
  grep -q omarchy-hw-laptop-closed /etc/pam.d/sudo || sed -i "/pam_fprintd\.so/i $gate" /etc/pam.d/sudo

  [[ -f /etc/pam.d/polkit-1 ]] || cat > /etc/pam.d/polkit-1 <<PAM
$gate
auth      sufficient pam_fprintd.so
auth      required pam_unix.so

account   required pam_unix.so
password  required pam_unix.so
session   required pam_unix.so
PAM
fi

cat > /etc/pam.d/omarchy-lock-fingerprint <<'PAM'
#%PAM-1.0
auth       required                    pam_fprintd.so
account    include                     system-local-login
PAM
echo done

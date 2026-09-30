English | [日本語](HISTORY.ja.md)

# Changelog

## Unreleased

- Fixed Windows setup so the sslpsk-pmd3 native backend is validated and the Python 3.10 OpenSSL DLL naming mismatch is repaired inside the virtual environment when required.
- Clarified that a separate CoreDevice media/HID session on the same iPad can cause ScreenCaptureService or HID timeouts even when RemotePairing, the userspace tunnel, and RSD are healthy.
- Updated the release check to scan Git release candidates while excluding intentionally ignored runtime secrets such as config.toml.

## 0.3.2

- Consolidated the device-specific UDID, destination, and pairing record into config.toml and removed value placeholders from the command examples.
- Changed the pairing record to be saved not implicitly to an internal path under the user profile, but to a relative path based on config.toml or to an explicitly specified path.
- Added check.ps1 so that checks can be run without asking the user for the virtual environment's internal path.

## 0.3.1

- Changed Python 3.10 detection from a fixed Windows install location to `py -3.10` and `python` on PATH.
- Removed per-user absolute path examples and the pymobiledevice3 storage location that does not need manual management from the procedure document.

## 0.3.0

- Organized the shared path for connecting from Windows to the iPad as RemotePairing, userspace tunnel, RSD, and DDI.
- Integrated Vision observation and Semantic observation as branches of the same CLI.
- Added Accessibility multi-pass scanning, label filtering, and best-effort AX Activate.
- Included conversion from screen coordinates to orientation-specific HID coordinates, tap, swipe, buttons, ASCII input, and Unicode paste.
- Added 90-degree rotation and the rule of reconnecting with a new CLI process after rotation.
- Quantified the screen diff before and after operations so the effect can be confirmed without sending images externally.
- Unified standard output to a single line of ASCII-escaped JSON so Japanese labels are not corrupted on the Windows console.
- Consolidated everything from initial setup through operation, recovery, troubleshooting, and non-adopted paths into README.md.

## Relationship to existing distributions

0.3.0 is an independent distribution. 0.1.0, which contains only the Vision path, and the preceding Hybrid version 0.2.0 are preserved unchanged.

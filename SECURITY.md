English | [日本語](SECURITY.ja.md)

# Security

## Pairing records

The StikPair `rp_pairing_file.plist` and the file specified by `device.pairing_record` in the converted `config.toml` contain a private key. Do not attach them to repositories, issues, logs, or chats.

This repository's `.gitignore` excludes `*.plist` and `config.toml`, but also run the following before committing.

```powershell
.\check.ps1
git status --short
```

If a leak is suspected, stop using the existing record and redo RemotePairing on the iPad.

## Network exposure

Do not expose the iPad's RemotePairing port or captured images to the internet without authentication. Between the controlling host and the iPad, use the same LAN, a managed VPN, or an access-controlled route.

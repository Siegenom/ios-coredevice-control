[English](SECURITY.md) | 日本語

# Security

## ペアリングレコード

StikPairの `rp_pairing_file.plist` と、変換後の
`config.toml` の `device.pairing_record` で指定したファイルには秘密鍵が含まれます。
リポジトリ、Issue、ログ、チャットへ添付しないでください。

このリポジトリの `.gitignore` は `*.plist` と `config.toml` を除外しますが、
コミット前に次も実行してください。

```powershell
.\check.ps1
git status --short
```

漏えいが疑われる場合は、既存レコードの利用を中止してiPad側でRemotePairingを
やり直してください。

## ネットワーク公開

iPadのRemotePairingポートや取得画像を、認証なしでインターネットへ公開しないで
ください。操作元ホストとiPadの間には、同一LAN、管理されたVPN、またはアクセス制御済み
のルートを使用してください。

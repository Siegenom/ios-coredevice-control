[English](README.md) | 日本語

# CoreDeviceを用いたiOSデバイス制御：実装と再現手順

Windows PCからネットワーク経由でiPadへ接続し、画面取得、Accessibility情報の取得、
アプリ起動、タップ、スワイプ、ボタン操作、文字入力を実行する構成の技術報告兼リファレンス実装です。
初回構築ではiPadとWindows PCをUSB接続しますが、RemotePairingの作成後は、両者の間にIP通信経路が
あればUSBケーブルなしで操作できます。

この動作確認済みの構成ではMacやXcodeを必要としません。Windows 11は検証に使用したホスト環境ですが、
制御アーキテクチャ自体はWindows固有ではなく、RemotePairing、ユーザー空間RSDトンネル、
Accessibility観測、CoreDeviceサービスを組み合わせた再現可能な実機制御構成です。

操作経路はWebDriverAgent / XCTest / Appiumを使用せず、RemotePairing、ユーザー空間トンネル、RSD、
DDI、CoreDevice HID / AppServiceを利用します。本構成ではこの接続・操作基盤を共通化し、
操作対象を見つける方法だけをVision観測とSemantic観測に分けます。

本書は、動作確認できた構成・再現手順・既知の制約を記録することを目的としています。

~~~text
利用者またはAIエージェント
              │
              ▼
Windows上の ipad-control CLI
              │
 RemotePairing → userspace tunnel → RSD → DDI
              │
       ┌──────┴──────────────────┐
       │                         │
 Vision観測                 Semantic観測
 画面PNG・座標              Accessibilityラベル
       │                         │
       └──────────┬──────────────┘
                  ▼
        CoreDevice HID・AppService
        タップ／スワイプ／ボタン
        文字入力／アプリ起動
                  │
                  ▼
                 iPad
~~~

Vision観測は画面の位置関係を取得できます。Semantic観測はVisionモデルを使わず、前面アプリの
メニュー項目や選択状態を短いテキストとして取得できます。両者の制約が異なるため、用途に応じて
切り替えます。

## デモ

[![実機iPadデモ：設定項目を移動するAccessibilityフォーカス](docs/ios-coredev-cont_demo.jpg)](docs/ios-coredev-cont_demo.mp4)

実機iPadの「設定」で、Accessibility要素の列挙中にフォーカス枠が項目を順に移動する様子を撮影した短いデモです。画像をクリックすると動画を再生できます。

## 1. 動作確認済みの構成

以下の構成で、画面取得、Accessibility項目列挙、設定アプリの起動、HIDタップ、スワイプ、
ホームボタン、文字入力まで確認しています。

| 項目 | 構成 |
|---|---|
| PC | Windows 11 |
| iPad | iPad Air（M4） |
| iPadOS | 27.0 |
| Python | 3.10.4 x64 |
| デバイス通信 | pymobiledevice3 11.15.4 |
| TLS補助 | sslpsk-pmd3 1.0.3 |
| 画像処理 | Pillow 12.3.0 |
| iPad側のペアリング用アプリ | StikPair |
| IPAのインストール | Sideloadly 0.60 |
| ネットワーク経路 | iPadのTCP 49152へ到達できるIPネットワーク |
| 参照実装 | ipad-hybrid-control 0.3.2 |

この表は実際に動作確認した組み合わせをそのまま記録したものです。ここに挙げた端末・OS・ツールだけが互換性を持つという意味ではありません。

> [!NOTE]
> Windows 11は本構成を実際に動作確認した環境です。本書は、ここで説明する仕組み自体がWindows固有であるとは主張しません。同梱するスクリプト（setup.ps1、run.ps1、check.ps1）は現時点ではPowerShellベースです。

> [!NOTE]
> StikPairを使ったiPad上でのRemotePairingはiPadOS 27以降を前提とします。古いiPadOSで
> USB信頼設定やWi-Fi同期が利用できる場合でも、本書と同じペアリング手順になるとは限りません。

## 2. 用語

- **RemotePairing**：iPadと操作元ホストが相互を識別する暗号鍵と識別子を登録する処理です。
- **ペアリングレコード**：RemotePairingで作られるplistファイルです。秘密鍵を含みます。
- **RSD（Remote Service Discovery）**：ネットワーク上のiPadが公開する開発・診断サービスへ
  接続する入口です。
- **DDI（Developer Disk Image）**：画面取得、HID入力、Accessibility監査などの
  開発者向けサービスを有効にするため、iPadへマウントするイメージです。
- **CoreDevice**：新しいiOS／iPadOS端末の画面、アプリ、HIDなどを扱うサービス群です。
- **HID**：タップ、スワイプ、ボタン、キーボード入力をiPadへ送る入力経路です。
- **Bundle ID**：アプリを識別する文字列です。設定アプリは com.apple.Preferences です。
- **Vision観測**：取得した画面画像を人または画像認識対応AIが読み、位置を判断する方式です。
- **Semantic観測**：Accessibilityからラベルを取得し、画像認識を使わず項目を判断する方式です。
- **AX Activate**：Accessibility要素へ送る起動操作です。本環境では選択やスクロールには作用
  しますが、UIKitの項目を確実には開きません。

## 3. 用意するもの

以降の章では、技術報告として実際に再現できる状態を保つため、動作確認済み経路の具体的な製品名を意図的に使用します。

### iPad側

- iPadOS 27以降のiPad
- iPadのパスコード
- インターネット接続
- Windows PCへ一時的に接続できるUSBケーブル
- StikPairのIPAファイル

### Windows側

- Windows 11 PC
- Python 3.10 x64
- Sideloadly
- Apple Account
- ipad-hybrid-control 0.3.2の配布フォルダー
- iPadのTCP 49152へ到達できるネットワーク

SideloadlyがUSB接続中のiPadを認識できる状態が必要です。Apple Accountのパスワードと
2要素認証コードは、Sideloadlyが入力を求めた時点で利用者本人が入力します。

## 4. StikPairをiPadへインストールする

### 4.1 iPadをUSB接続する

1. iPadを起動し、画面ロックを解除します。
2. USBケーブルでiPadとWindows PCを接続します。
3. 「このコンピュータを信頼しますか？」と表示された場合は **信頼** をタップします。
4. iPadのパスコードを入力します。
5. Sideloadlyを起動します。
6. iDevice欄に、接続したiPadが @USB 付きで表示されることを確認します。
7. iDevice欄に表示されたUDIDを控えます。

SideloadlyにiPadが表示されない場合は、iPadをロック解除したままケーブルを挿し直し、
WindowsのデバイスマネージャーでApple Mobile Device USBドライバーを確認します。

### 4.2 IPAをサイドロードする

1. StikPairのIPAファイルをSideloadlyへドラッグ＆ドロップします。
2. iDevice欄で対象のiPadを選択します。
3. Apple ID欄へApple Accountのメールアドレスを入力します。
4. **Start** を押します。
5. パスワード入力画面でApple Accountのパスワードを入力します。
6. 2要素認証を求められた場合は、信頼済みデバイスへ届いた確認コードを入力します。
7. Sideloadlyが完了を表示するまでUSB接続を維持します。
8. iPadのホーム画面にStikPairが追加されたことを確認します。

> [!TIP]
> 無料のApple Accountで署名したアプリには有効期限があります。期限切れ後にStikPairを再び
> 起動する場合は再署名が必要です。書き出し済みのペアリングレコードを使う通常運用では、
> 毎回StikPairを起動する必要はありません。

## 5. iPadでデベロッパモードと署名元を有効にする

### 5.1 デベロッパモード

1. iPadで **設定** を開きます。
2. **プライバシーとセキュリティ** を開きます。
3. 画面下部の **デベロッパモード** を開きます。
4. デベロッパモードをオンにします。
5. 指示に従ってiPadを再起動します。
6. 再起動後にロックを解除します。
7. 確認画面で **オンにする** を選び、パスコードを入力します。

### 5.2 「信頼されていないデベロッパ」と表示された場合

1. **設定** → **一般** → **VPNとデバイス管理** を開きます。
2. **デベロッパApp** に表示されたApple Accountを開きます。
3. **信頼** をタップします。
4. 確認画面でもう一度 **信頼** をタップします。
5. StikPairを開き直します。

## 6. StikPairでRemotePairingを行う

1. iPadでStikPairを起動します。
2. ローカルネットワークへのアクセスを求められたら **許可** します。
3. **Pair iPhone or iPad** をタップします。
4. StikPairを開いたまま、**設定** → **プライバシーとセキュリティ** →
   **デベロッパモード** を開きます。
5. **Pair with StikPair** をタップします。
6. StikPairのライブアクティビティに表示されたPINを入力します。
7. Pairing completeと表示されたらStikPairへ戻ります。
8. **Export Pairing File** をタップします。
9. rp_pairing_file.plistを「ファイル」アプリへ保存します。

ペアリング後にデベロッパモード画面からStikPairの名前が消えても、レコードが直ちに無効に
なったとは限りません。Windows側の接続検査で成否を判断します。

## 7. ペアリングファイルをWindowsへ移す

rp_pairing_file.plistを、共有フォルダー、クラウドストレージ、メッセージ添付など任意の
安全な方法でWindows PCへ移します。以降の変換コマンドを実行する前に、配布フォルダー直下へ
一時保存します。

このファイルには秘密鍵が含まれます。第三者へ送信せず、リポジトリや公開フォルダーへ追加
しないでください。漏えいした場合は、既存レコードの利用を中止し、StikPairでペアリングを
やり直します。

## 8. WindowsのPython環境を準備する

配布フォルダーをカレントディレクトリにしたPowerShellを開きます。

~~~powershell
.\setup.ps1
~~~

setup.ps1は次の処理を行います。

1. .venvへPython 3.10の仮想環境を作成する。
2. 本配布パッケージを編集可能インストールし、固定バージョンのpymobiledevice3、sslpsk-pmd3、Pillow、tomliも導入する。
3. Windowsでsslpsk-pmd3のネイティブバックエンドを読み込めるか検査し、必要ならPython 3.10のOpenSSL DLL名の不一致を仮想環境内で修復する。
4. config.example.tomlからconfig.tomlを作成する。

setup.ps1は、Windows Python Launcherの`py -3.10`を使います。Python Launcherを使わず、
PATH上の`python`がPython 3.10を指す環境では、次のように指定します。

~~~powershell
.\setup.ps1 -Python python
~~~

`python --version`が3.10以外を表示する場合は、Python 3.10をインストールして`py -3.10`が
利用できる状態にしてから、引数なしでsetup.ps1を実行します。

動作確認したWindows/Python 3.10環境では、sslpsk-pmd3 1.0.3が`libssl-1_1-x64.dll`と
`libcrypto-1_1-x64.dll`を探す一方、Python 3.10は同じOpenSSL 1.1ライブラリを
`libssl-1_1.dll`と`libcrypto-1_1.dll`という名前で同梱していました。`setup.ps1`は
`sslpsk_pmd3.sslpsk`のimport失敗を検出し、必要な場合だけPython同梱DLLを`.venv`内へ
sslpsk-pmd3が期待する名前で配置してから再検査します。無関係なアプリケーションのDLLには依存しません。

インストール後の基本構成は次のとおりです。

| ファイル／ディレクトリ | 用途 |
|---|---|
| README.md | 本手順書 |
| config.toml | 実機ごとのUDID、接続先、出力先 |
| run.ps1 | CLI起動ラッパー |
| src\ipad_hybrid_control | 共通接続、観測、HID操作の実装 |
| artifacts | 取得画像の保存先 |
| tools\check_release.py | 個人情報・秘密情報の混入検査 |
| tests | 座標、画像差分、ラベル、plist変換のテスト |

## 9. 設定ファイルを記入する

setup.ps1が作成したconfig.tomlを開き、空欄のUDIDとhostだけを記入します。UDIDはSideloadlyの
iDevice欄で控えた値、hostはWindowsからiPadへ到達できるIPアドレスまたはホスト名です。

~~~toml
[device]
udid = ""
host = ""
port = 49152
pairing_record = "secrets/remote-pairing.plist"
~~~

pairing_recordとoutput.directoryの相対パスは、config.tomlがある配布フォルダーを基準に解決
されます。別の保存場所が必要なら、この二つの値だけを変更します。

config.tomlは端末ごとの秘密情報を含むため、Git管理対象から除外します。

## 10. StikPairのファイルをpymobiledevice3形式へ変換する

config.tomlを保存してから実行します。

~~~powershell
.\run.ps1 convert-pairing .\rp_pairing_file.plist
~~~

変換後の記録はconfig.tomlのpairing_recordへ保存されます。接続のたびに、この指定先の記録から
pymobiledevice3の内部トランスポートキャッシュを更新するため、認証にはconfig.tomlで指定した
記録が使われます。元ファイルと変換後ファイルの両方を秘密情報として扱います。変換を確認した後、
配布フォルダーへ置いた元ファイルは安全な場所へ移すか削除します。

## 11. WindowsからiPadへ到達できるようにする

USBケーブルを外した後は、WindowsからiPadのTCP 49152へ到達できるIP経路が必要です。

- WindowsとiPadを同じLANへ接続する
- 拠点間VPNを利用する
- 両者を同じオーバーレイネットワークへ参加させる
- ルーターで到達可能な経路を構成する

遠隔地からの動作確認ではTailscaleを使用しましたが、Tailscale固有の機能は必須では
ありません。WindowsからiPadのIPアドレスまたはホスト名へ到達できれば利用できます。

初回接続時はiPadを起動し、ロックを解除しておきます。TCP 49152への到達性は次節のdoctorが
config.tomlのhostを使って検査します。

## 12. ペアリング接続を検証する

~~~powershell
.\run.ps1 doctor
~~~

doctorは既定でUDID、ホスト、ペアリング記録のパス、エラー中の機密情報を伏せます。ローカルでの調査時だけ `.\run.ps1 --debug doctor` で詳細を表示できます。詳細出力は内容を確認せず共有しないでください。

doctorは次を検査します。

1. config.tomlのUDID、ホスト、ポート、ペアリング記録。
2. pairing_recordに指定したファイルの存在。
3. plistの必須キーとpeer_udid。
4. iPadのTCP 49152への到達性。

okがtrueにならない場合は、problems配列の内容を確認します。

## 13. DDIをマウントする

~~~powershell
.\run.ps1 mount-ddi
~~~

初回はAppleの署名サービスから個人化チケットとDDIを取得するため、通常より時間がかかります。
stateがmountedまたはalready-mountedになれば完了です。

iPadの再起動後、画面取得、Accessibility、HIDのいずれかへ接続できなくなった場合は、
DDIを再度マウントします。

> [!NOTE]
> iPadOSの更新でDDI処理が変わる可能性があります。本構成はpymobiledevice3 11.15.4と
> iPadOS 27.0の組み合わせで確認しています。

## 14. 共通接続基盤を確認する

~~~powershell
.\run.ps1 status
~~~

成功時は向きと画面寸法が返ります。statusは共通基盤の次の範囲を確認します。

- RemotePairing接続
- ユーザー空間トンネル
- RSD接続
- SpringBoardの画面向き
- ScreenCaptureService

この段階が失敗する場合は、Vision観測とSemantic観測のどちらも利用できません。観測経路の
問題へ進む前に、ペアリング、ネットワーク、DDIを修復します。

このCLIは、各コマンドの開始時にRemotePairingからユーザー空間トンネルとRSDを確立し、
処理後に閉じます。タップ、スワイプ、ボタン、キーボード入力では、iPadからWindowsへ戻る
メディアストリームも同じユーザー空間トンネルへ登録します。CoreDevice HIDはこの
メディアストリームが開始されている間だけ有効になるためです。画面取得に成功してもHIDだけが
反応しない場合は、RTPの戻り経路とユーザー空間トンネルの登録を確認します。

CLIの標準出力は1回につき1行のJSONです。日本語ラベルはASCIIエスケープされるため、Windowsの
コンソールがUTF-8以外でもJSONパーサーで元の文字列へ復元できます。

## 15. 観測経路を選択する

両経路は同じiPad接続を利用します。違いは「画面上に何があるか」を取得する方法です。

| 判断条件 | Vision観測 | Semantic観測 |
|---|---:|---:|
| Visionモデルを使わず項目名を読みたい |  | 適する |
| アイコン、画像、配置、座標を知りたい | 適する |  |
| 前面アプリの項目を低コストで列挙したい |  | 適する |
| ホーム画面を操作したい | 適する | 利用不可 |
| Accessibilityに現れない対象を操作したい | 適する | 利用不可 |
| 項目名は分かるが位置が分からない | 適する | 名前の確認のみ |
| UIKit項目を確実に開きたい | 座標HIDを使用 | AX Activateは保証なし |

### 15.1 Vision観測

~~~powershell
.\run.ps1 observe
~~~

次のファイルが作成されます。

~~~text
artifacts\screen.png
artifacts\screen-thumb.jpg
~~~

screen.pngはiPadの実画面です。人またはVision対応AIが画像を読み、対象の中心ピクセル座標を
決めます。画像には通知、アカウント名、写真などが写る可能性があるため、必要な相手以外へ
送信しないでください。

### 15.2 Semantic観測

前面アプリのAccessibility項目を列挙します。

~~~powershell
.\run.ps1 elements
~~~

文字列で絞り込む場合はfilterを指定します。

~~~powershell
.\run.ps1 elements --filter "Wi-Fi"
.\run.ps1 elements --filter "一般" --passes 3
~~~

出力の意味は次のとおりです。

| フィールド | 意味 |
|---|---|
| scanned | 複数パスで収集した全要素数 |
| matched | filter適用後の要素数 |
| timedOut | 走査中にタイムアウトしたか |
| elements | indexとcaptionの一覧 |

Accessibility走査は一度にフォーカス1サイクル分しか返さず、実行ごとに件数が変わります。
実装は各パスの前に先頭へ戻し、platform identifierで結果を統合します。対象が欠落する場合は
passesを増やします。

Semantic観測には次の制約があります。

- ホーム画面では要素を取得できない。
- 前面をシステム警告が覆うと警告側の要素だけが返る。
- 利用可能な要素情報にHIDへ変換できる座標がない。
- ラベルが読めても、その位置へ直接タップすることはできない。

### 15.3 Hybrid観測

次の順序で二経路を組み合わせます。

1. elementsで目的のラベルが存在するか確認します。
2. ラベルだけで処理できる場合はSemantic観測を継続します。
3. 座標が必要、要素が欠落、ホーム画面、画像だけの対象のいずれかならobserveを実行します。
4. 画像上の座標をtapまたはswipeへ渡します。
5. 操作後にelementsまたはafter.pngで結果を確認します。

Semantic観測からVision観測への切り替えは異常処理ではありません。Accessibilityが意味を、
画面画像が位置を担当するための正規の経路です。

## 16. アプリ起動とHID操作を確認する

### 16.1 設定アプリを起動する

~~~powershell
.\run.ps1 launch com.apple.Preferences
~~~

操作後の画面はartifacts\after.pngへ保存されます。

### 16.2 画像座標をタップする

~~~powershell
.\run.ps1 tap 1180 820
~~~

座標は直前に取得したPNG上のピクセル座標です。実装は操作直前に画面向きと画像寸法を取得し、
画像座標をHIDの0～65535へ変換します。

### 16.3 スワイプする

~~~powershell
.\run.ps1 swipe 1800 800 700 800
~~~

速度を変更する場合はduration、補間数を変更する場合はstepsを指定します。

~~~powershell
.\run.ps1 swipe 1800 800 700 800 --duration 500 --steps 24
~~~

### 16.4 ホーム画面へ戻る

~~~powershell
.\run.ps1 press home
~~~

lock、volume-up、volume-down、mute、siriも同じpressコマンドで指定できます。

### 16.5 文字を入力する

入力欄へフォーカスを移してから実行します。

~~~powershell
.\run.ps1 type "settings"
~~~

typeはUS配列の印刷可能ASCII向けです。日本語やASCII外の文字はpasteを使用します。

~~~powershell
.\run.ps1 paste "日本語テスト"
~~~

仮想HIDキーボードとして接続されるため、iPadのソフトキーボードが表示されない場合があります。

### 16.6 ラベルへAX Activateを送る

~~~powershell
.\run.ps1 tap-text "一般" --measure-change
~~~

同じラベルが複数ある場合はindexを指定します。

~~~powershell
.\run.ps1 tap-text "アプリ" --index 1 --measure-change
~~~

tap-textはbest effortです。本環境では選択やスクロールには作用しましたが、UIKitの項目を
確実には開きません。画面遷移しない場合は繰り返さず、Vision観測で座標を取得してtapを
使用します。

### 16.7 画像差分で作用を確認する

各操作へmeasure-changeを付けると、操作前後の縮小画像から0～1の変化量を計算します。

~~~powershell
.\run.ps1 tap 1180 820 --measure-change
~~~

changeは画面の意味を解釈しません。0に近い値は無反応の可能性を示しますが、成功条件そのもの
ではありません。必要に応じてafter.pngまたはelementsを確認します。

### 16.8 画面を90度回転する

~~~powershell
.\run.ps1 rotate left
~~~

rightも指定できます。回転が成功すると、そのとき使用したRSD接続が継続利用できなくなる場合が
あります。このコマンドは回転後の画像取得を行わず終了します。新しいCLIコマンドとしてorient、
status、observeのいずれかを実行し、再接続後の向きを確認します。

~~~powershell
.\run.ps1 orient
.\run.ps1 observe
~~~

動作確認に使用したiPadでは、portrait、landscapeLeft、landscapeRightの座標変換を実機の
ジェスチャーで確認しました。portraitUpsideDownにはUIが回転しなかったため、到達可能な向きには
含めていません。別機種では、配布物の座標テストに加えて実機で各向きを確認してください。

## 17. 疎通後にAIエージェントへ操作させるときの基本ループ

### 17.1 Visionを使用するループ

1. observeで最新画面を取得する。
2. PNGを画像として解析する。
3. 一度に一つのtap、swipe、press、type、paste、launchを実行する。
4. after.pngを解析する。
5. 目的の状態になるまで繰り返す。

画面遷移、アニメーション、回転、Slide Over、Split Viewの後は新しい画像を取得します。
古い画像の座標を使い続けません。

### 17.2 Visionを使用しないループ

1. launchで対象アプリを前面へ出す。
2. elementsでラベルを列挙する。
3. filterで目的の項目を絞る。
4. tap-textが作用する種類なら一度だけ実行する。
5. measure-changeとelementsの再取得で作用を確認する。
6. 座標が必要になった時点でHybrid観測へ切り替える。

Semantic経路だけで完結しない画面が存在します。Accessibilityに座標がない以上、文字列から
任意のUIKit項目のHID座標を推測しません。

## 18. 取得画像を共有する場合

エージェントがWindows上のファイルを直接読める場合、画像サーバーは不要です。observeまたは
操作後に出力されたPNGを画像入力として渡します。

~~~text
artifacts\screen.png
artifacts\after.png
~~~

別ホストへ共有する場合は、認証とアクセス制御のある共有方法を使用します。取得画像を
認証なしのHTTPサーバーや公開URLへ置かないでください。

AIクライアントによってはローカル画像へのMarkdownリンクを灰色のプレースホルダーとして
表示します。その場合は、クライアントの画像添付機能または画像データを直接渡すAPIを使用します。

## 19. 再起動後の復旧手順

1. iPadを起動し、ロックを解除します。
2. WindowsからiPadのTCP 49152へ到達できることを確認します。
3. .\run.ps1 doctorを実行します。
4. .\run.ps1 mount-ddiを実行します。
5. .\run.ps1 statusを実行します。
6. Vision経路はobserve、Semantic経路はelementsで確認します。

ペアリングレコードが有効なら、通常はStikPairでのペアリングやUSB接続をやり直す必要は
ありません。

## 20. トラブルシューティング

### SideloadlyにiPadが表示されない

- iPadをロック解除する。
- USBケーブルを挿し直す。
- iPad側の信頼確認を完了する。
- データ通信対応のUSBケーブルを使う。
- Apple Mobile Device USBドライバーを確認する。

### SideloadlyがApple Account認証前に失敗する

Anisette初期化やDLL読み込みの失敗では、Apple Accountのパスワード画面まで進みません。
Sideloadlyを終了し、管理者権限が必要な初期化を完了させ、Sideloadlyが使用するDLL一式を
同一バージョンで揃えてから再実行します。認証画面へ到達する前の失敗は、パスワードや
2要素認証の誤りではありません。

### StikPairが「信頼されていないデベロッパ」で開かない

**設定** → **一般** → **VPNとデバイス管理** で、サイドロードに使ったApple Accountを
信頼します。

### StikPairが接続待ちのまま進まない

- StikPairのローカルネットワーク権限を有効にする。
- デベロッパモードがオンになっているか確認する。
- StikPairを起動した状態でPair with StikPairから開始する。
- PINの有効時間が切れた場合は最初からやり直す。

### doctorがペアリングレコードを見つけられない

config.tomlのpairing_recordが変換先と一致しているか確認します。一致しない場合は、
convert-pairingをもう一度実行します。UDIDとpeer_udidが対象iPadと一致していることも確認します。

### TCP 49152へ接続できない

- iPadとWindowsの間にIP経路があるか確認する。
- iPad側のWi-FiまたはVPNが接続中か確認する。
- Windows側のVPNルートとファイアウォールを確認する。
- iPadを起動し、ロック解除して再試行する。

### 画面取得、Accessibility、HIDだけが失敗する

DDIを再マウントします。

~~~powershell
.\run.ps1 mount-ddi
~~~

その後、status、observeまたはelementsを再実行します。

### elementsが空になる

- ホーム画面ではなくアプリを前面へ出す。
- launchで対象アプリを起動する。
- システム警告が前面を覆っていないか確認する。
- passesを3以上へ増やす。

### elementsの件数が実行ごとに変わる

Accessibility走査の既知の性質です。複数パス統合を使用しても対象が欠落する場合はpassesを
増やします。完全なUIツリーとして扱いません。

### tap-textで項目が開かない

AX Activateの既知の制約です。同じ操作を繰り返さず、observeで位置を確認してtapを使用します。

### タップ位置がずれる

- 操作直前にobserveで新しい画面を取得する。
- iPadの回転後は古い座標を使わない。
- PNGの実ピクセル座標を指定する。
- Split ViewやSlide Overで表示領域が変わっていないか確認する。

### setup.ps1がsslpsk-pmd3のネイティブ依存検査で停止する

64bit版Python 3.10の通常インストールを使用し、その`DLLs`ディレクトリに`libssl-1_1.dll`と
`libcrypto-1_1.dll`が存在することを確認してから`setup.ps1`を再実行します。必要な別名DLLは
`.venv`内だけに配置されます。無関係なアプリケーションからDLLをコピーしたり、出所不明のDLLを
ダウンロードしたりしないでください。

### 接続がTimeoutErrorになる

まず、同じiPadで別プロセスがCoreDeviceのメディアまたはHIDサービスを使用していないか確認します。
動作確認環境では、RemotePairing、ユーザー空間トンネル、RSDまで正常に接続できていても、別の
ScreenStreamServerが端末のメディアセッションを保持しているとScreenCaptureServiceやHIDが
TimeoutErrorになりました。競合プロセスを終了し、操作を直列に再実行します。回転操作の直後は
新しいCLIコマンドとして後続操作を実行します。

### HID開始時にmedia-in-use相当のエラーになる

別の映像配信サーバーや操作プロセスが同じiPadのCoreDeviceメディア/HIDセッションを保持しています。
これはセッション競合であり、RemotePairingやRSDの失敗を意味しません。競合するプロセスを終了してから、
tap、swipe、press、type、pasteを再実行します。

## 21. 補足：成立が見込まれたが採用しなかった経路

ここでは、理論上または製品仕様上は利用できる可能性があったものの、動作確認環境では完了条件を
満たさず、最終構成に採用しなかった経路をまとめます。本文の手順には含めません。

### 21.1 Apple DevicesのWi-Fi接続

USB接続中にiPadを信頼し、Apple Devicesで「Wi-FiがオンになっているときにこのiPadを表示」を
有効にして適用しました。この方法は同一LAN上の端末管理に利用できる構成ですが、動作確認時は
ケーブルを外すとApple DevicesのサイドバーからiPadが消え、無線接続を確認できませんでした。
そのため、操作経路にはStikPairで作成したRemotePairingレコードを使用しました。

### 21.2 iPadOS 26での端末主導ペアリング

iPadOS 26でも開発者向けペアリングが成立する可能性はありましたが、動作確認した端末では
StikPairとのペアリングを完了できませんでした。iPadOS 27へ更新後、デベロッパモードの
「Pair with StikPair」とPIN入力を使う端末主導の手順で完了しました。本書は再現できた
iPadOS 27以降の手順を採用しています。

### 21.3 Accessibility操作だけで完結する経路

Accessibilityから項目名、選択状態、ボタンやヘッダの種別は取得できました。しかし、取得できる
要素にHID座標はなく、AX Activateはフォーカス移動やスクロールには作用しても、UIKitの項目を
確実には開きませんでした。そのためSemantic観測は対象の意味を読む用途とし、位置が必要な操作は
Vision観測と座標HIDへ分岐する構成にしました。

### 21.4 ローカル画像へのMarkdownリンク

Windows上のPNG自体は正常でも、AIクライアントがローカルファイルへのMarkdownリンクを画像として
展開せず、灰色のプレースホルダーだけを表示する場合がありました。画像取得の失敗ではないため、
画像添付機能または画像データを直接受け取れるAPIを使用して共有しました。

### 21.5 SideloadlyのAnisette初期化

Remote AnisetteではApple側の404、Local AnisetteではDLLの欠落やアクセス拒否が発生し、
Apple Accountのパスワード入力まで進まない状態がありました。認証情報を変更しても解決しない
段階のエラーであり、Sideloadlyが使用するAnisette DLLを同一構成で初期化できる状態へ修復して
からサイドロードを行いました。

## 22. 完了チェックリスト

### 初回構築

- [ ] iPadをUSB接続し、「このコンピュータを信頼」を完了した
- [ ] iPadのデベロッパモードを有効にし、再起動後の確認を完了した
- [ ] StikPairをiPadへインストールし、署名元を信頼した
- [ ] StikPairとデベロッパモード画面でPINペアリングを完了した
- [ ] rp_pairing_file.plistをWindowsへ安全に移した
- [ ] setup.ps1でPython 3.10環境を作成した
- [ ] convert-pairingでpymobiledevice3形式へ変換した
- [ ] config.tomlへUDIDと到達先を設定した
- [ ] doctorがok=trueを返した
- [ ] mount-ddiがmountedまたはalready-mountedを返した

### 共通経路

- [ ] statusでRemotePairing、ユーザー空間トンネル、RSD、画面取得を確認した
- [ ] launchで設定アプリを起動した
- [ ] press homeでホーム画面へ戻った
- [ ] tapまたはswipeが画面へ作用した
- [ ] typeまたはpasteで文字を入力した

### 観測経路

- [ ] Vision経路のobserveでscreen.pngとサムネイルを取得した
- [ ] Semantic経路のelementsで前面アプリのラベルを取得した
- [ ] Accessibilityに座標がない場合、Vision経路へ切り替えた
- [ ] 操作後に画像差分、after.png、elementsのいずれかで結果を確認した

### 再起動後

- [ ] iPadをロック解除した
- [ ] TCP 49152への到達を確認した
- [ ] doctor、mount-ddi、statusの順に復旧を確認した
- [ ] USB再接続や再ペアリングが不要であることを確認した

## 23. 配布前の検査

テストと公開前検査を実行します。

~~~powershell
.\check.ps1
~~~

公開前検査は、HEADから到達できる全コミットのAuthor/CommitterメールがGitHub noreply形式であることも検査します。完全なGit履歴のあるcheckoutで実行してください。履歴がない場合やshallow cloneでは失敗します。ローカルの退避refは対象外です。CIではクリーンなWindows runnerでsetup.ps1を実行し、ネイティブバックエンド、依存関係の整合性、Pythonのコンパイル、単体テスト、公開前検査を確認します。

check.ps1は最初にsslpsk-pmd3のネイティブバックエンドを読み込めることを検査し、その後で単体テストと公開前検査を続けて実行します。公開前検査はGitの公開候補ファイルを対象にするため、ignoreしたローカル実行時ファイルでは失敗しません。実行時config、ペアリング記録、秘密情報ディレクトリ、リポジトリ直下の生成物／ビルドディレクトリを拒否し、続いてテキストファイル内のApple Accountメールアドレス、実機UDID、Tailscaleの100.64.0.0/10内のIPv4アドレス、秘密鍵マーカーを検査します。サニタイズ済みの文書画像・ログ・ペアリング用途ではないplist fixtureは許可します。配布物にはconfig.toml、StikPairの書き出しファイル、pairing_record、artifacts、secrets、仮想環境を含めません。

## 24. 参考資料

- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)
- [StikPair](https://github.com/StikDebug/StikPair)
- [Sideloadly](https://sideloadly.io/)
- [Apple Platform Security](https://support.apple.com/guide/security/welcome/web)

## ライセンス

本パッケージのコードはGNU General Public License v3.0以降で配布します。依存ライブラリの
ライセンスはTHIRD_PARTY.mdを参照してください。

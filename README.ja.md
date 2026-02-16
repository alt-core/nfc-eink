# nfc-eink

[English](README.md)

NFC e-ink カードディスプレイ用の Python ライブラリです。

4種類のデバイス (2解像度 x 2色モード) に対応:
- 400x300 / 296x128
- 4色 (黒/白/黄/赤) / 2色 (黒/白)

このライブラリは [@niw氏の gist](https://gist.github.com/niw/3885b22d502bb1e145984d41568f202d#file-ezsignepaperprotocol-md) で公開されているプロトコル仕様を [nfcpy](https://github.com/nfcpy/nfcpy) で実装したものです。本プロジェクトは独自に開発されたものであり、元の仕様の作者とは無関係です。

> **免責事項:** このライブラリは個人的な利用目的で作成したものであり、品質の保証はありません。利用は自己責任でお願いします。対象デバイスへの損害について作者は一切責任を負いません。

> **備考:** このプロジェクトは [Claude Code](https://claude.ai/claude-code) で100%作成されました。

## インストール

```bash
pip install nfc-eink[cli]
```

## クイックスタート

### Python API

```python
from nfc_eink import EInkCard
from PIL import Image

with EInkCard() as card:
    card.send_image(Image.open("photo.png"))
    card.refresh()
```

### CLI

```bash
# 画像をカードに送信
nfc-eink send photo.png

# 画面を白でクリア
nfc-eink clear

# デバイス情報を表示
nfc-eink info

# 基本的な動作確認 (全面黒 / ストライプパターン)
nfc-eink diag black
nfc-eink diag stripe
```

## 動作要件

- Python 3.9+
- USB NFCリーダー (Sony RC-S380 PaSoRi で動作確認)
- [nfcpy](https://github.com/nfcpy/nfcpy) - NFC通信
- [lzallright](https://github.com/vlaci/lzallright) - LZO圧縮

## 対応デバイス

| 解像度 | 色数 | パレット |
|--------|------|---------|
| 400x300 | 4 | 黒、白、黄、赤 |
| 400x300 | 2 | 黒、白 |
| 296x128 | 4 | 黒、白、黄、赤 |
| 296x128 | 2 | 黒、白 |

デバイスのパラメータ (解像度、色数、ブロック構成) は 00D1 コマンドで自動検出されます。

## 応用

```python
from nfc_eink import EInkCard

# 生のピクセルデータ (デバイスの解像度に合った色インデックス配列) を使用
pixels = [[1] * 400 for _ in range(300)]  # 全面白
with EInkCard() as card:
    card.send_image(pixels)
    card.refresh()
```

## ライセンス

MIT

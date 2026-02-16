# nfc-eink

[English](README.md)

NFC e-ink カードディスプレイ (400x300, 4色) 用の Python ライブラリです。

このライブラリは [@niw氏の gist](https://gist.github.com/niw/3885b22d502bb1e145984d41568f202d#file-ezsignepaperprotocol-md) で公開されているプロトコル仕様を [nfcpy](https://github.com/nfcpy/nfcpy) で実装したものです。本プロジェクトは独自に開発されたものであり、元の仕様の作者とは無関係です。

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

# デバイス情報を表示
nfc-eink info
```

## 動作要件

- Python 3.9+
- USB NFCリーダー (Sony RC-S380 PaSoRi で動作確認)
- [nfcpy](https://github.com/nfcpy/nfcpy) - NFC通信
- [lzallright](https://github.com/vlaci/lzallright) - LZO圧縮

## 対応色

| インデックス | 色   |
|-------------|------|
| 0           | 黒   |
| 1           | 白   |
| 2           | 黄   |
| 3           | 赤   |

## 応用

```python
from nfc_eink import EInkCard

# 生のピクセルデータ (300x400 の色インデックス配列, 値は 0-3) を使用
pixels = [[1] * 400 for _ in range(300)]  # 全面白
with EInkCard() as card:
    card.send_image(pixels)
    card.refresh()
```

## ライセンス

MIT

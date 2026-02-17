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
pip install "nfc-eink[cli] @ git+https://github.com/alt-core/nfc-eink.git"
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

## ディザリング

画像変換では [CIELAB](https://ja.wikipedia.org/wiki/L*a*b*%E8%A1%A8%E8%89%B2%E7%B3%BB) 色空間でのエラー拡散ディザリングを使用し、知覚的に正確な色変換を行います。詳細は [docs/dithering.ja.md](docs/dithering.ja.md) を参照してください。

| アルゴリズム | デフォルト | 説明 |
|-------------|:--------:|------|
| `pillow` | yes | Pillow 内蔵 (RGB空間 Floyd-Steinberg、高速) |
| `atkinson` | | 高コントラスト、制限パレット向き (CIELAB) |
| `floyd-steinberg` | | 標準的なエラー拡散 (CIELAB) |
| `jarvis` | | 最も滑らか、写真向き (CIELAB) |
| `stucki` | | Jarvis に近い品質 (CIELAB) |
| `none` | | 最近傍色のみ (CIELAB) |

```python
with EInkCard() as card:
    card.send_image(Image.open("photo.png"), dither="jarvis")
    card.refresh()
```

```bash
nfc-eink send photo.png --dither jarvis
```

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

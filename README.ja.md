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

# 画面いっぱいに表示 (はみ出た部分をクロップ)
nfc-eink send photo.png --resize cover

# 写真モード: 実写写真に最適化
nfc-eink send photo.png --photo

# 画面を白でクリア
nfc-eink clear

# デバイス情報を表示
nfc-eink info

# 単色塗りつぶし (表示テスト / キャリブレーション用)
nfc-eink diag black
nfc-eink diag white
nfc-eink diag yellow   # 4色デバイスのみ
nfc-eink diag red      # 4色デバイスのみ

# ブロックマッピングテスト
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
| `jarvis` | | 最も滑らか、広範囲エラー拡散 (CIELAB) |
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

### 写真モード

`--photo` は実写写真に適した4つのオプションをまとめたプリセットです:

- **`--dither atkinson`**: Atkinson ディザリングは量子化誤差の 25% を意図的に捨てることで、コントラストを維持しクリアな印象を生む。4色しかない極端に制限されたパレットでは、誤差を100%拡散する方式 (Floyd-Steinberg, Jarvis) だと泥っぽい仕上がりになりやすい。
- **`--resize cover`**: 画像を画面全体に拡大し、はみ出た部分をクロップする。写真は余白なく表示した方が見栄えがよい。
- **`--palette tuned`**: 理想的な RGB 値ではなく、実際の e-ink パネルの発色に合わせて調整されたパレットを使用する。ディザリングアルゴリズムがパネルの実際の表現能力をより正確に把握でき、色の選択精度が向上する。
- **`--tone-map`**: 画像の輝度レンジをパネルの表現可能な明るさに圧縮する。理想の白 (L\*=100) とパネルの実際の白 (L\*≈66) の乖離が大きいため、これを行わないとディザリング誤差が蓄積し、明るい領域に黄色のアーティファクトが発生する。

個別のオプションで上書きも可能: `--photo --dither jarvis` は Jarvis ディザリングを使いつつ、他の写真モード設定は維持される。

## 応用

```python
from nfc_eink import EInkCard

# 生のピクセルデータ (デバイスの解像度に合った色インデックス配列) を使用
pixels = [[1] * 400 for _ in range(300)]  # 全面白
with EInkCard() as card:
    card.send_image(pixels)
    card.refresh()
```

## デモ

`examples/tree_demo.py` — NFC e-ink カードにデバイス固有の L-system 樹木を育てるデモです。シリアル番号から決定論的に木の形状が生成され、タッチするたびに1段階成長します。

```bash
# デモ実行 (NFC カードをループで待機)
python examples/tree_demo.py

# プレビューモード: NFC 機器なしで各ステップの画像を PNG 出力
python examples/tree_demo.py --preview DEMO001
```

## ライセンス

MIT

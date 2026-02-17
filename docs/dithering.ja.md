# ディザリングアルゴリズム

[English](dithering.md)

## 背景

本ライブラリが対応する 4色 e-ink デバイスのパレットは以下の通り:

| インデックス | 色 | RGB (量子化用) |
|:-----------:|:---:|:---:|
| 0 | 黒 | (0, 0, 0) |
| 1 | 白 | (255, 255, 255) |
| 2 | 黄 | (255, 255, 0) |
| 3 | 赤 | (255, 0, 0) |

フルカラー画像をこの 4色に減色する際、単純に最近傍色に置き換えるとグラデーションや中間色が失われる。ディザリングは、量子化誤差を周辺ピクセルに拡散することで、マクロ的に元の色調を再現する手法である。

### パレット RGB 値と実際の発色の乖離

上記のパレット RGB 値は**理想値**であり、実際の e-ink デバイスの発色とは異なる。e-ink の特性として:

- **黒**: 完全な黒にはならず、やや灰色がかる
- **白**: 純白ではなく、クリーム色や薄灰色に近い
- **黄**: くすんだ黄色で、(255, 255, 0) ほど鮮やかではない
- **赤**: オレンジ寄りの赤で、(255, 0, 0) とは色相がずれる

ディザリングは「入力画像の色をパレット色の混合で近似する」処理であるため、パレットの CIELAB 値が実際の発色と乖離していると、最近傍色の選択やエラー拡散の方向が最適でなくなる。たとえば、実物では赤がオレンジ寄りであるにもかかわらず純赤 (255, 0, 0) として計算すると、中間色でのマッピング精度が低下する。

理想的には、実デバイスの各色をカラーメーター等で測定し、その実測 RGB 値をパレットとして使用すべきである。現在の実装ではこのキャリブレーションは行っておらず、理想的な RGB 値をそのまま使用している。`nfc-eink diag black/white/yellow/red` で各色のベタ塗りを表示して実物の発色を確認できる。

### Pillow のみの実装の問題点

Pillow の `Image.quantize()` による Floyd-Steinberg ディザリング (RGB 空間) には2つの問題がある:

1. **RGB 空間での色距離**: RGB の Euclidean 距離は人間の色知覚と一致しない。特にこの偏ったパレット (青・緑・紫が不在) では、中間色が黄や赤に誤マッピングされやすい
2. **アルゴリズム固定**: Pillow は Floyd-Steinberg 以外のディザリングをサポートしておらず、極端に制限されたパレットには最適ではない

## 色空間: RGB vs CIELAB

### RGB の問題

RGB は光の加法混色に基づく色空間であり、人間の知覚的な「色の近さ」とは一致しない。例えば:

- RGB 距離では `(0, 100, 0)` (暗い緑) と `(0, 0, 100)` (暗い青) は等距離だが、人間の目には青の方がずっと暗く見える
- 彩度の高い色 (黄、赤) が不釣り合いに「近い」と判定されることがある

### CIELAB (L\*a\*b\*)

CIELAB は国際照明委員会 (CIE) が 1976 年に定義した、知覚的に均一な色空間である:

- **L\*** : 明度 (0=黒, 100=白)
- **a\*** : 赤-緑 軸 (正=赤, 負=緑)
- **b\*** : 黄-青 軸 (正=黄, 負=青)

CIELAB 空間での Euclidean 距離 (CIE76 ΔE) は、人間が知覚する「色の違い」にほぼ比例する。これにより:

- 最近傍色の選択精度が向上する
- エラー拡散のベクトルが知覚的に意味のある方向になる

### RGB → CIELAB 変換

変換は3段階で行う:

1. **sRGB ガンマ展開** : 非線形 sRGB (0-255) → リニア RGB (0-1)
   - `v ≤ 0.04045` のとき `v / 12.92`
   - それ以外 `((v + 0.055) / 1.055) ^ 2.4`

2. **リニア RGB → CIE XYZ** : 3x3 行列変換 (D65 光源基準)

3. **XYZ → CIELAB** : 非線形変換
   - `f(t) = t^(1/3)` (t > δ³ のとき)
   - `f(t) = t/(3δ²) + 4/29` (それ以外)
   - ただし δ = 6/29

## ディザリングアルゴリズム

### エラー拡散ディザリングの原理

エラー拡散ディザリングは以下の手順で動作する:

1. 画像を左上から右下へ走査する
2. 各ピクセルについて、パレット中の最近傍色を選択する
3. 元の色と選択された色の差 (量子化誤差) を計算する
4. この誤差を、まだ処理していない周辺ピクセルに重み付きで加算する

重みの分配パターンがアルゴリズムごとに異なる。`*` は現在のピクセル、数値は重み、分母で除算する。

### Floyd-Steinberg (1976)

```
        * 7
    3 5 1
    (÷ 16)
```

- 4近傍に 100% のエラーを分配
- 最も標準的なアルゴリズム
- 滑らかな結果を生むが、極端に制限されたパレットでは「泥っぽく」なりやすい
- 高速 (4ピクセルへの書き込みのみ)

### Atkinson (1984)

```
        * 1 1
    1 1 1
        1
    (÷ 8)
```

- 6近傍に **75%** のエラーを分配 (25% は捨てる)
- Bill Atkinson が Macintosh の 1bit ディスプレイ向けに設計
- エラーの一部を捨てることで:
  - コントラストが維持される
  - 暗部のディテールは犠牲になるが、全体的にクリアな印象
  - 極端に制限されたパレットでの「泥っぽさ」を防ぐ
- 4色 e-ink のように極端に制限されたパレットに適している

### Jarvis-Judice-Ninke (1976)

```
            * 7 5
    3 5 7 5 3
    1 3 5 3 1
    (÷ 48)
```

- 12近傍に 100% のエラーを分配
- 最も広範囲にエラーを拡散し、最も滑らかな結果を生む
- 写真のグラデーション再現に優れる
- 処理が遅い (12ピクセルへの書き込み)

### Stucki (1981)

```
            * 8 4
    2 4 8 4 2
    1 2 4 2 1
    (÷ 42)
```

- Jarvis と同じ12近傍だが重みが異なる
- Jarvis とほぼ同等の品質
- 中心に近いピクセルへの重みがやや強い

## 本ライブラリの設計

### アルゴリズム選択

`convert_image()` の `dither` パラメータでアルゴリズムを指定できる:

```python
from nfc_eink.convert import convert_image
from PIL import Image

img = Image.open("photo.png")

# Pillow 内蔵 Floyd-Steinberg (デフォルト) — 高速、RGB空間
pixels = convert_image(img, dither='pillow')

# Atkinson — 高コントラスト、制限パレット向き (CIELAB)
pixels = convert_image(img, dither='atkinson')

# Floyd-Steinberg — 標準的なエラー拡散 (CIELAB)
pixels = convert_image(img, dither='floyd-steinberg')

# Jarvis-Judice-Ninke — 最も滑らか、写真向き (CIELAB)
pixels = convert_image(img, dither='jarvis')

# Stucki — Jarvis に近い品質 (CIELAB)
pixels = convert_image(img, dither='stucki')

# ディザリングなし — 最近傍色のみ (CIELAB)
pixels = convert_image(img, dither='none')
```

CLI からの使用:

```bash
nfc-eink send photo.png                        # デフォルト: pillow
nfc-eink send photo.png --dither atkinson      # CIELAB Atkinson
nfc-eink send photo.png --dither floyd-steinberg
nfc-eink send photo.png --dither none
```

### Pillow (デフォルト)

`dither='pillow'` (デフォルト) は Pillow の `Image.quantize()` による Floyd-Steinberg ディザリング (RGB 空間) を使用する。高速で安定しているが、RGB 空間での色距離計算のため、CIELAB ベースの実装と比べて知覚的な色変換の精度は劣る。

CIELAB ベースの各アルゴリズム (`atkinson`, `floyd-steinberg`, `jarvis`, `stucki`, `none`) は色変換の精度で優れるが、処理速度は遅い (400x300 で 1〜2秒)。

### 実装方針

- 色距離の計算は全て CIELAB 空間で行う (CIE76 ΔE)
- RGB → CIELAB 変換は標準公式で自前実装 (外部ライブラリ不要)
- 各アルゴリズムは重み行列の差し替えのみで実現 (コア処理は共通)
- 2色 (黒/白) モードでも同一の CIELAB ベース実装を使用
- Pillow 内蔵の quantize によるフォールバックも利用可能

## 参考文献

- Floyd, R.W. and Steinberg, L. (1976). "An Adaptive Algorithm for Spatial Greyscale." *Proceedings of the Society for Information Display*, 17(2), 75-77.
- Atkinson, B. (1984). 初代 Macintosh の HyperCard 向けに開発。正式な論文はないが、アルゴリズムの詳細は広く知られている。
- Jarvis, J.F., Judice, C.N. and Ninke, W.H. (1976). "A Survey of Techniques for the Display of Continuous Tone Pictures on Bilevel Displays." *Computer Graphics and Image Processing*, 5(1), 13-40.
- Stucki, P. (1981). "MECCA - a multiple-error correcting computation algorithm for bilevel image hardcopy reproduction." IBM Research Report RZ1060.
- CIE (1976). "Official Recommendations on Uniform Color Spaces, Color-Difference Equations, and Psychometric Color Terms." CIE Publication No. 15, Supplement 2.
- Tanner Helland. "[Image Dithering: Eleven Algorithms and Source Code](https://tannerhelland.com/2012/12/28/dithering-eleven-algorithms-source-code.html)."

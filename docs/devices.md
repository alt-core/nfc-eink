# Supported Devices

## Device Variants

| Device | A0 raw | color_mode | bpp | swap | rotated | hflip | FB layout |
|--------|--------|-----------|-----|------|---------|-------|-----------|
| 296x128 2-color | 296×128 | 0x01 | 1 | no | yes (CW90) | no | 128×296 |
| 400x300 4-color | 400×600 | 0x07 | 2 | no | no | no | 400×300 |
| 296x128 4-color | 128×592 | 0x07 | 2 | yes | yes (CW90) | no | 128×296 |
| 400x300 2-color | 300×400 | 0x47 | 1 | yes | no | yes | 400×300 |

- **A0 raw**: A0 tag の width × height_raw フィールド値
- **swap**: A0 の width < height のとき、landscape にするため width/height を入れ替え
- **rotated**: `_ROTATED_PANELS` に該当する場合、CW90 回転で FB レイアウトに変換
- **hflip**: swap したが rotate しないパネルで、水平反転で軸を補正

## A0 TLV Structure

```
A0: [flags, color_mode, rows_per_block, height_raw_hi, height_raw_lo, width_hi, width_lo]
```

- `height_raw = physical_dimension × bits_per_pixel`
- `a0[3:5] × a0[5:7] / 8 = fb_total_bytes` (全デバイスで成立)
- `rows_per_block` は全デバイスで 32

## Color Mode (a0[1])

Note: "color mode" is a name assigned by this project for convenience. The actual semantics of this byte are unknown; it may encode display type, panel driver ID, or other information beyond color capability.

| color_mode | bpp | Devices |
|-----------|-----|---------|
| 0x01 | 1 | 296x128 2-color |
| 0x07 | 2 | 400x300 4-color, 296x128 4-color |
| 0x47 | 1 | 400x300 2-color |

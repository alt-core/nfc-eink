# 400x300 4-Color e-Paper NFC Protocol

I investigated the protocol of the name-tag-size e-paper device that can be rewritten via NFC.

## 1. Assumptions

- Screen size: `400 x 300`
- Color index (2-bit):
  - `0 = Black`
  - `1 = White`
  - `2 = Yellow`
  - `3 = Red`
- Transport: ISO7816 APDU over NFC

## 2. Sequence

1. Authentication  
   - `0020 00010420091210` -> `9000`
2. Image data transfer
   - Send multiple `F0D3 ...`
3. Start screen refresh  
   - `F0D4 858000` -> `9000`
4. Poll refresh completion
   - Send: `F0DE 000001`
   - Response: `01 9000` = refreshing
   - Response: `00 9000` = refresh complete

## 3. Image data format

### 3.1 Block structure

- Split by every 20 rows
- Total blocks: `300 rows / 20 rows = 15 blocks`
- `blockNo`: `0..14`

### 3.2 Uncompressed size per block

- Per row: `400 pixel / 4 pixel = 100 byte`
- Per block: `100 byte * 20 rows = 2000 byte`

### 3.3 Packing

Pack 4 pixels into 1 byte.

- `byte = p0 | (p1 << 2) | (p2 << 4) | (p3 << 6)`
- `p0..p3` are color indexes in 0..3
- Byte order inside a row is right-to-left

### 3.4 Compression

- Compress each 2000-byte block with `LZO1X-1` (`lzo1x_1_compress`)

## 4. `F0D3 ...` (image transfer) spec

### 4.1 APDU format

- Header: `CLA INS P1 P2 Lc`
- `CLA`: `F0`
- `INS`: `D3`
- `P1`: `00`
- `P2`:
  - `00`: intermediate fragment of a block
  - `01`: final fragment of a block
- `Lc`: `2 + len(compressedFragment)`
- Data:
  - `blockNo` (1 byte)
  - `fragNo` (1 byte)
  - `compressedFragment` (variable)

### 4.2 Fragment size limit

- Max `compressedFragment` is 250 bytes (`0xFC - 2`)
- One block can be split into multiple `F0D3 ...` APDUs

### 4.3 Reassembly rules on receiver side

1. Group by `blockNo`, then concatenate in `fragNo` order
2. When `P2=01` arrives, that `blockNo` is complete
3. Decompress the completed block with LZO back to 2000 bytes

## 5. `F0D3 ...` examples

### Example 1: one-packet block

`F0D300011600000255555555552000000000000000B10000110000`

Breakdown:

- `F0 D3 00 01 16`  
  - `P2=01`, so this APDU is the final fragment for the block
  - `Lc=0x16` (22 bytes)
- First 2 bytes of Data:
  - `00` = `blockNo=0`
  - `00` = `fragNo=0`
- Remaining 20 bytes are compressed payload

### Example 2: first fragment of a multi-packet block

`F0D30000FC020002...`

Breakdown:

- `P2=00` (intermediate fragment)
- `Lc=0xFC`
- Data starts with:
  - `02` = `blockNo=2`
  - `00` = `fragNo=0`

For the same `blockNo=2`, `fragNo=1,2,...` follows, and only the last fragment uses `P2=01`.

## 6. Helper commands (optional)

Depending on environment, these can be used for capability checks.

- `F0D8 000005000000000E`: `"4_color Screen"` (panel type)
- `00D1 000000`: device info

## 7. Status words

- `9000`: success
- `6700`: length/format error
- `6D00`: INS not supported
- `6A86`: invalid P1/P2

Do not consider refresh complete with only `F0D4 ...` = `9000`. Confirm `00 9000` from `F0DE ...`.

## 8. CoreNFC implementation notes

- Not officially documented, but `NFCTagReaderSession.connect(to:)` is disconnected after about 20 seconds from session start.
- If you keep sending `F0D3 ...`, then after `F0D4 ...` wait with `F0DE ...`, the session can disconnect mid-refresh and the update may not complete.
- So, after finishing `F0D3 ...`, call `NFCTagReaderSession.restartPolling()` once, authenticate again with `0020 ...`, then start refresh with `F0D4 ...` and wait with `F0DE ...` to get another ~20 seconds of margin.

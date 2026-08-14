# Caoliao QR API Notes

Source checked on 2026-08-13:

- Documentation: https://cli.im/open-api/qrcode-api/create-qr-code.html
- Create endpoint: `GET https://api.2dcode.biz/v1/create-qr-code`
- Decode endpoint: `POST https://api.2dcode.biz/v1/read-qr-code`

## Create Parameters

| Parameter | Use in this skill | Notes |
| --- | --- | --- |
| `data` | Required | URL-encoded source text. The documentation recommends no more than 900 characters in typical use. |
| `format` | `svg` | API supports `png` and `svg`. SVG is used as the canonical matrix source. |
| `error_correction` | `H` | Documented levels are L 7%, M 15%, Q 25%, and H 30%. |
| `border` | `4` | Width is measured in QR modules. |
| `size` | Not sent for SVG | Documentation says this affects bitmap output only. |

The documentation states that normal API requests have no fixed request limit, while abusive, malicious, or illegal traffic may be rejected. The endpoint exposes no logo parameter and no multi-item request body. This skill therefore calls it once per unique URL and performs company branding locally.

## Decode Contract

Upload the generated PNG as multipart field `file`. A successful response has this shape:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "contents": ["decoded text"]
  }
}
```

Accept a QR only when `code` is `0` and `data.contents` contains the exact original URL. Network success alone is not validation.

## Observed SVG Shape

The create endpoint currently returns one square `viewBox` and a path with `id="qr-path"`. Each dark module is represented as an axis-aligned unit-square subpath. The generator validates this structure before composing a branded SVG or PNG. If the API changes this representation, fail instead of silently emitting a potentially corrupt QR.

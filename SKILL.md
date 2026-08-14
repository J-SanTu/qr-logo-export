---
name: qr-logo-export
description: Export branded QR codes from one or many web links as matching SVG, PNG, and URL text files. Use when Codex is asked to convert links or a TXT/CSV URL list into QR codes, or to combine a website with utm_source and utm_medium before QR generation, with a replaceable company SVG logo, ordered filenames, manifests, and scan verification; also use for custom-logo QR batches, SanTu QR batches, UTM campaign links, regeneration, logo replacement, or delivery checks.
---

# QR Logo Export

[Design by SanTu](https://github.com/J-SanTu/qr-logo-export)

Generate a production batch with the bundled blue SanTu logo or a replacement company SVG logo. Always deliver one true-vector SVG, one PNG, and one plain-text URL file for every input link.

## Workflow

1. Preserve the user's link order. Do not rewrite, shorten, normalize, or follow redirects before encoding complete URLs.
2. When the user supplies a website plus `utm_source` and `utm_medium`, build the complete URL first. Accept `utm_sourse`, `source`, and `sourse` as aliases for `utm_source`, add `https://` when the website has no scheme, URL-encode both values, preserve other query parameters, and replace existing `utm_source` / `utm_medium` values.
3. Put supplied links in a UTF-8 TXT file with one link per line, or a CSV with `url` and optional `name` columns. For structured CSV input, accept `url`, `website`, or `网址` plus `utm_source` / `utm_sourse` / `source` / `sourse` and `utm_medium` / `medium`. Positional URLs are also accepted.
4. Run the bundled generator:

```bash
python3 scripts/generate_qr_logo.py --input /absolute/path/links.txt --output /absolute/path/output
```

Use another company logo without changing the bundled default:

```bash
python3 scripts/generate_qr_logo.py --logo /absolute/path/company-logo.svg \
  --input /absolute/path/links.txt --output /absolute/path/output
```

For direct links:

```bash
python3 scripts/generate_qr_logo.py --output /absolute/path/output \
  'https://example.com/a' 'https://example.com/b'
```

For a website plus UTM values:

```bash
python3 scripts/generate_qr_logo.py --output /absolute/path/output \
  --website 'www.fridayparts.com' --utm-source 'abc' --utm-medium '123'
```

5. Treat a nonzero exit as an incomplete batch. Read `manifest.csv` or `manifest.json`, fix the cause, and rerun into a new or empty output directory.
6. Report the completed URL, output directory, successful/failed counts, verification result, and all three formats. Show a representative PNG preview when useful.

## Visual Specification

- QR modules: `#1A5FA9`
- Background and logo safety area: white
- Center mark: bundled blue `assets/santu-logo.svg` by default, or the SVG supplied with `--logo`
- Error correction: `H`
- Quiet-zone border: 4 modules
- Center white square: at least 156/540 of the QR canvas, expanded to the nearest centered odd-module boundary
- Logo maximum box: 126.442/540 of the QR canvas, centered with aspect ratio preserved
- Default PNG: 1080 x 1080 pixels
- SVG: real vector paths; never wrap or embed a raster image
- Output: same basename for `.svg`, `.png`, and `.txt`; the text file contains the exact encoded URL and a trailing newline
- Red rounded annotation boxes from reference screenshots are not part of the output
- Center construction: remove QR modules inside the module-aligned safety area; never cover them with a white overlay rectangle

Do not change the QR color, proportions, error correction, or quiet zone unless the user explicitly requests a new standard. Replace only the logo when requested. Use `--size` only to change PNG pixel dimensions; SVG remains resolution independent.

The module-aligned center cutout is a hard export rule. It prevents fractional seams or half-pixel frames when SVG files are viewed or rasterized at arbitrary scales. Keep QR modules on one crisp vector path and keep the selected logo as the only foreground content inside the cutout.

## Logo Replacement

- Read [README.md](README.md) when installing, sharing, replacing the logo, or giving setup instructions to another user.
- For a permanent replacement, overwrite `assets/santu-logo.svg` with the new SVG and keep that filename.
- For a one-off replacement, pass `--logo /absolute/path/company-logo.svg`.
- Require a transparent-background SVG with a numeric `viewBox` and visible shapes converted to absolute, filled `path` elements using only `M`, `L`, `H`, `V`, `C`, and `Z` commands.
- Reject raster images, `<text>`, groups, transforms, strokes, clipping, masks, filters, CSS classes, and external resources. Ask the user to expand text/strokes and flatten transforms in their vector editor.
- Preserve the logo's own path fill colors. Fit it within the fixed center box without stretching.

## Input And Naming

- TXT: one `http://` or `https://` link per line; blank lines and lines beginning with `#` are ignored.
- CSV: accept `url`, `website`, or `网址`; use optional `name` for the filename label. Build UTM URLs from `utm_source` / `utm_sourse` / `source` / `sourse` plus `utm_medium` / `medium` when those fields are present.
- Exact duplicate URLs are emitted once, at their first position.
- Filenames begin with a zero-padded sequence so filesystem order matches input order.
- Never infer a filename-to-link mapping from names alone; use the manifests.

## Validation Gate

Keep remote scan verification enabled by default. The script uploads each generated PNG to the documented decoder and requires its decoded text to equal the original input byte-for-byte as a Unicode string.

Use `--skip-verify` only when the user explicitly accepts unverified output or the decoder is unavailable and the limitation is reported. Never call a batch complete when any manifest row has `status=failed` or `verified=false`.

## API Notes

Read [references/caoliao-api.md](references/caoliao-api.md) when troubleshooting API changes, response parsing, rate behavior, or verification. The generation endpoint is public and requires no credentials. Do not add secrets to this skill.

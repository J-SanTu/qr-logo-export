<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="QR Logo Export: build UTM links and export branded, scan-verified SVG, PNG, and URL text files">
</p>

<p align="center">
  <strong>中文</strong> | <a href="#english">English</a>
</p>

<p align="center">
  <a href="https://github.com/J-SanTu/qr-logo-export"><strong>Design by SanTu</strong></a>
</p>

# QR Logo Export

把完整链接，或“网址 + UTM 参数”，批量转换为品牌二维码。每条链接同时导出真矢量 **SVG**、`1080 x 1080` **PNG** 和保存完整链接的 **TXT**，保留输入顺序，并生成逐张扫码验证结果。

> 默认使用 FP Logo；替换一个 SVG 文件，即可生成你公司的版本。

## 实际输出

<p align="center">
  <img src="./assets/readme/example-fp-qr.png" width="420" alt="使用 FP 圆形 Logo 生成的真实二维码输出">
</p>

| 输出 | 规格 |
| --- | --- |
| SVG | 纯矢量路径，不嵌入位图，任意缩放 |
| PNG | 默认 `1080 x 1080` 像素 |
| TXT | 与 SVG/PNG 同名，保存二维码实际编码的完整链接 |
| Logo | 居中、等比例缩放、保留原填充色 |
| 二维码 | `#1A5FA9`、H 级容错、4 模块静区 |
| 验证 | 默认逐张远程解码，结果必须与原链接完全一致 |

<p align="center">
  <img src="./assets/readme/workflow.svg" width="100%" alt="拼接完整链接、应用公司 Logo、导出并验证 SVG、PNG 与链接 TXT 的三步流程">
</p>

## 最快安装

### 1. 准备环境

- Codex 桌面端、Codex CLI 或 Codex IDE 扩展
- Python 3
- [Pillow](https://pypi.org/project/pillow/)

```bash
python3 -m pip install Pillow
```

### 2. 安装 Skill

**GitHub 安装（推荐）**

在 Codex 中输入：

```text
$skill-installer

请安装这个 Skill：
https://github.com/J-SanTu/qr-logo-export
```

**手动安装**

把整个 `qr-logo-export` 文件夹复制到：

```text
~/.agents/skills/qr-logo-export/
```

检查下列文件是否存在：

```text
~/.agents/skills/qr-logo-export/SKILL.md
```

如果 Skill 没有立即出现，重启 Codex。

## 30 秒生成第一批

安装后，在 Codex 中输入：

```text
使用 $qr-logo-export，把下面的链接依次生成带公司 Logo 的 SVG、PNG 和链接 TXT：
https://example.com/a
https://example.com/b
```

Codex 会保持链接顺序，生成同名 `.svg` / `.png` / `.txt` 文件，并输出 `manifest.csv` 和 `manifest.json`。

## 网址 + UTM 参数

只提供基础网址、`utm_source` 和 `utm_medium` 时，Skill 会先拼接完整链接，再把该链接写入二维码和同名 TXT。

输入示例：

```text
网址：www.fridayparts.com
source：abc
medium：123
```

拼接结果：

```text
https://www.fridayparts.com/?utm_source=abc&utm_medium=123
```

在 Codex 中可直接输入：

```text
使用 $qr-logo-export：
网址 www.fridayparts.com
sourse: abc
medium: 123
```

命令行用法：

```bash
python3 scripts/generate_qr_logo.py \
  --website 'www.fridayparts.com' \
  --utm-source 'abc' \
  --utm-medium '123' \
  --output /absolute/path/output
```

`utm_source` 也兼容 `utm_sourse`、`source`、`sourse`；`utm_medium` 也兼容 `medium`。缺少协议时自动补 `https://`。原网址已有其他查询参数时会予以保留；已有同名 UTM 参数时会由新值替换。参数值会自动进行标准 URL 编码。

## 替换公司 Logo

### 方式 A：永久替换默认 Logo

1. 准备公司 Logo 的 SVG 文件。
2. 将文字与描边转为轮廓，并展开群组和变换。
3. 保留数字形式的 `viewBox`，只使用带填充色的 `<path>`。
4. 用新文件覆盖 [`assets/fp-logo.svg`](./assets/fp-logo.svg)，文件名保持不变。
5. 先生成一张测试二维码，确认外观和扫码结果。

### 方式 B：单次使用其他 Logo

```bash
python3 scripts/generate_qr_logo.py \
  --logo /absolute/path/company-logo.svg \
  --input /absolute/path/links.txt \
  --output /absolute/path/output
```

### Logo SVG 要求

| 支持 | 不支持 |
| --- | --- |
| 透明背景的真矢量 SVG | 嵌入 PNG / JPG |
| 数字 `viewBox` | `<text>` 文字元素 |
| 绝对坐标 `M/L/H/V/C/Z` 路径 | 群组、transform、stroke |
| 直接写在 `<path>` 上的填充色 | 裁切、遮罩、滤镜、CSS 或外部资源 |

> 若 Logo 不符合要求，请先在 Illustrator、Figma 或 Inkscape 中展开轮廓与变换后再导出。

## 批量输入

### TXT

每行一个 `http://` 或 `https://` 链接。空行与以 `#` 开头的行会被忽略。

```text
https://example.com/a
https://example.com/b
```

```bash
python3 scripts/generate_qr_logo.py \
  --input /absolute/path/links.txt \
  --output /absolute/path/output
```

### CSV

CSV 可直接提供完整 `url`，也可以提供 `website` + UTM 字段；可选 `name` 用于控制文件名：

```csv
url,name
https://example.com/a,campaign-a
https://example.com/b,campaign-b
```

UTM 批量示例：

```csv
website,utm_source,utm_medium,name
www.fridayparts.com,abc,123,fridayparts-campaign
https://example.com/path,newsletter,email,email-campaign
```

## 完成标准

一批二维码只有在下列条件全部满足时才算完成：

- 每个唯一链接都有同名 SVG、PNG 和 TXT。
- TXT 内容与二维码实际编码的完整链接完全一致。
- `manifest.json` 中 `failed` 为 `0`。
- 默认验证模式下，每一项的 `verified` 都为 `true`。
- 导出 SVG 不包含位图，中心留白不会产生半像素框线。

<details>
<summary><strong>高级参数</strong></summary>

```text
--size 2048          修改 PNG 尺寸，SVG 始终保持矢量
--timeout 45         设置 HTTP 超时秒数
--retries 5          设置单次请求重试次数
--skip-verify        跳过远程解码，仅在明确接受未验证输出时使用
```

</details>

---

<a id="english"></a>

# English

QR Logo Export converts complete URLs, or a website plus UTM values, into branded QR codes. Each link produces a true-vector **SVG**, a `1080 x 1080` **PNG**, and a matching **TXT** containing the complete encoded URL. It preserves input order and records per-file scan verification.

> The bundled FP logo works out of the box. Replace one SVG asset to create your company's version.

## Output

| Output | Specification |
| --- | --- |
| SVG | True vector paths, no embedded bitmap, resolution independent |
| PNG | `1080 x 1080` pixels by default |
| TXT | Same basename as SVG/PNG; contains the exact URL encoded in the QR code |
| Logo | Centered, aspect ratio preserved, original fill colors retained |
| QR code | `#1A5FA9`, error correction H, four-module quiet zone |
| Verification | Every PNG is decoded remotely and must match its source URL exactly |

## Quick install

### 1. Requirements

- Codex desktop, Codex CLI, or the Codex IDE extension
- Python 3
- [Pillow](https://pypi.org/project/pillow/)

```bash
python3 -m pip install Pillow
```

### 2. Install the Skill

**From GitHub (recommended)**

```text
$skill-installer

Install this Skill:
https://github.com/J-SanTu/qr-logo-export
```

**Manual installation**

Copy the complete `qr-logo-export` folder to:

```text
~/.agents/skills/qr-logo-export/
```

Confirm that `~/.agents/skills/qr-logo-export/SKILL.md` exists. Restart Codex if the Skill does not appear immediately.

## First batch in 30 seconds

Prompt Codex with:

```text
Use $qr-logo-export to convert these links in order into SVG, PNG, and URL TXT files with the company logo:
https://example.com/a
https://example.com/b
```

Codex preserves link order, creates matching `.svg` / `.png` / `.txt` files, and writes `manifest.csv` plus `manifest.json`.

## Website + UTM values

When given a website, `utm_source`, and `utm_medium`, the Skill builds the complete URL before encoding it into the QR code and writing the matching TXT file.

Input:

```text
website: www.fridayparts.com
source: abc
medium: 123
```

Result:

```text
https://www.fridayparts.com/?utm_source=abc&utm_medium=123
```

CLI example:

```bash
python3 scripts/generate_qr_logo.py \
  --website 'www.fridayparts.com' \
  --utm-source 'abc' \
  --utm-medium '123' \
  --output /absolute/path/output
```

For `utm_source`, the aliases `utm_sourse`, `source`, and `sourse` are accepted. For `utm_medium`, `medium` is accepted. Missing schemes default to `https://`; unrelated existing query parameters are preserved; existing UTM values are replaced; parameter values are URL-encoded.

## Replace the company logo

### Option A: replace the default permanently

1. Prepare the company logo as an SVG.
2. Convert text and strokes to outlines, then expand groups and transforms.
3. Keep a numeric `viewBox` and filled `<path>` elements only.
4. Replace [`assets/fp-logo.svg`](./assets/fp-logo.svg) without changing the filename.
5. Generate one test QR code and verify its appearance and scan result.

### Option B: select a logo for one run

```bash
python3 scripts/generate_qr_logo.py \
  --logo /absolute/path/company-logo.svg \
  --input /absolute/path/links.txt \
  --output /absolute/path/output
```

### Logo SVG requirements

| Supported | Not supported |
| --- | --- |
| Transparent-background, true-vector SVG | Embedded PNG / JPG |
| Numeric `viewBox` | `<text>` elements |
| Absolute `M/L/H/V/C/Z` path commands | Groups, transforms, or strokes |
| Fill colors directly on each `<path>` | Clipping, masks, filters, CSS, or external resources |

> If the logo does not meet these requirements, expand outlines and transforms in Illustrator, Figma, or Inkscape before exporting it again.

## Batch input

### TXT

Use one `http://` or `https://` URL per line. Blank lines and lines beginning with `#` are ignored.

```text
https://example.com/a
https://example.com/b
```

```bash
python3 scripts/generate_qr_logo.py \
  --input /absolute/path/links.txt \
  --output /absolute/path/output
```

### CSV

CSV may contain a complete `url`, or a `website` plus UTM fields. The optional `name` column controls the output basename:

```csv
url,name
https://example.com/a,campaign-a
https://example.com/b,campaign-b
```

Structured UTM input:

```csv
website,utm_source,utm_medium,name
www.fridayparts.com,abc,123,fridayparts-campaign
https://example.com/path,newsletter,email,email-campaign
```

## Completion criteria

A batch is complete only when:

- Every unique URL has a matching SVG, PNG, and TXT.
- TXT content exactly matches the complete URL encoded in the QR code.
- `failed` is `0` in `manifest.json`.
- Every item has `verified: true` when default verification is enabled.
- Exported SVG files contain no bitmap, and the module-aligned center cutout has no half-pixel frame.

<details>
<summary><strong>Advanced options</strong></summary>

```text
--size 2048          Change PNG dimensions; SVG remains vector
--timeout 45         Set the HTTP timeout in seconds
--retries 5          Set attempts per HTTP request
--skip-verify        Skip remote decoding only when unverified output is explicitly acceptable
```

</details>

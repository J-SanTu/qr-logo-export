#!/usr/bin/env python3
"""Generate ordered SVG + PNG + URL text batches of branded QR codes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageColor, ImageDraw
except ImportError as exc:
    raise SystemExit("Pillow is required: install it with `python3 -m pip install Pillow`.") from exc

try:
    import certifi
except ImportError:
    certifi = None


CREATE_ENDPOINT = "https://api.2dcode.biz/v1/create-qr-code"
DECODE_ENDPOINT = "https://api.2dcode.biz/v1/read-qr-code"
QR_COLOR = "#1A5FA9"
CANVAS = 540.0
SAFE_BOX = 156.0
LOGO_MAX_SIZE = 126.442
DEFAULT_SIZE = 1080
USER_AGENT = "qr-logo-export/1.0"
TLS_CONTEXT = ssl.create_default_context(cafile=certifi.where() if certifi else None)
DEFAULT_LOGO = Path(__file__).resolve().parents[1] / "assets" / "santu-logo.svg"

MODULE_RE = re.compile(
    r"M(?P<x1>-?[\d.]+),(?P<y1>-?[\d.]+)"
    r"H(?P<x2>-?[\d.]+)V(?P<y2>-?[\d.]+)H(?P<x3>-?[\d.]+)z",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"[A-Za-z]|-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


@dataclass(frozen=True)
class InputItem:
    url: str
    name: str = ""


@dataclass(frozen=True)
class LogoPath:
    data: str
    fill: str
    fill_rule: str


@dataclass(frozen=True)
class LogoAsset:
    source: Path
    view_box: tuple[float, float, float, float]
    paths: tuple[LogoPath, ...]


@dataclass
class Result:
    index: int
    url: str
    name: str
    svg: str = ""
    png: str = ""
    url_text: str = ""
    svg_sha256: str = ""
    png_sha256: str = ""
    url_text_sha256: str = ""
    verified: bool = False
    status: str = "failed"
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-generate branded QR codes as matching SVG, PNG, and URL text files."
    )
    parser.add_argument("urls", nargs="*", help="HTTP(S) links in output order")
    parser.add_argument("--input", type=Path, help="UTF-8 TXT or CSV input file")
    parser.add_argument("--website", help="Website to combine with UTM source and medium")
    parser.add_argument(
        "--utm-source", "--utm-sourse", "--source", "--sourse", dest="utm_source",
        help="utm_source value (source, utm_sourse, and sourse are accepted)",
    )
    parser.add_argument(
        "--utm-medium", "--medium", dest="utm_medium", help="utm_medium value"
    )
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument(
        "--logo",
        type=Path,
        default=DEFAULT_LOGO,
        help="Path-only SVG logo (default: assets/santu-logo.svg)",
    )
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE, help="PNG width/height")
    parser.add_argument("--skip-verify", action="store_true", help="Skip remote scan verification")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=3, help="HTTP attempts per request")
    args = parser.parse_args()
    structured_values = (args.website, args.utm_source, args.utm_medium)
    if any(structured_values) and not all(structured_values):
        parser.error("--website, --utm-source, and --utm-medium must be provided together")
    if args.website and (args.input or args.urls):
        parser.error("--website cannot be combined with --input or positional URLs")
    if not args.input and not args.urls and not args.website:
        parser.error("provide --input, --website with UTM values, or at least one URL")
    if args.size < 256 or args.size > 8192:
        parser.error("--size must be between 256 and 8192")
    if args.retries < 1 or args.retries > 10:
        parser.error("--retries must be between 1 and 10")
    return args


def load_logo(path: Path) -> LogoAsset:
    source = path.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"logo file not found: {source}")
    try:
        root = ET.fromstring(source.read_bytes())
    except ET.ParseError as exc:
        raise ValueError(f"logo is not valid SVG: {source}") from exc
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("logo root element must be <svg>")
    try:
        view_box = tuple(float(value) for value in root.attrib["viewBox"].replace(",", " ").split())
    except (KeyError, ValueError) as exc:
        raise ValueError("logo SVG must have a numeric viewBox") from exc
    if len(view_box) != 4 or view_box[2] <= 0 or view_box[3] <= 0:
        raise ValueError("logo SVG viewBox must contain four values with positive width and height")

    paths: list[LogoPath] = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "svg":
            continue
        if tag != "path":
            raise ValueError(
                f"unsupported logo element <{tag}>; use path-only SVG without groups, text, images, or clipping"
            )
        unsupported = set(node.attrib) & {
            "class", "clip-path", "filter", "mask", "stroke", "style", "transform"
        }
        if unsupported:
            raise ValueError(
                "unsupported logo path attribute(s): " + ", ".join(sorted(unsupported))
            )
        data = node.attrib.get("d", "").strip()
        if not data:
            raise ValueError("every logo path must have non-empty d data")
        commands = [token for token in TOKEN_RE.findall(data) if token.isalpha()]
        unsupported_commands = sorted(set(commands) - {"M", "L", "H", "V", "C", "Z"})
        if unsupported_commands:
            raise ValueError(
                "logo paths must use absolute M/L/H/V/C/Z commands; unsupported: "
                + ", ".join(unsupported_commands)
            )
        fill = node.attrib.get("fill", "#000000")
        if fill.lower() == "none":
            continue
        try:
            ImageColor.getrgb(fill)
        except ValueError as exc:
            raise ValueError(f"unsupported logo fill color: {fill}") from exc
        fill_rule = node.attrib.get("fill-rule", "nonzero").lower()
        if fill_rule not in {"evenodd", "nonzero"}:
            raise ValueError(f"unsupported logo fill-rule: {fill_rule}")
        paths.append(LogoPath(data=data, fill=fill, fill_rule=fill_rule))
    if not paths:
        raise ValueError("logo SVG contains no visible paths")
    return LogoAsset(source=source, view_box=view_box, paths=tuple(paths))


def build_utm_url(website: str, source: str, medium: str) -> str:
    website = website.strip()
    source = source.strip()
    medium = medium.strip()
    if not website:
        raise ValueError("website cannot be empty")
    if not source or not medium:
        raise ValueError("utm_source and utm_medium cannot be empty")
    if "://" not in website:
        website = "https://" + website
    parsed = urllib.parse.urlsplit(website)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"not a valid website: {website}")
    query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key not in {"utm_source", "utm_medium"}
    ]
    query.extend((("utm_source", source), ("utm_medium", medium)))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path or "/", urllib.parse.urlencode(query), parsed.fragment)
    )


def first_value(row: dict[str, str | None], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value and value.strip():
            return value.strip()
    return ""


def read_items(
    path: Path | None,
    urls: list[str],
    website: str | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
) -> list[InputItem]:
    raw: list[InputItem] = []
    if path:
        if not path.is_file():
            raise ValueError(f"input file not found: {path}")
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    raise ValueError("CSV input must contain headers")
                reader.fieldnames = [field.strip().lower() for field in reader.fieldnames]
                if not {"url", "website", "网址"}.intersection(reader.fieldnames):
                    raise ValueError("CSV input must contain a 'url', 'website', or '网址' header")
                for row_number, row in enumerate(reader, start=2):
                    base = first_value(row, "url", "website", "网址")
                    source = first_value(row, "utm_source", "utm_sourse", "source", "sourse")
                    medium = first_value(row, "utm_medium", "medium")
                    name = first_value(row, "name")
                    if not base and not source and not medium:
                        continue
                    if not base:
                        raise ValueError(f"CSV row {row_number} has UTM values but no website")
                    if source or medium:
                        if not source or not medium:
                            raise ValueError(
                                f"CSV row {row_number} must provide both utm_source and utm_medium"
                            )
                        base = build_utm_url(base, source, medium)
                    raw.append(InputItem(url=base, name=name))
        else:
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                value = line.strip()
                if value and not value.startswith("#"):
                    raw.append(InputItem(url=value))
    raw.extend(InputItem(url=value.strip()) for value in urls if value.strip())
    if website is not None and utm_source is not None and utm_medium is not None:
        raw.append(InputItem(url=build_utm_url(website, utm_source, utm_medium)))

    seen: set[str] = set()
    items: list[InputItem] = []
    for item in raw:
        parsed = urllib.parse.urlsplit(item.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"not an HTTP(S) URL: {item.url}")
        if item.url not in seen:
            seen.add(item.url)
            items.append(item)
    if not items:
        raise ValueError("input contains no URLs")
    return items


def request_bytes(request: urllib.request.Request, timeout: float, retries: int) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=TLS_CONTEXT) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                return response.read()
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * (2 ** (attempt - 1)))
    raise RuntimeError(f"request failed after {retries} attempt(s): {last_error}")


def fetch_matrix(url: str, timeout: float, retries: int) -> tuple[float, str, list[tuple[float, float, float, float]]]:
    query = urllib.parse.urlencode(
        {"data": url, "format": "svg", "error_correction": "H", "border": "4"}
    )
    request = urllib.request.Request(f"{CREATE_ENDPOINT}?{query}", headers={"User-Agent": USER_AGENT})
    payload = request_bytes(request, timeout, retries)
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RuntimeError("create endpoint did not return valid SVG") from exc
    view_box = root.attrib.get("viewBox", "").split()
    if len(view_box) != 4 or view_box[0:2] != ["0", "0"] or view_box[2] != view_box[3]:
        raise RuntimeError(f"unsupported SVG viewBox: {root.attrib.get('viewBox')!r}")
    matrix_size = float(view_box[2])
    qr_path = next((node for node in root.iter() if node.attrib.get("id") == "qr-path"), None)
    if qr_path is None or not qr_path.attrib.get("d"):
        raise RuntimeError("SVG response has no qr-path")
    path_data = qr_path.attrib["d"]
    modules: list[tuple[float, float, float, float]] = []
    for match in MODULE_RE.finditer(path_data):
        x1, y1, x2, y2 = (float(match.group(key)) for key in ("x1", "y1", "x2", "y2"))
        modules.append((x1, y1, x2, y2))
    if not modules:
        raise RuntimeError("SVG qr-path module representation changed")
    return matrix_size, path_data, modules


def center_cutout(
    matrix_size: float,
    modules: list[tuple[float, float, float, float]],
) -> tuple[int, int, list[tuple[float, float, float, float]]]:
    matrix_modules = round(matrix_size)
    if not math.isclose(matrix_size, matrix_modules) or matrix_modules % 2 == 0:
        raise RuntimeError(f"unsupported QR matrix size: {matrix_size:g}")

    minimum_modules = math.ceil(matrix_modules * SAFE_BOX / CANVAS)
    cutout_modules = minimum_modules if minimum_modules % 2 == 1 else minimum_modules + 1
    cutout_min = (matrix_modules - cutout_modules) // 2
    cutout_max = cutout_min + cutout_modules
    if cutout_min < 4 or cutout_max > matrix_modules - 4:
        raise RuntimeError("center cutout would overlap the QR quiet zone")

    visible_modules = [
        module
        for module in modules
        if not (
            module[0] >= cutout_min
            and module[2] <= cutout_max
            and module[1] >= cutout_min
            and module[3] <= cutout_max
        )
    ]
    return cutout_min, cutout_max, visible_modules


def modules_to_path(modules: list[tuple[float, float, float, float]]) -> str:
    return "".join(
        f"M{x1:g},{y1:g}H{x2:g}V{y2:g}H{x1:g}z" for x1, y1, x2, y2 in modules
    )


def compose_svg(
    matrix_size: float,
    modules: list[tuple[float, float, float, float]],
    cutout_min: int,
    cutout_max: int,
    logo: LogoAsset,
) -> str:
    min_x, min_y, logo_width, logo_height = logo.view_box
    fit_scale = LOGO_MAX_SIZE / max(logo_width, logo_height)
    display_width = logo_width * fit_scale
    display_height = logo_height * fit_scale
    logo_x = (CANVAS - display_width) / 2
    logo_y = (CANVAS - display_height) / 2
    scale = CANVAS / matrix_size
    qr_path = modules_to_path(modules)
    logo_paths = "\n".join(
        f'      <path d="{html.escape(path.data, quote=True)}" fill="{html.escape(path.fill, quote=True)}" fill-rule="{path.fill_rule}"/>'
        for path in logo.paths
    )
    return f'''<svg width="{int(CANVAS)}" height="{int(CANVAS)}" viewBox="0 0 {int(CANVAS)} {int(CANVAS)}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="{int(CANVAS)}" height="{int(CANVAS)}" fill="white"/>
  <path id="qr-modules" d="{qr_path}" fill="{QR_COLOR}" shape-rendering="crispEdges" transform="scale({scale:.12g})"/>
  <metadata data-center-cutout="{cutout_min}:{cutout_max}"/>
  <svg id="center-logo" x="{logo_x:.6g}" y="{logo_y:.6g}" width="{display_width:.6g}" height="{display_height:.6g}" viewBox="{min_x:g} {min_y:g} {logo_width:g} {logo_height:g}" preserveAspectRatio="xMidYMid meet">
{logo_paths}
  </svg>
</svg>
'''


def svg_path_polygons(path: str, curve_steps: int = 24) -> list[list[tuple[float, float]]]:
    tokens = TOKEN_RE.findall(path)
    polygons: list[list[tuple[float, float]]] = []
    points: list[tuple[float, float]] = []
    cursor = (0.0, 0.0)
    command = ""
    index = 0

    def number() -> float:
        nonlocal index
        value = float(tokens[index])
        index += 1
        return value

    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index].upper()
            index += 1
        if command == "M":
            cursor = (number(), number())
            if points:
                polygons.append(points)
            points = [cursor]
            command = "L"
        elif command == "L":
            cursor = (number(), number())
            points.append(cursor)
        elif command == "H":
            cursor = (number(), cursor[1])
            points.append(cursor)
        elif command == "V":
            cursor = (cursor[0], number())
            points.append(cursor)
        elif command == "C":
            start = cursor
            c1 = (number(), number())
            c2 = (number(), number())
            end = (number(), number())
            for step in range(1, curve_steps + 1):
                t = step / curve_steps
                inv = 1.0 - t
                x = inv**3 * start[0] + 3 * inv**2 * t * c1[0] + 3 * inv * t**2 * c2[0] + t**3 * end[0]
                y = inv**3 * start[1] + 3 * inv**2 * t * c1[1] + 3 * inv * t**2 * c2[1] + t**3 * end[1]
                points.append((x, y))
            cursor = end
        elif command == "Z":
            if points:
                polygons.append(points)
                points = []
            command = ""
        else:
            raise RuntimeError(f"unsupported logo SVG command: {command}")
    if points:
        polygons.append(points)
    return polygons


def polygon_area(points: list[tuple[float, float]]) -> float:
    return sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
    ) / 2


def render_logo(logo_asset: LogoAsset, pixel_size: int) -> Image.Image:
    supersample = 4
    target = max(1, pixel_size)
    work_size = target * supersample
    min_x, min_y, width, height = logo_asset.view_box
    factor = work_size / max(width, height)
    offset_x = (work_size - width * factor) / 2 - min_x * factor
    offset_y = (work_size - height * factor) / 2 - min_y * factor
    logo = Image.new("RGBA", (work_size, work_size), (255, 255, 255, 0))
    for logo_path in logo_asset.paths:
        polygons = svg_path_polygons(logo_path.data)
        if not polygons:
            continue
        mask = Image.new("1", (work_size, work_size), 0)
        dominant_sign = 1 if polygon_area(max(polygons, key=lambda points: abs(polygon_area(points)))) >= 0 else -1
        for polygon in polygons:
            points = [
                (x * factor + offset_x, y * factor + offset_y) for x, y in polygon
            ]
            polygon_mask = Image.new("1", (work_size, work_size), 0)
            ImageDraw.Draw(polygon_mask).polygon(points, fill=1)
            if logo_path.fill_rule == "evenodd":
                mask = ImageChops.logical_xor(mask, polygon_mask)
            elif (1 if polygon_area(polygon) >= 0 else -1) == dominant_sign:
                mask = ImageChops.lighter(mask, polygon_mask)
            else:
                mask = ImageChops.subtract(mask, polygon_mask)
        color = ImageColor.getrgb(logo_path.fill)
        rgba = (*color, 255) if len(color) == 3 else color
        layer = Image.new("RGBA", (work_size, work_size), rgba)
        logo.alpha_composite(Image.composite(layer, Image.new("RGBA", logo.size), mask))
    return logo.resize((target, target), Image.Resampling.LANCZOS)


def render_png(
    matrix_size: float,
    modules: list[tuple[float, float, float, float]],
    size: int,
    logo_asset: LogoAsset,
) -> Image.Image:
    image = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(image)
    for x1, y1, x2, y2 in modules:
        left = math.floor(x1 * size / matrix_size)
        top = math.floor(y1 * size / matrix_size)
        right = math.ceil(x2 * size / matrix_size) - 1
        bottom = math.ceil(y2 * size / matrix_size) - 1
        draw.rectangle((left, top, right, bottom), fill=QR_COLOR)

    logo_size = round(size * LOGO_MAX_SIZE / CANVAS)
    logo_left = (size - logo_size) // 2
    logo = render_logo(logo_asset, logo_size)
    image.paste(logo, (logo_left, logo_left), logo)
    return image


def verify_png(path: Path, expected: str, timeout: float, retries: int) -> tuple[bool, list[str]]:
    boundary = f"----fpqr{uuid.uuid4().hex}"
    file_bytes = path.read_bytes()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="qrcode.png"\r\n',
            b"Content-Type: image/png\r\n\r\n",
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        DECODE_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "User-Agent": USER_AGENT,
        },
    )
    payload = request_bytes(request, timeout, retries)
    try:
        response = json.loads(payload)
        contents = response.get("data", {}).get("contents", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        raise RuntimeError("decode endpoint returned invalid JSON") from exc
    if response.get("code") != 0 or not isinstance(contents, list):
        raise RuntimeError(f"decode endpoint rejected image: {response!r}")
    return expected in contents, [str(value) for value in contents]


def slug_for(item: InputItem) -> str:
    if item.name:
        candidate = item.name
    else:
        parsed = urllib.parse.urlsplit(item.url)
        path_bits = [part for part in parsed.path.split("/") if part]
        candidate = "-".join([parsed.hostname or "link", *path_bits[-2:]])
    candidate = unicodedata.normalize("NFKC", urllib.parse.unquote(candidate)).strip()
    candidate = re.sub(r"[^\w.-]+", "-", candidate, flags=re.UNICODE).strip("-._")
    return candidate[:72] or "link"


def unique_basename(index: int, item: InputItem, used: set[str]) -> str:
    root = f"{index:03d}-{slug_for(item)}"
    candidate = root
    suffix = 2
    while candidate.casefold() in used:
        candidate = f"{root}-{suffix}"
        suffix += 1
    used.add(candidate.casefold())
    return candidate


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifests(
    output: Path,
    results: list[Result],
    verify_enabled: bool,
    size: int,
    logo: LogoAsset,
) -> None:
    fields = list(asdict(results[0]).keys()) if results else list(Result.__dataclass_fields__.keys())
    with (output / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(result) for result in results)
    manifest = {
        "specification": {
            "qr_color": QR_COLOR,
            "logo_file": logo.source.name,
            "logo_sha256": sha256(logo.source),
            "error_correction": "H",
            "border_modules": 4,
            "png_size": size,
            "formats": ["svg", "png", "txt"],
            "verification_enabled": verify_enabled,
        },
        "summary": {
            "total": len(results),
            "succeeded": sum(result.status == "ok" for result in results),
            "failed": sum(result.status != "ok" for result in results),
        },
        "items": [asdict(result) for result in results],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    try:
        items = read_items(
            args.input, args.urls, args.website, args.utm_source, args.utm_medium
        )
        logo = load_logo(args.logo)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    if args.output.exists() and any(args.output.iterdir()):
        print(f"Output error: directory is not empty: {args.output}", file=sys.stderr)
        return 2
    args.output.mkdir(parents=True, exist_ok=True)
    results: list[Result] = []
    used_names: set[str] = set()
    width = max(3, len(str(len(items))))
    for position, item in enumerate(items, start=1):
        basename = unique_basename(position, item, used_names)
        if width > 3:
            basename = f"{position:0{width}d}-{basename.split('-', 1)[1]}"
        svg_path = args.output / f"{basename}.svg"
        png_path = args.output / f"{basename}.png"
        url_text_path = args.output / f"{basename}.txt"
        result = Result(index=position, url=item.url, name=item.name)
        print(f"[{position}/{len(items)}] {item.url}", flush=True)
        try:
            matrix_size, _, modules = fetch_matrix(item.url, args.timeout, args.retries)
            cutout_min, cutout_max, visible_modules = center_cutout(matrix_size, modules)
            svg_path.write_text(
                compose_svg(matrix_size, visible_modules, cutout_min, cutout_max, logo),
                encoding="utf-8",
            )
            render_png(matrix_size, visible_modules, args.size, logo).save(
                png_path, format="PNG", optimize=True
            )
            url_text_path.write_text(item.url + "\n", encoding="utf-8")
            result.svg = svg_path.name
            result.png = png_path.name
            result.url_text = url_text_path.name
            result.svg_sha256 = sha256(svg_path)
            result.png_sha256 = sha256(png_path)
            result.url_text_sha256 = sha256(url_text_path)
            if args.skip_verify:
                result.status = "ok"
            else:
                verified, decoded = verify_png(png_path, item.url, args.timeout, args.retries)
                result.verified = verified
                if not verified:
                    raise RuntimeError(f"scan mismatch; decoded={decoded!r}")
                result.status = "ok"
        except (OSError, RuntimeError, ValueError) as exc:
            result.error = str(exc)
            print(f"  FAILED: {exc}", file=sys.stderr, flush=True)
        results.append(result)
        write_manifests(args.output, results, not args.skip_verify, args.size, logo)

    succeeded = sum(result.status == "ok" for result in results)
    failed = len(results) - succeeded
    print(f"Completed: {succeeded} succeeded, {failed} failed. Output: {args.output.resolve()}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

/**
 * Lightweight, client-side "preview" badges for non-media (Other) assets.
 *
 * Instead of fetching or generating a thumbnail, we render a small inline SVG
 * data URL showing the file extension on a category-colored tile. Badges are
 * deterministic and memoized by extension, so rendering is constant-time with
 * zero network requests — fast for search result grids.
 */

type ContentCategory = "document" | "data" | "archive" | "code" | "other";

/** Maps an extension to a coarse content category (mirrors the backend). */
const EXT_CATEGORY: Record<string, ContentCategory> = {
  // documents
  pdf: "document",
  doc: "document",
  docx: "document",
  txt: "document",
  rtf: "document",
  odt: "document",
  md: "document",
  ppt: "document",
  pptx: "document",
  xls: "document",
  xlsx: "document",
  pages: "document",
  // structured data
  csv: "data",
  json: "data",
  xml: "data",
  yaml: "data",
  yml: "data",
  tsv: "data",
  parquet: "data",
  // archives
  zip: "archive",
  tar: "archive",
  gz: "archive",
  tgz: "archive",
  rar: "archive",
  "7z": "archive",
  bz2: "archive",
  // code / text
  py: "code",
  js: "code",
  ts: "code",
  tsx: "code",
  jsx: "code",
  java: "code",
  c: "code",
  cpp: "code",
  h: "code",
  hpp: "code",
  go: "code",
  rs: "code",
  rb: "code",
  sh: "code",
  html: "code",
  css: "code",
  sql: "code",
};

/** Background / text colors per category. */
const CATEGORY_STYLE: Record<ContentCategory, { bg: string; fg: string }> = {
  document: { bg: "#1565C0", fg: "#FFFFFF" },
  data: { bg: "#2E7D32", fg: "#FFFFFF" },
  archive: { bg: "#6A1B9A", fg: "#FFFFFF" },
  code: { bg: "#37474F", fg: "#FFFFFF" },
  other: { bg: "#546E7A", fg: "#FFFFFF" },
};

/** Extract a lowercase extension (no dot) from a filename or bare extension. */
export function extractExtension(nameOrExt: string): string {
  if (!nameOrExt) return "";
  const cleaned = nameOrExt.trim().toLowerCase();
  const lastDot = cleaned.lastIndexOf(".");
  const ext = lastDot >= 0 ? cleaned.slice(lastDot + 1) : cleaned;
  // Guard against paths or query strings sneaking in.
  return /^[a-z0-9]+$/.test(ext) ? ext : "";
}

export function getContentCategory(ext: string): ContentCategory {
  return EXT_CATEGORY[ext] ?? "other";
}

const badgeCache = new Map<string, string>();

/**
 * Returns a memoized inline-SVG data URL badge for a file's extension.
 * Pass the filename (preferred) or a bare extension. Optionally pass a
 * backend-provided content category to override the client-side derivation.
 */
export function getExtensionBadge(nameOrExt: string, category?: string): string {
  const ext = extractExtension(nameOrExt);
  const resolvedCategory = (
    category && category in CATEGORY_STYLE ? category : getContentCategory(ext)
  ) as ContentCategory;
  const cacheKey = `${ext || "file"}:${resolvedCategory}`;

  const cached = badgeCache.get(cacheKey);
  if (cached) return cached;

  const style = CATEGORY_STYLE[resolvedCategory];
  const label = (ext ? ext.toUpperCase() : "FILE").slice(0, 5);
  const fontSize = label.length > 4 ? 42 : 56;

  const svg = `<svg width="300" height="200" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="${style.bg}"/>
  <rect x="108" y="44" width="84" height="104" rx="8" fill="${style.fg}" opacity="0.16"/>
  <text x="50%" y="52%" font-family="Arial, sans-serif" font-size="${fontSize}" font-weight="700" fill="${
    style.fg
  }" text-anchor="middle" dominant-baseline="middle">${label}</text>
  <text x="50%" y="80%" font-family="Arial, sans-serif" font-size="18" font-weight="500" fill="${
    style.fg
  }" opacity="0.85" text-anchor="middle" dominant-baseline="middle">${resolvedCategory.toUpperCase()}</text>
</svg>`;

  const url = `data:image/svg+xml;base64,${btoa(svg)}`;
  badgeCache.set(cacheKey, url);
  return url;
}

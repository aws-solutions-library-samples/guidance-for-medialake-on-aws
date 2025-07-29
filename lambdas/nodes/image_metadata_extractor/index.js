const AWS = require("aws-sdk");
const s3 = new AWS.S3();
const dynamoDB = new AWS.DynamoDB();
const exifr = require("exifr");
const xml2js = require("xml2js");
const { lambdaMiddleware } = require("./lambda_middleware");

const MEDIALAKE_ASSET_TABLE = process.env.MEDIALAKE_ASSET_TABLE;
const UNSUPPORTED_EXTENSIONS = [".webp"];

// ── Helpers ────────────────────────────────────────────────────────────────────

function sliceArray(arr, limit) {
  const size = Math.min(arr.length, limit);
  const values = arr.slice(0, size);
  return size < arr.length ? [values, arr.length - size] : [values, 0];
}

function formatBytes(arr) {
  return arr.map((v) => v.toString(16).padStart(2, "0")).join(" ");
}

function clipBytes(uint8arr, limit = 60) {
  const arr = Array.from(uint8arr);
  const [values, remain] = sliceArray(arr, limit);
  let out = formatBytes(values);
  if (remain > 0) out += `\n... and ${remain} more`;
  return out;
}

function clipString(str, limit = 300) {
  const arr = str.split("");
  const [values, remain] = sliceArray(arr, limit);
  let out = values.join("");
  if (remain > 0) out += `\n... and ${remain} more`;
  return out;
}

function prettyCase(key) {
  return key
    .match(/([A-Z]+(?=[A-Z][a-z]))|([A-Z][a-z]+)|([0-9]+)|([a-z]+)|([A-Z]+)/g)
    .map((s) => s[0].toUpperCase() + s.slice(1))
    .join(" ");
}

const convertFloatsToDecimals = (obj) => {
  if (obj == null || typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map(convertFloatsToDecimals);
  const res = {};
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === "number") res[k] = v.toString();
    else if (typeof v === "object") res[k] = convertFloatsToDecimals(v);
    else res[k] = v;
  }
  return res;
};

function normalizeDateString(str) {
  const m = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) {
    const [, y, mn, d] = m;
    return `${y}-${mn.padStart(2, "0")}-${d.padStart(2, "0")}`;
  }
  return str;
}

function normalizeDateTimeString(str) {
  const m = str.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{3})Z$/);
  if (m) {
    const [, date, hh, mm, ms] = m;
    return `${date}T${hh}:${mm}:00.${ms}Z`;
  }
  return str;
}

function sanitizeMetadata(obj) {
  if (obj == null || typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map(sanitizeMetadata);
  return Object.entries(obj).reduce((out, [k, v]) => {
    if (typeof v === "string") {
      if (!/^0000-00-00/.test(v)) {
        let s = normalizeDateString(v);
        s = normalizeDateTimeString(s);
        if (!isNaN(Date.parse(s))) {
          out[k] = s
            .replace(/[\u0000-\u001F\u007F-\u009F]/g, "")
            .replace(/[\\"']/g, "\\$&");
        }
      }
    } else if (v instanceof Uint8Array) {
      out[k] = clipBytes(v);
    } else {
      const nested = sanitizeMetadata(v);
      if (nested !== undefined) out[k] = nested;
    }
    return out;
  }, {});
}

function isLikelyBase64(str) {
  return (
    typeof str === "string" &&
    str.length > 100 &&
    /^[A-Za-z0-9+/]+={0,2}$/.test(str)
  );
}

function removeBase64Fields(obj) {
  if (Array.isArray(obj)) {
    const filtered = [];
    for (const item of obj) {
      if (isLikelyBase64(item)) continue;
      if (item && typeof item === "object") removeBase64Fields(item);
      filtered.push(item);
    }
    obj.length = 0;
    obj.push(...filtered);
  } else if (obj && typeof obj === "object") {
    for (const [key, val] of Object.entries(obj)) {
      if (
        isLikelyBase64(val) ||
        (Array.isArray(val) && val.every((el) => isLikelyBase64(el)))
      ) {
        delete obj[key];
      } else {
        removeBase64Fields(val);
      }
    }
  }
}

function forceAllObjects(x) {
  if (x == null || typeof x !== "object") return { value: x };
  if (Array.isArray(x)) return x.map(forceAllObjects);
  return Object.entries(x).reduce((out, [k, v]) => {
    out[k] = forceAllObjects(v);
    return out;
  }, {});
}

async function extractOrganizedMetadata(buffer) {
  const options = {
    tiff: true,
    exif: true,
    gps: true,
    xmp: true,
    interop: true,
    jfif: true,
    ihdr: true,
    mergeOutput: false,
    sanitize: true,
    reviveValues: true,
    translateKeys: true,
    translateValues: true,
    multiSegment: true,
  };
  const raw = await exifr.parse(buffer, options);
  return organizeMetadata(raw || {});
}

function organizeMetadata(raw) {
  const out = {};
  const seen = new Set();
  for (const [seg, data] of Object.entries(raw)) {
    if (seg === "errors") continue;
    if (data && typeof data === "object") {
      out[seg] = {};
      for (const [k, v] of Object.entries(data)) {
        if (!seen.has(k)) {
          const val =
            v instanceof Uint8Array
              ? clipBytes(v)
              : typeof v === "string"
                ? clipString(v)
                : v;
          out[seg][prettyCase(k)] = val;
          seen.add(k);
        }
      }
    } else {
      out[seg] = data;
    }
  }
  return out;
}

async function extractSvgMetadata(buffer) {
  try {
    const doc = await new xml2js.Parser({
      explicitArray: false,
    }).parseStringPromise(buffer);
    return doc.svg?.metadata || null;
  } catch {
    return null;
  }
}

// ─── EXIF & SVG pipeline ───────────────────────────────────────────────────────

async function processImageFile(bucket, key) {
  const ext = key.slice(key.lastIndexOf(".")).toLowerCase();
  if (UNSUPPORTED_EXTENSIONS.includes(ext)) {
    return { UnsupportedFormat: { Message: `${ext} not supported` } };
  }
  const { Body } = await s3.getObject({ Bucket: bucket, Key: key }).promise();
  if (ext === ".svg") {
    const svgMeta = await extractSvgMetadata(Body);
    return { SVGMetadata: svgMeta };
  }
  return extractOrganizedMetadata(Body);
}

// ─── Lambda handler for latest event shape ───────────────────────────────────
exports.lambda_handler = async (event) => {
  console.log("Received event:", JSON.stringify(event));

  const assets = event.payload?.assets;
  if (!Array.isArray(assets) || assets.length === 0) {
    throw new Error("Event.payload.assets must be a non-empty array");
  }

  const results = [];

  for (const asset of assets) {
    // ── 1) pull the ID ────────────────────────────────────────────────
    const inventoryId = asset.InventoryID;

    if (!inventoryId) {
      console.warn(
        "Skipping asset without InventoryID:",
        JSON.stringify(asset),
      );
      continue;
    }

    // ── 2) locate the object in S3 ────────────────────────────────────
    const loc =
      asset.DigitalSourceAsset?.MainRepresentation?.StorageInfo
        ?.PrimaryLocation;

    if (!loc?.Bucket || !loc.ObjectKey?.FullPath) {
      console.error(
        "Skipping asset with missing S3 location:",
        JSON.stringify(asset),
      );
      continue;
    }

    try {
      // ── 3) extract & clean metadata ────────────────────────────────
      const rawMeta = await processImageFile(
        loc.Bucket,
        loc.ObjectKey.FullPath,
      );
      let cleaned = sanitizeMetadata(rawMeta);
      removeBase64Fields(cleaned);

      const forced = forceAllObjects(cleaned);
      const converted = convertFloatsToDecimals(forced);
      const marshalled = AWS.DynamoDB.Converter.marshall(converted);

      // ── 4) append under the existing Metadata map ─────────────────
      await dynamoDB
        .updateItem({
          TableName: MEDIALAKE_ASSET_TABLE,
          Key: { InventoryID: { S: inventoryId } },
          UpdateExpression: "SET #M.#E = :m",
          ExpressionAttributeNames: {
            "#M": "Metadata",
            "#E": "EmbeddedMetadata",
          },
          ExpressionAttributeValues: {
            ":m": { M: marshalled },
          },
          ReturnValues: "UPDATED_NEW",
        })
        .promise();
      const updatedAsset = AWS.DynamoDB.Converter.unmarshall(getResp.Item);

      console.log(`Updated metadata for ${inventoryId}`);
      results.push({ inventoryId, status: "OK", updatedAsset });
    } catch (err) {
      console.error(`Error processing ${inventoryId}:`, err);
      results.push({ inventoryId, status: "ERROR", message: err.message });
    }
  }

  return {
    statusCode: 200,
    body: JSON.stringify({ results }),
  };
};

// ── Wrap with middleware ───────────────────────────────────────────────────────

const baseHandler = exports.lambda_handler;
exports.lambda_handler = lambdaMiddleware({
  eventBusName: process.env.EVENT_BUS_NAME || "default-event-bus",
  metricsNamespace: process.env.METRICS_NAMESPACE || "MediaLake",
  cleanupS3: true,
  largePayloadBucket: process.env.EXTERNAL_PAYLOAD_BUCKET,
  externalPayloadBucket: process.env.EXTERNAL_PAYLOAD_BUCKET,
  maxRetries: 3,
  standardizePayloads: true,
  maxResponseSize: 240 * 1024, // 240 KB
})(baseHandler);

const AWS     = require('aws-sdk');
const s3      = new AWS.S3();
const dynamo  = new AWS.DynamoDB();
const exifr   = require('exifr');
const xml2js  = require('xml2js');

const MEDIALAKE_ASSET_TABLE = process.env.MEDIALAKE_ASSET_TABLE;
const UNSUPPORTED_EXTENSIONS = ['.webp'];

// Slice and format helpers
function sliceArray(arr, limit) {
  const size = Math.min(arr.length, limit);
  const values = arr.slice(0, size);
  return size < arr.length ? [values, arr.length - size] : [values, 0];
}

function formatBytes(arr) {
  return arr.map(val => val.toString(16).padStart(2, '0')).join(' ');
}

// Clip for logging
function clipBytes(uint8arr, limit = 60) {
  const arr = Array.from(uint8arr);
  const [values, remaining] = sliceArray(arr, limit);
  let output = formatBytes(values);
  if (remaining > 0) output += `\n... and ${remaining} more`;
  return output;
}

function clipString(str, limit = 300) {
  const arr = str.split('');
  const [values, remaining] = sliceArray(arr, limit);
  let output = values.join('');
  if (remaining > 0) output += `\n... and ${remaining} more`;
  return output;
}

function prettyCase(string) {
  return string
    .match(/([A-Z]+(?=[A-Z][a-z]))|([A-Z][a-z]+)|([0-9]+)|([a-z]+)|([A-Z]+)/g)
    .map(s => s.charAt(0).toUpperCase() + s.slice(1))
    .join(' ');
}

const convertFloatsToDecimals = obj => {
  if (obj == null || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(convertFloatsToDecimals);
  const res = {};
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === 'number') res[k] = v.toString();
    else if (typeof v === 'object') res[k] = convertFloatsToDecimals(v);
    else res[k] = v;
  }
  return res;
};

// Normalize date-only strings to YYYY-MM-DD
function normalizeDateString(str) {
  const m = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) {
    const [, y, mn, d] = m;
    return `${y}-${mn.padStart(2, '0')}-${d.padStart(2, '0')}`;
  }
  return str;
}

// Normalize malformed ISO datetime like 2008-03-20T04:54:000Z → 2008-03-20T04:54:00.000Z
function normalizeDateTimeString(str) {
  const m = str.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{3})Z$/);
  if (m) {
    const [, date, hh, mm, ms] = m;
    return `${date}T${hh}:${mm}:00.${ms}Z`;
  }
  return str;
}

// Clean control chars, normalize dates, and drop invalid dates
function sanitizeMetadata(obj) {
  if (obj == null || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(sanitizeMetadata);
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === 'string') {
      // Drop placeholder zero dates
      if (/^0000-00-00/.test(v)) continue;
      // Normalize simple dates and malformed times
      let s = normalizeDateString(v);
      s = normalizeDateTimeString(s);
      // Validate final ISO date
      const parsed = Date.parse(s);
      if (!isNaN(parsed)) {
        out[k] = s.replace(/[\u0000-\u001F\u007F-\u009F]/g, '')
                   .replace(/[\\"']/g, '\\$&');
      } else {
        // If not a valid date, skip this field entirely
        continue;
      }
    } else if (v instanceof Uint8Array) {
      out[k] = clipBytes(v);
    } else {
      const nested = sanitizeMetadata(v);
      if (nested !== undefined) out[k] = nested;
    }
  }
  return out;
}

// Force every leaf node to be an object { value: ... }
function forceAllObjects(x) {
  if (x == null || typeof x !== 'object') return { value: x };
  if (Array.isArray(x)) return x.map(forceAllObjects);
  const out = {};
  for (const [k, v] of Object.entries(x)) {
    out[k] = forceAllObjects(v);
  }
  return out;
}

async function extractOrganizedMetadata(imageBuffer) {
  const options = {
    tiff: true, ifd0: true, exif: true, gps: true,
    interop: true, ifd1: true, makerNote: false, userComment: false,
    xmp: true, icc: true, iptc: true, jfif: true, ihdr: true,
    mergeOutput: false, sanitize: true, reviveValues: true,
    translateKeys: true, translateValues: true, multiSegment: true
  };
  const raw = await exifr.parse(imageBuffer, options);
  return organizeMetadata(raw || {});
}

function organizeMetadata(raw) {
  const out = {};
  const seen = new Set();
  for (const [segment, data] of Object.entries(raw)) {
    if (segment === 'errors') continue;
    if (data && typeof data === 'object') {
      out[segment] = {};
      for (const [k, v] of Object.entries(data)) {
        if (!seen.has(k)) {
          let val = v;
          if (v instanceof Uint8Array) val = clipBytes(v);
          else if (typeof v === 'string') val = clipString(v);
          out[segment][prettyCase(k)] = val;
          seen.add(k);
        }
      }
    } else {
      out[segment] = data;
    }
  }
  return out;
}

async function extractSvgMetadata(buffer) {
  const xml = buffer.toString('utf8');
  try {
    const doc = await new xml2js.Parser({ explicitArray: false }).parseStringPromise(xml);
    return { svgMetadata: doc.svg?.metadata || null };
  } catch {
    return null;
  }
}

async function processImageFile(bucket, key) {
  const ext = key.slice(key.lastIndexOf('.')).toLowerCase();
  if (UNSUPPORTED_EXTENSIONS.includes(ext)) {
    return { UnsupportedFormat: { Message: `${ext} not supported`, FileExtension: ext } };
  }
  const { Body } = await s3.getObject({ Bucket: bucket, Key: key }).promise();
  if (ext === '.svg') {
    const svg = await extractSvgMetadata(Body);
    return svg.svgMetadata ? { SVGMetadata: svg.svgMetadata } : { SVGMetadata: null };
  }
  return extractOrganizedMetadata(Body);
}

exports.lambda_handler = async (event) => {
  console.log(event);
  const inventoryId = event.input?.InventoryID;
  if (!inventoryId) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Missing InventoryID' }) };
  }

  const loc = event.input.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation;
  const rawMeta = await processImageFile(loc.Bucket, loc.ObjectKey.FullPath);
  const cleaned = sanitizeMetadata(rawMeta);
  const forced  = forceAllObjects(cleaned);

  const newMeta    = { CustomMetadata: forced };
  const marshalled = AWS.DynamoDB.Converter.marshall(convertFloatsToDecimals(newMeta));

  await dynamo.updateItem({
    TableName: MEDIALAKE_ASSET_TABLE,
    Key: { InventoryID: { S: inventoryId } },
    UpdateExpression: 'SET Metadata = :m',
    ExpressionAttributeValues: { ':m': { M: marshalled } }
  }).promise();

  return { statusCode: 200, body: JSON.stringify({ inventoryId }) };
};

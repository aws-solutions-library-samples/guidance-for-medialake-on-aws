const AWS     = require('aws-sdk');
const s3      = new AWS.S3();
const dynamo  = new AWS.DynamoDB();
const exifr   = require('exifr');
const xml2js  = require('xml2js');

const MEDIALAKE_ASSET_TABLE  = process.env.MEDIALAKE_ASSET_TABLE;
const UNSUPPORTED_EXTENSIONS = ['.webp'];

// ——— Helpers for clipping long byte arrays & strings ———

function sliceArray(arr, limit) {
  const size   = Math.min(arr.length, limit);
  const values = arr.slice(0, size);
  return size < arr.length ? [values, arr.length - size] : [values, 0];
}

function formatBytes(arr) {
  return arr.map(v => v.toString(16).padStart(2, '0')).join(' ');
}

function clipBytes(uint8arr, limit = 60) {
  const arr              = Array.from(uint8arr);
  const [values, remain] = sliceArray(arr, limit);
  let out               = formatBytes(values);
  if (remain > 0) out += `\n... and ${remain} more`;
  return out;
}

function clipString(str, limit = 300) {
  const arr              = str.split('');
  const [values, remain] = sliceArray(arr, limit);
  let out               = values.join('');
  if (remain > 0) out += `\n... and ${remain} more`;
  return out;
}

// ——— Case‑prettify & float→decimal helpers ———

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
    if (typeof v === 'number')      res[k] = v.toString();
    else if (typeof v === 'object') res[k] = convertFloatsToDecimals(v);
    else                             res[k] = v;
  }
  return res;
};

// ——— Date normalization ———

function normalizeDateString(str) {
  const m = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) {
    const [, y, mn, d] = m;
    return `${y}-${mn.padStart(2,'0')}-${d.padStart(2,'0')}`;
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

// ——— Metadata sanitization ———

function sanitizeMetadata(obj) {
  if (obj == null || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(sanitizeMetadata);
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === 'string') {
      if (/^0000-00-00/.test(v)) continue;  // drop placeholders
      let s = normalizeDateString(v);
      s     = normalizeDateTimeString(s);
      if (!isNaN(Date.parse(s))) {
        out[k] = s
          .replace(/[\u0000-\u001F\u007F-\u009F]/g, '')
          .replace(/[\\"']/g, '\\$&');
      }
      // otherwise skip non-date strings
    } else if (v instanceof Uint8Array) {
      out[k] = clipBytes(v);
    } else {
      const nested = sanitizeMetadata(v);
      if (nested !== undefined) out[k] = nested;
    }
  }
  return out;
}

// ——— Base64‑blob detection & removal ———

// Very long strings (>100 chars) of A–Z a–z 0–9 + /, optional = padding
function isLikelyBase64(str) {
  return (
    typeof str === 'string' &&
    str.length > 100 &&
    /^[A-Za-z0-9+/]+={0,2}$/.test(str)
  );
}

// Recursively remove any key whose value is base64‑blob or array of such blobs
function removeBase64Fields(obj) {
  if (Array.isArray(obj)) {
    // filter out base64 string items
    let filtered = [];
    for (const item of obj) {
      if (isLikelyBase64(item)) {
        continue;
      } else if (item && typeof item === 'object') {
        removeBase64Fields(item);
        filtered.push(item);
      } else {
        filtered.push(item);
      }
    }
    obj.length = 0;
    obj.push(...filtered);
  } else if (obj && typeof obj === 'object') {
    for (const [key, val] of Object.entries(obj)) {
      if (isLikelyBase64(val)) {
        delete obj[key];
      } else if (Array.isArray(val) && val.every(el => isLikelyBase64(el))) {
        delete obj[key];
      } else {
        removeBase64Fields(val);
      }
    }
  }
}

// ——— Force every leaf into { value: ... } ———

function forceAllObjects(x) {
  if (x == null || typeof x !== 'object') return { value: x };
  if (Array.isArray(x)) return x.map(forceAllObjects);
  const out = {};
  for (const [k, v] of Object.entries(x)) {
    out[k] = forceAllObjects(v);
  }
  return out;
}

// ——— EXIF & SVG extraction pipelines ———

async function extractOrganizedMetadata(buffer) {
  const options = {
    tiff: true, exif: true, gps: true, xmp: true,
    interop: true, jfif: true, ihdr: true,
    mergeOutput: false, sanitize: true, reviveValues: true,
    translateKeys: true, translateValues: true, multiSegment: true
  };
  const raw = await exifr.parse(buffer, options);
  return organizeMetadata(raw || {});
}

function organizeMetadata(raw) {
  const out  = {};
  const seen = new Set();
  for (const [segment, data] of Object.entries(raw)) {
    if (segment === 'errors') continue;
    if (data && typeof data === 'object') {
      out[segment] = {};
      for (const [k, v] of Object.entries(data)) {
        if (!seen.has(k)) {
          let val = v instanceof Uint8Array
                    ? clipBytes(v)
                    : typeof v === 'string'
                      ? clipString(v)
                      : v;
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
    const doc = await new xml2js.Parser({ explicitArray: false })
                               .parseStringPromise(xml);
    return doc.svg?.metadata || null;
  } catch {
    return null;
  }
}

async function processImageFile(bucket, key) {
  const ext = key.slice(key.lastIndexOf('.')).toLowerCase();
  if (UNSUPPORTED_EXTENSIONS.includes(ext)) {
    return { UnsupportedFormat: { Message: `${ext} not supported` } };
  }
  const { Body } = await s3.getObject({ Bucket: bucket, Key: key }).promise();
  if (ext === '.svg') {
    const svgMeta = await extractSvgMetadata(Body);
    return { SVGMetadata: svgMeta };
  }
  return extractOrganizedMetadata(Body);
}

// ——— Lambda handler ———

exports.lambda_handler = async (event) => {
  console.log('Received event:', JSON.stringify(event));

  const inventoryId = event.input?.InventoryID;
  if (!inventoryId) {
    throw new Error('Missing InventoryID');
  }

  const loc = event.input?.DigitalSourceAsset
             ?.MainRepresentation
             ?.StorageInfo
             ?.PrimaryLocation;
  if (!loc?.Bucket || !loc.ObjectKey?.FullPath) {
    throw new Error('Missing StorageInfo.PrimaryLocation');
  }

  try {
    const rawMeta = await processImageFile(loc.Bucket, loc.ObjectKey.FullPath);
    let cleaned   = sanitizeMetadata(rawMeta);

    // remove any deep‑nested base64 blobs
    removeBase64Fields(cleaned);

    const forced     = forceAllObjects(cleaned);
    const newMeta    = { CustomMetadata: forced };
    const converted  = convertFloatsToDecimals(newMeta);
    const marshalled = AWS.DynamoDB.Converter.marshall(converted);

    const updateParams = {
      TableName: MEDIALAKE_ASSET_TABLE,
      Key: { InventoryID: { S: inventoryId } },
      UpdateExpression: 'SET Metadata = :m',
      ExpressionAttributeValues: { ':m': { M: marshalled } }
    };

    try {
      await dynamo.updateItem(updateParams).promise();
    } catch (updateErr) {
      if (
        updateErr.code === 'ValidationException' &&
        /Item size has exceeded/.test(updateErr.message)
      ) {
        console.error(
          'Payload too large – dumping updateParams:',
          JSON.stringify(updateParams, null, 2)
        );
      }
      throw updateErr;
    }

    return { statusCode: 200, body: JSON.stringify({ inventoryId }) };

  } catch (err) {
    console.error('Processing failed for', inventoryId, err);
    throw err;
  }
};

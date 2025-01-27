const AWS = require('aws-sdk');
const s3 = new AWS.S3();
const dynamoDB = new AWS.DynamoDB();
const exifr = require('exifr');

const MEDIALAKE_ASSET_TABLE = process.env.MEDIALAKE_ASSET_TABLE;

// Utility functions
function clipBytes(uint8arr, limit = 60) {
    const arr = Array.from(uint8arr);
    const [values, remaining] = sliceArray(arr, limit);
    let output = formatBytes(values);
    if (remaining > 0) output += `\n... and ${remaining} more`;
    return output;
}

function clipString(string, limit = 300) {
    const arr = string.split('');
    const [values, remaining] = sliceArray(arr, limit);
    let output = values.join('');
    if (remaining > 0) output += `\n... and ${remaining} more`;
    return output;
}

function sliceArray(arr, limit) {
    const size = Math.min(arr.length, limit);
    const values = arr.slice(0, size);
    if (size < arr.length)
        return [values, arr.length - size];
    else
        return [values, 0];
}

function formatBytes(arr) {
    return arr
        .map(val => val.toString(16).padStart(2, '0'))
        .join(' ');
}

function prettyCase(string) {
    return string.match(/([A-Z]+(?=[A-Z][a-z]))|([A-Z][a-z]+)|([0-9]+)|([a-z]+)|([A-Z]+)/g)
        .map(s => s.charAt(0).toUpperCase() + s.slice(1))
        .join(' ');
}

const convertFloatsToDecimals = (obj) => {
    if (typeof obj !== 'object' || obj === null) return obj;
    if (Array.isArray(obj)) return obj.map(convertFloatsToDecimals);
    const result = {};
    for (const [key, value] of Object.entries(obj)) {
        if (typeof value === 'number') {
            result[key] = value.toString();
        } else if (typeof value === 'object') {
            result[key] = convertFloatsToDecimals(value);
        } else {
            result[key] = value;
        }
    }
    return result;
};

// const categoryMapping = {
//     exif: 'EXIF',
//     ifd1: 'Thumbnail (IFD1)',
//     ifd0: 'Image (IFD0)',
//     gps: 'GPS',
//     iptc: 'IPTC',
//     xmp: 'XMP',
//     icc: 'ICC',
//     jfif: 'JFIF (JPEG only)',
//     ihdr: 'IHDR (PNG only)',
//     makerNote: 'Maker Note',
//     userComment: 'User Comment',
//     xmpRights: 'Rights',
//     Iptc4xmpCore: 'IPTC Core',
//     Iptc4xmpExt: 'IPTC Extension',
//     photoshop: 'Photoshop',
//     plus: 'PLUS',
//     dc: 'Dublin Core',
//     xmpMM: 'XMP Media Management',
//     aux: 'Auxiliary',
//     crs: 'Camera Raw Settings',
//     exifEX: 'EXIF Extended',
//     xmpDM: 'XMP Dynamic Media',
//     interop: 'Interoperability'
// };

// function humanReadableCategory(category) {
//     return categoryMapping[category] || category;
// }


function humanReadableCategory(category) {
    return category;
}


async function extractOrganizedMetadata(imageBuffer) {
    const options = {
        // APP segments
        tiff: true,
        // TIFF blocks start
        ifd0: true,
        exif: true,
        gps: true,
        interop: true,
        ifd1: true,
        // other data
        makerNote: false,
        userComment: false,
        // TIFF blocks end
        xmp: true,
        icc: true,
        iptc: true,
        // JPEG only
        jfif: true,
        // PNG only
        ihdr: true,
        // output styles
        mergeOutput: false,
        sanitize: true,
        reviveValues: true,
        translateKeys: true,
        translateValues: true,
        // for XMP Extended
        multiSegment: true,
    };

    const rawMetadata = await exifr.parse(imageBuffer, options);
    return organizeMetadata(rawMetadata);
}



function organizeMetadata(rawMetadata) {
    const organizedMetadata = {};
    const seenKeys = new Set();

    for (const [segment, data] of Object.entries(rawMetadata)) {
        if (segment === 'errors') {
            console.error('Metadata extraction errors:', data);
            continue; // Skip adding errors to the organized metadata
        }

        const readableSegment = humanReadableCategory(segment);
        if (typeof data === 'object' && data !== null) {
            organizedMetadata[readableSegment] = {};
            for (const [key, value] of Object.entries(data)) {
                if (!seenKeys.has(key)) {
                    let processedValue = value;
                    if (value instanceof Uint8Array) {
                        processedValue = clipBytes(value);
                    } else if (typeof value === 'string') {
                        processedValue = clipString(value);
                    }
                    organizedMetadata[readableSegment][prettyCase(key)] = processedValue;
                    seenKeys.add(key);
                }
            }
        } else {
            organizedMetadata[readableSegment] = data;
        }
    }

    return organizedMetadata;
}


async function processImageFile(bucket, key) {
    try {
        const { Body: imageContent } = await s3.getObject({ Bucket: bucket, Key: key }).promise();
        console.log(`Retrieved image size: ${imageContent.length} bytes`);

        const metadata = await extractOrganizedMetadata(imageContent);
        if (!metadata) {
            throw new Error('Failed to extract metadata');
        }

        return metadata;
    } catch (error) {
        console.error('Error processing image file:', error);
        return null;
    }
}

function sanitizeMetadata(obj) {
    if (typeof obj !== 'object' || obj === null) return obj;
    if (Array.isArray(obj)) return obj.map(sanitizeMetadata);
    const result = {};
    for (const [key, value] of Object.entries(obj)) {
        if (typeof value === 'string') {
            // Remove control characters and escape special characters
            result[key] = value.replace(/[\u0000-\u001F\u007F-\u009F]/g, '')
                .replace(/[\\"']/g, '\\$&')
                .replace(/\u0000/g, '\\0');
        } else if (typeof value === 'object') {
            result[key] = sanitizeMetadata(value);
        } else {
            result[key] = value;
        }
    }
    return result;
}


exports.lambda_handler = async (event) => {
    console.log('Received event:', JSON.stringify(event));
    const { input } = event;
    const inventoryId = input?.InventoryID;
    const digitalSourceAsset = input?.DigitalSourceAsset;

    if (!inventoryId) {
        console.error('Invalid event format: missing InventoryID');
        return { statusCode: 400, body: 'Missing InventoryID' };
    }

    const bucket = digitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket;
    const key = digitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath;

    try {
        const extractedMetadata = await processImageFile(bucket, key);
        if (!extractedMetadata) {
            return { statusCode: 500, body: 'Failed to extract metadata' };
        }

        const sanitizedMetadata = sanitizeMetadata(extractedMetadata);
        const newCustomMetadata = { CustomMetadata: sanitizedMetadata };
        const convertedNewMetadata = convertFloatsToDecimals(newCustomMetadata);

        // Get existing item from DynamoDB
        const { Item: existingItem } = await dynamoDB.getItem({
            TableName: MEDIALAKE_ASSET_TABLE,
            Key: { InventoryID: { S: inventoryId } }
        }).promise();

        const existingMetadata = existingItem?.Metadata?.M || {};

        // Combine existing metadata with new CustomMetadata
        const updatedMetadata = {
            ...existingMetadata,
            ...AWS.DynamoDB.Converter.marshall(convertedNewMetadata)
        };

        // Update DynamoDB
        await dynamoDB.updateItem({
            TableName: MEDIALAKE_ASSET_TABLE,
            Key: { InventoryID: { S: inventoryId } },
            UpdateExpression: 'SET Metadata = :Metadata',
            ExpressionAttributeValues: {
                ':Metadata': { M: updatedMetadata }
            },
            ReturnValues: 'UPDATED_NEW'
        }).promise();

        console.log('Successfully updated DynamoDB item');

        return {
            statusCode: 200,
            body: JSON.stringify({
                inventoryId,
                message: 'Metadata extracted and stored successfully',
                metadata: sanitizedMetadata
            }, (key, value) => {
                if (typeof value === 'bigint') {
                    return value.toString();
                }
                return value;
            })
        };

    } catch (error) {
        console.error('Lambda handler error:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({
                error: 'Error extracting or storing image metadata',
                message: error.message
            })
        };
    }
};

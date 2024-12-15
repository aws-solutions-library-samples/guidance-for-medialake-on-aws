const AWS = require('aws-sdk');
const s3 = new AWS.S3();
const dynamoDB = new AWS.DynamoDB();
const exifr = require('exifr');

const MEDIALAKE_ASSET_TABLE = process.env.MEDIALAKE_ASSET_TABLE;

const convertFloatsToDecimals = (obj) => {
    if (typeof obj !== 'object' || obj === null) return obj;

    if (Array.isArray(obj)) {
        return obj.map(convertFloatsToDecimals);
    }

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

const categoryMapping = {
    xmpRights: 'Rights',
    Iptc4xmpCore: 'IPTC Core',
    iptc: 'IPTC',
    jfif: 'JFIF',
    Iptc4xmpExt: 'IPTC Extension',
    ifd0: 'Basic Image Information',
    photoshop: 'Photoshop',
    xmp: 'XMP',
    plus: 'PLUS',
    dc: 'Dublin Core',
    exif: 'EXIF'
};

function humanReadableCategory(category) {
    return categoryMapping[category] || category;
}

async function extractOrganizedMetadata(imageBuffer) {
    const options = {
        tiff: true,
        xmp: true,
        icc: true,
        iptc: true,
        jfif: true,
        ihdr: true,
        ifd0: true,
        ifd1: true,
        exif: true,
        gps: true,
        interop: true,
        makerNote: true,
        userComment: true,
        mergeOutput: false,
        translateKeys: true,
        translateValues: true,
        reviveValues: true,
    };

    const exr = new exifr.Exifr(options);
    await exr.read(imageBuffer);
    const rawMetadata = await exr.parse();

    return organizeMetadata(rawMetadata);
}

function organizeMetadata(rawMetadata) {
    const organizedMetadata = {};
    const seenKeys = new Set();

    for (const [segment, data] of Object.entries(rawMetadata)) {
        const readableSegment = humanReadableCategory(segment);
        if (typeof data === 'object' && data !== null) {
            organizedMetadata[readableSegment] = {};
            for (const [key, value] of Object.entries(data)) {
                if (!seenKeys.has(key)) {
                    organizedMetadata[readableSegment][key] = value;
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

        const newCustomMetadata = { CustomMetadata: extractedMetadata };
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
            body: { inventoryId }
        };

    } catch (error) {
        console.error('Lambda handler error:', error);
        return {
            statusCode: 500,
            body: `Error extracting image metadata: ${error.message}`
        };
    }
};

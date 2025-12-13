/**
 * Test Data Fixtures for Semantic Search E2E Tests
 *
 * Provides fixtures for managing test media assets (video, image, audio)
 * including S3 upload and cleanup functionality.
 *
 * @requirements 5.1, 5.2, 5.3, 5.4, 5.5
 *
 * **Feature: twelvelabs-marengo-3-0-playwright-tests**
 */

import { test as authTest } from "./auth.fixtures";
import {
  S3Client,
  PutObjectCommand,
  DeleteObjectCommand,
  ListObjectsV2Command,
} from "@aws-sdk/client-s3";
import * as crypto from "crypto";

const AWS_REGION = process.env.AWS_REGION || "us-east-1";

/**
 * Test media asset types
 */
export type MediaType = "video" | "image" | "audio";

/**
 * Test asset configuration
 */
export interface TestAsset {
  /** Unique identifier for the asset */
  id: string;
  /** Type of media asset */
  type: MediaType;
  /** Original filename */
  filename: string;
  /** S3 key where asset is uploaded */
  s3Key: string;
  /** S3 bucket name */
  bucket: string;
  /** File size in bytes */
  size: number;
  /** Content type (MIME type) */
  contentType: string;
}

/**
 * Test asset upload result
 */
export interface UploadResult {
  success: boolean;
  asset?: TestAsset;
  error?: string;
}

/**
 * Sample test files configuration
 * These are small test files that can be used for E2E testing
 */
export const SAMPLE_TEST_FILES = {
  video: {
    filename: "test-video.mp4",
    contentType: "video/mp4",
    // Small test video content (base64 encoded minimal MP4)
    // In production, this would be a real test video file
    generateContent: () => generateMinimalMp4(),
  },
  image: {
    filename: "test-image.jpg",
    contentType: "image/jpeg",
    // Small test image content
    generateContent: () => generateMinimalJpeg(),
  },
  audio: {
    filename: "test-audio.mp3",
    contentType: "audio/mpeg",
    // Small test audio content
    generateContent: () => generateMinimalMp3(),
  },
};

/**
 * Generate a minimal valid MP4 file for testing
 * This creates a tiny but valid MP4 container
 */
function generateMinimalMp4(): Buffer {
  // Minimal MP4 file structure (ftyp + moov boxes)
  // This is a valid but empty MP4 container
  const ftyp = Buffer.from([
    0x00,
    0x00,
    0x00,
    0x14, // size: 20 bytes
    0x66,
    0x74,
    0x79,
    0x70, // type: 'ftyp'
    0x69,
    0x73,
    0x6f,
    0x6d, // major_brand: 'isom'
    0x00,
    0x00,
    0x00,
    0x01, // minor_version: 1
    0x69,
    0x73,
    0x6f,
    0x6d, // compatible_brand: 'isom'
  ]);

  const moov = Buffer.from([
    0x00,
    0x00,
    0x00,
    0x08, // size: 8 bytes (minimal moov)
    0x6d,
    0x6f,
    0x6f,
    0x76, // type: 'moov'
  ]);

  return Buffer.concat([ftyp, moov]);
}

/**
 * Generate a minimal valid JPEG file for testing
 */
function generateMinimalJpeg(): Buffer {
  // Minimal 1x1 pixel JPEG
  return Buffer.from([
    0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
    0x00, 0x01, 0x00, 0x00, 0xff, 0xdb, 0x00, 0x43, 0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08,
    0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0a, 0x0c, 0x14, 0x0d, 0x0c, 0x0b, 0x0b, 0x0c, 0x19, 0x12,
    0x13, 0x0f, 0x14, 0x1d, 0x1a, 0x1f, 0x1e, 0x1d, 0x1a, 0x1c, 0x1c, 0x20, 0x24, 0x2e, 0x27, 0x20,
    0x22, 0x2c, 0x23, 0x1c, 0x1c, 0x28, 0x37, 0x29, 0x2c, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1f, 0x27,
    0x39, 0x3d, 0x38, 0x32, 0x3c, 0x2e, 0x33, 0x34, 0x32, 0xff, 0xc0, 0x00, 0x0b, 0x08, 0x00, 0x01,
    0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xff, 0xc4, 0x00, 0x1f, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01,
    0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04,
    0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0xff, 0xc4, 0x00, 0xb5, 0x10, 0x00, 0x02, 0x01, 0x03,
    0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7d, 0x01, 0x02, 0x03, 0x00,
    0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06, 0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32,
    0x81, 0x91, 0xa1, 0x08, 0x23, 0x42, 0xb1, 0xc1, 0x15, 0x52, 0xd1, 0xf0, 0x24, 0x33, 0x62, 0x72,
    0x82, 0x09, 0x0a, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x34, 0x35,
    0x36, 0x37, 0x38, 0x39, 0x3a, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4a, 0x53, 0x54, 0x55,
    0x56, 0x57, 0x58, 0x59, 0x5a, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6a, 0x73, 0x74, 0x75,
    0x76, 0x77, 0x78, 0x79, 0x7a, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8a, 0x92, 0x93, 0x94,
    0x95, 0x96, 0x97, 0x98, 0x99, 0x9a, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xb2,
    0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xc2, 0xc3, 0xc4, 0xc5, 0xc6, 0xc7, 0xc8, 0xc9,
    0xca, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xd9, 0xda, 0xe1, 0xe2, 0xe3, 0xe4, 0xe5, 0xe6,
    0xe7, 0xe8, 0xe9, 0xea, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8, 0xf9, 0xfa, 0xff, 0xda,
    0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3f, 0x00, 0xfb, 0xd5, 0xdb, 0x20, 0xa8, 0xf1, 0x5e, 0x5a,
    0x33, 0x8a, 0xc8, 0xaf, 0xff, 0xd9,
  ]);
}

/**
 * Generate a minimal valid MP3 file for testing
 */
function generateMinimalMp3(): Buffer {
  // Minimal MP3 file with ID3 header and one frame
  return Buffer.from([
    // ID3v2 header
    0x49,
    0x44,
    0x33, // 'ID3'
    0x04,
    0x00, // version 2.4.0
    0x00, // flags
    0x00,
    0x00,
    0x00,
    0x00, // size (0 bytes of ID3 data)
    // MP3 frame header (silent frame)
    0xff,
    0xfb,
    0x90,
    0x00, // MPEG Audio Layer 3, 128kbps, 44100Hz
    // Minimal frame data (silence)
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
  ]);
}

/**
 * Generate a unique asset ID
 */
function generateAssetId(): string {
  return `test-asset-${crypto.randomBytes(4).toString("hex")}`;
}

/**
 * Test data fixture types
 */
export type TestDataFixtures = {
  /** Upload a video file to S3 for testing */
  uploadTestVideo: (bucket: string, prefix?: string) => Promise<UploadResult>;
  /** Upload an image file to S3 for testing */
  uploadTestImage: (bucket: string, prefix?: string) => Promise<UploadResult>;
  /** Upload an audio file to S3 for testing */
  uploadTestAudio: (bucket: string, prefix?: string) => Promise<UploadResult>;
  /** Upload any test asset to S3 */
  uploadTestAsset: (bucket: string, type: MediaType, prefix?: string) => Promise<UploadResult>;
  /** Delete a test asset from S3 */
  deleteTestAsset: (asset: TestAsset) => Promise<boolean>;
  /** Clean up all test assets in a bucket with a given prefix */
  cleanupTestAssets: (bucket: string, prefix: string) => Promise<void>;
  /** List of uploaded assets for cleanup */
  uploadedAssets: TestAsset[];
};

/**
 * Extended test fixture with test data capabilities
 */
export const test = authTest.extend<TestDataFixtures>({
  /**
   * Track uploaded assets for cleanup
   */
  uploadedAssets: async ({}, use) => {
    const assets: TestAsset[] = [];
    await use(assets);
  },

  /**
   * Upload a test video file to S3
   */
  uploadTestVideo: async ({ uploadedAssets }, use) => {
    const s3Client = new S3Client({ region: AWS_REGION });

    const uploadVideo = async (
      bucket: string,
      prefix: string = "test-assets"
    ): Promise<UploadResult> => {
      const assetId = generateAssetId();
      const config = SAMPLE_TEST_FILES.video;
      const s3Key = `${prefix}/${assetId}/${config.filename}`;
      const content = config.generateContent();

      try {
        console.log(`[TestDataFixture] Uploading test video to s3://${bucket}/${s3Key}`);

        await s3Client.send(
          new PutObjectCommand({
            Bucket: bucket,
            Key: s3Key,
            Body: content,
            ContentType: config.contentType,
          })
        );

        const asset: TestAsset = {
          id: assetId,
          type: "video",
          filename: config.filename,
          s3Key,
          bucket,
          size: content.length,
          contentType: config.contentType,
        };

        uploadedAssets.push(asset);
        console.log(`[TestDataFixture] Video uploaded successfully: ${assetId}`);

        return { success: true, asset };
      } catch (error: any) {
        console.error(`[TestDataFixture] Error uploading video:`, error);
        return { success: false, error: error.message };
      }
    };

    await use(uploadVideo);
  },

  /**
   * Upload a test image file to S3
   */
  uploadTestImage: async ({ uploadedAssets }, use) => {
    const s3Client = new S3Client({ region: AWS_REGION });

    const uploadImage = async (
      bucket: string,
      prefix: string = "test-assets"
    ): Promise<UploadResult> => {
      const assetId = generateAssetId();
      const config = SAMPLE_TEST_FILES.image;
      const s3Key = `${prefix}/${assetId}/${config.filename}`;
      const content = config.generateContent();

      try {
        console.log(`[TestDataFixture] Uploading test image to s3://${bucket}/${s3Key}`);

        await s3Client.send(
          new PutObjectCommand({
            Bucket: bucket,
            Key: s3Key,
            Body: content,
            ContentType: config.contentType,
          })
        );

        const asset: TestAsset = {
          id: assetId,
          type: "image",
          filename: config.filename,
          s3Key,
          bucket,
          size: content.length,
          contentType: config.contentType,
        };

        uploadedAssets.push(asset);
        console.log(`[TestDataFixture] Image uploaded successfully: ${assetId}`);

        return { success: true, asset };
      } catch (error: any) {
        console.error(`[TestDataFixture] Error uploading image:`, error);
        return { success: false, error: error.message };
      }
    };

    await use(uploadImage);
  },

  /**
   * Upload a test audio file to S3
   */
  uploadTestAudio: async ({ uploadedAssets }, use) => {
    const s3Client = new S3Client({ region: AWS_REGION });

    const uploadAudio = async (
      bucket: string,
      prefix: string = "test-assets"
    ): Promise<UploadResult> => {
      const assetId = generateAssetId();
      const config = SAMPLE_TEST_FILES.audio;
      const s3Key = `${prefix}/${assetId}/${config.filename}`;
      const content = config.generateContent();

      try {
        console.log(`[TestDataFixture] Uploading test audio to s3://${bucket}/${s3Key}`);

        await s3Client.send(
          new PutObjectCommand({
            Bucket: bucket,
            Key: s3Key,
            Body: content,
            ContentType: config.contentType,
          })
        );

        const asset: TestAsset = {
          id: assetId,
          type: "audio",
          filename: config.filename,
          s3Key,
          bucket,
          size: content.length,
          contentType: config.contentType,
        };

        uploadedAssets.push(asset);
        console.log(`[TestDataFixture] Audio uploaded successfully: ${assetId}`);

        return { success: true, asset };
      } catch (error: any) {
        console.error(`[TestDataFixture] Error uploading audio:`, error);
        return { success: false, error: error.message };
      }
    };

    await use(uploadAudio);
  },

  /**
   * Upload any type of test asset to S3
   */
  uploadTestAsset: async ({ uploadedAssets }, use) => {
    const s3Client = new S3Client({ region: AWS_REGION });

    const uploadAsset = async (
      bucket: string,
      type: MediaType,
      prefix: string = "test-assets"
    ): Promise<UploadResult> => {
      const assetId = generateAssetId();
      const config = SAMPLE_TEST_FILES[type];
      const s3Key = `${prefix}/${assetId}/${config.filename}`;
      const content = config.generateContent();

      try {
        console.log(`[TestDataFixture] Uploading test ${type} to s3://${bucket}/${s3Key}`);

        await s3Client.send(
          new PutObjectCommand({
            Bucket: bucket,
            Key: s3Key,
            Body: content,
            ContentType: config.contentType,
          })
        );

        const asset: TestAsset = {
          id: assetId,
          type,
          filename: config.filename,
          s3Key,
          bucket,
          size: content.length,
          contentType: config.contentType,
        };

        uploadedAssets.push(asset);
        console.log(`[TestDataFixture] ${type} uploaded successfully: ${assetId}`);

        return { success: true, asset };
      } catch (error: any) {
        console.error(`[TestDataFixture] Error uploading ${type}:`, error);
        return { success: false, error: error.message };
      }
    };

    await use(uploadAsset);
  },

  /**
   * Delete a test asset from S3
   */
  deleteTestAsset: async ({ uploadedAssets }, use) => {
    const s3Client = new S3Client({ region: AWS_REGION });

    const deleteAsset = async (asset: TestAsset): Promise<boolean> => {
      try {
        console.log(`[TestDataFixture] Deleting asset s3://${asset.bucket}/${asset.s3Key}`);

        await s3Client.send(
          new DeleteObjectCommand({
            Bucket: asset.bucket,
            Key: asset.s3Key,
          })
        );

        // Remove from tracked assets
        const index = uploadedAssets.findIndex((a) => a.id === asset.id);
        if (index > -1) {
          uploadedAssets.splice(index, 1);
        }

        console.log(`[TestDataFixture] Asset deleted successfully: ${asset.id}`);
        return true;
      } catch (error: any) {
        console.error(`[TestDataFixture] Error deleting asset:`, error);
        return false;
      }
    };

    await use(deleteAsset);
  },

  /**
   * Clean up all test assets in a bucket with a given prefix
   */
  cleanupTestAssets: async ({ uploadedAssets }, use) => {
    const s3Client = new S3Client({ region: AWS_REGION });

    const cleanup = async (bucket: string, prefix: string): Promise<void> => {
      console.log(`[TestDataFixture] Cleaning up test assets in s3://${bucket}/${prefix}`);

      try {
        // List all objects with the prefix
        let continuationToken: string | undefined;
        let isTruncated = true;

        while (isTruncated) {
          const listResponse = await s3Client.send(
            new ListObjectsV2Command({
              Bucket: bucket,
              Prefix: prefix,
              ContinuationToken: continuationToken,
            })
          );

          if (listResponse.Contents && listResponse.Contents.length > 0) {
            const deletePromises = listResponse.Contents.map((object) => {
              if (object.Key) {
                console.log(`[TestDataFixture] Deleting ${object.Key} from ${bucket}`);
                return s3Client.send(new DeleteObjectCommand({ Bucket: bucket, Key: object.Key }));
              }
              return Promise.resolve();
            });
            await Promise.all(deletePromises);
          }

          isTruncated = listResponse.IsTruncated ?? false;
          continuationToken = listResponse.NextContinuationToken;
        }

        // Clear tracked assets for this bucket/prefix
        const remaining = uploadedAssets.filter(
          (a) => a.bucket !== bucket || !a.s3Key.startsWith(prefix)
        );
        uploadedAssets.length = 0;
        uploadedAssets.push(...remaining);

        console.log(`[TestDataFixture] Cleanup completed for ${prefix}`);
      } catch (error: any) {
        console.error(`[TestDataFixture] Error during cleanup:`, error);
      }
    };

    await use(cleanup);

    // Auto-cleanup all tracked assets after test
    console.log(`[TestDataFixture] Auto-cleaning ${uploadedAssets.length} tracked assets`);
    for (const asset of [...uploadedAssets]) {
      try {
        await s3Client.send(
          new DeleteObjectCommand({
            Bucket: asset.bucket,
            Key: asset.s3Key,
          })
        );
        console.log(`[TestDataFixture] Auto-deleted: ${asset.s3Key}`);
      } catch (error: any) {
        console.error(`[TestDataFixture] Error auto-deleting ${asset.s3Key}:`, error);
      }
    }
  },
});

// Re-export expect from Playwright
export { expect } from "@playwright/test";

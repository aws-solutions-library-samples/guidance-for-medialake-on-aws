import { test, expect } from "@playwright/test";
import {
  S3Client,
  PutObjectCommand,
  HeadBucketCommand,
  DeleteObjectCommand,
  CreateBucketCommand,
  DeleteBucketCommand,
  ListObjectsV2Command,
  BucketLocationConstraint,
} from "@aws-sdk/client-s3";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import * as crypto from "crypto";

/**
 * S3 Upload Test
 *
 * This test:
 * 1. Creates an S3 bucket with a random name
 * 2. Uploads a test image to the bucket
 * 3. Deletes the image from the bucket
 * 4. Deletes the bucket
 *
 * Prerequisites:
 * 1. AWS credentials must be configured in one of the following ways:
 *    - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
 *    - Shared credentials file (~/.aws/credentials)
 *    - AWS IAM role (if running on AWS services like EC2)
 *
 * To run this test:
 * npx playwright test tests/s3-upload.spec.ts
 *
 * To run with specific AWS profile:
 * AWS_PROFILE=your-profile npx playwright test tests/s3-upload.spec.ts
 */

// Test configuration
const TEST_FILE_NAME = "test_photo1.jpg";
const LOCAL_TEST_FILE_PATH = path.join(os.tmpdir(), TEST_FILE_NAME);
const AWS_REGION = process.env.AWS_REGION || "us-east-1";

// Generate a random bucket name
function generateRandomBucketName(): string {
  // Generate a random ID (8 characters)
  const randomId = crypto.randomBytes(4).toString("hex");
  return `medialake-test-${randomId}`;
}

// Create a helper function to create a test image
function createTestImage(filePath: string, width = 100, height = 100): void {
  // Check if the test directory exists, if not create it
  const testDir = path.dirname(filePath);
  if (!fs.existsSync(testDir)) {
    fs.mkdirSync(testDir, { recursive: true });
  }

  // If the test file already exists, just return
  if (fs.existsSync(filePath)) {
    console.log(`Test file already exists at ${filePath}`);
    return;
  }

  // Create a simple test image (we're using a real JPG header with minimal data)
  // This is a very small valid JPEG that should work for testing
  const minimalJpeg = Buffer.from([
    0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01,
    0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00, 0xff, 0xdb, 0x00, 0x43,
    0x00, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xc0, 0x00, 0x0b, 0x08, 0x00, 0x01, 0x00,
    0x01, 0x01, 0x01, 0x11, 0x00, 0xff, 0xc4, 0x00, 0x14, 0x00, 0x01, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0xff, 0xc4, 0x00, 0x14, 0x10, 0x01, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0xff, 0xda, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3f, 0x00, 0x00,
    0x00, 0xff, 0xd9,
  ]);

  fs.writeFileSync(filePath, minimalJpeg);
  console.log(`Created test image at ${filePath}`);
}

// Helper function to empty a bucket before deletion
async function emptyBucket(
  s3Client: S3Client,
  bucketName: string,
): Promise<void> {
  console.log(`Emptying bucket ${bucketName} before deletion`);

  try {
    // List all objects in the bucket
    const listCommand = new ListObjectsV2Command({
      Bucket: bucketName,
    });

    const listResponse = await s3Client.send(listCommand);

    if (listResponse.Contents && listResponse.Contents.length > 0) {
      // Delete each object
      for (const object of listResponse.Contents) {
        if (object.Key) {
          const deleteParams = {
            Bucket: bucketName,
            Key: object.Key,
          };

          await s3Client.send(new DeleteObjectCommand(deleteParams));
          console.log(`Deleted object ${object.Key} from bucket ${bucketName}`);
        }
      }
    }

    console.log(`Bucket ${bucketName} emptied successfully`);
  } catch (error) {
    console.error(`Error emptying bucket ${bucketName}:`, error);
    throw error;
  }
}

// This test will create a bucket, upload a file to S3, delete the file, and then delete the bucket
test("create bucket, upload file to S3, and clean up", async ({ page }) => {
  // Ensure we have a test image
  createTestImage(LOCAL_TEST_FILE_PATH);

  // Generate a random bucket name
  const TEST_BUCKET = generateRandomBucketName();
  console.log(`Using random bucket name: ${TEST_BUCKET}`);

  // Initialize S3 client with proper credentials
  const s3Client = new S3Client({
    region: AWS_REGION,
  });

  try {
    // Step 1: Create the bucket
    console.log(`Creating bucket ${TEST_BUCKET} in region ${AWS_REGION}...`);

    // Only specify LocationConstraint if not in us-east-1 (which is the default)
    const createBucketParams: any = {
      Bucket: TEST_BUCKET,
    };

    // AWS requires no LocationConstraint for us-east-1, but requires it for other regions
    if (AWS_REGION !== "us-east-1") {
      createBucketParams.CreateBucketConfiguration = {
        LocationConstraint: AWS_REGION as BucketLocationConstraint,
      };
    }

    const createBucketCommand = new CreateBucketCommand(createBucketParams);

    const createBucketResponse = await s3Client.send(createBucketCommand);
    console.log(
      `Bucket creation response:`,
      JSON.stringify(createBucketResponse, null, 2),
    );
    expect(createBucketResponse.$metadata.httpStatusCode).toBe(200);

    // Wait a moment for bucket to be available
    console.log(`Waiting for bucket ${TEST_BUCKET} to be fully available...`);
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Step 2: Verify bucket exists
    const headBucketCommand = new HeadBucketCommand({ Bucket: TEST_BUCKET });
    await s3Client.send(headBucketCommand);
    console.log(`Bucket ${TEST_BUCKET} exists and is accessible`);

    // Step 3: Read the test file
    const fileContent = fs.readFileSync(LOCAL_TEST_FILE_PATH);
    console.log(`Read test file of size ${fileContent.length} bytes`);

    // Step 4: Upload the file to S3
    // Create a unique test ID
    const testId = `test-${Date.now()}`;

    const uploadParams = {
      Bucket: TEST_BUCKET,
      Key: TEST_FILE_NAME,
      Body: fileContent,
      ContentType: "image/jpeg",
      Metadata: {
        "x-amz-meta-source": "playwright-test",
        "x-amz-meta-test-id": testId,
      },
    };

    console.log(`Uploading ${TEST_FILE_NAME} to ${TEST_BUCKET}`);
    const uploadResponse = await s3Client.send(
      new PutObjectCommand(uploadParams),
    );

    console.log(`Successfully uploaded ${TEST_FILE_NAME} to ${TEST_BUCKET}`);
    console.log("S3 upload response:", JSON.stringify(uploadResponse, null, 2));

    // Verify upload was successful
    expect(uploadResponse.$metadata.httpStatusCode).toBe(200);

    // Step 5: Delete the file from S3
    console.log(`Deleting ${TEST_FILE_NAME} from ${TEST_BUCKET}`);
    const deleteParams = {
      Bucket: TEST_BUCKET,
      Key: TEST_FILE_NAME,
    };

    const deleteResponse = await s3Client.send(
      new DeleteObjectCommand(deleteParams),
    );
    console.log("Delete response:", JSON.stringify(deleteResponse, null, 2));

    // Verify delete was successful
    expect(deleteResponse.$metadata.httpStatusCode).toBe(204);
    console.log(`Successfully deleted ${TEST_FILE_NAME} from ${TEST_BUCKET}`);
  } catch (error) {
    console.error("Error during S3 operations:", error);
    throw error;
  } finally {
    // Step 6: Clean up - Delete the bucket regardless of test success/failure
    try {
      // Make sure the bucket is empty before deleting it
      await emptyBucket(s3Client, TEST_BUCKET);

      // Delete the bucket
      console.log(`Deleting bucket ${TEST_BUCKET}...`);
      const deleteBucketCommand = new DeleteBucketCommand({
        Bucket: TEST_BUCKET,
      });

      const deleteBucketResponse = await s3Client.send(deleteBucketCommand);
      console.log(
        `Bucket deletion response:`,
        JSON.stringify(deleteBucketResponse, null, 2),
      );
      console.log(`Successfully deleted bucket ${TEST_BUCKET}`);
    } catch (error) {
      console.error(`Error deleting bucket ${TEST_BUCKET}:`, error);
      // Don't throw here to avoid masking the original test error
      console.error(
        "Bucket cleanup failed, you may need to manually delete the bucket",
      );
    }
  }
});

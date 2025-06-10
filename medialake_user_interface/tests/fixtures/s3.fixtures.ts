import { test as base } from '@playwright/test';
import { 
  S3Client, 
  CreateBucketCommand,
  DeleteBucketCommand,
  ListObjectsV2Command,
  DeleteObjectCommand,
  HeadBucketCommand,
  BucketLocationConstraint
} from '@aws-sdk/client-s3';
import { fromIni } from '@aws-sdk/credential-providers';
import * as crypto from 'crypto';
import { TestInfo } from '@playwright/test';

const AWS_REGION = process.env.AWS_REGION || 'us-east-1';
const AWS_PROFILE = 'medialake-dev4';

// Generate a random bucket name
function generateRandomBucketName(): string {
  const randomId = crypto.randomBytes(4).toString('hex');
  return `medialake-pw-test-${randomId}`; // Prefix to identify test buckets
}

// Helper function to empty a bucket before deletion
async function emptyBucket(s3Client: S3Client, bucketName: string): Promise<void> {
  console.log(`[Fixture] Emptying bucket ${bucketName} before deletion`);
  try {
    const listCommand = new ListObjectsV2Command({ Bucket: bucketName });
    let isTruncated = true;
    let continuationToken: string | undefined;

    while (isTruncated) {
        const listResponse = await s3Client.send(new ListObjectsV2Command({
             Bucket: bucketName,
             ContinuationToken: continuationToken
         }));
        
        if (listResponse.Contents && listResponse.Contents.length > 0) {
            const deletePromises = listResponse.Contents.map(object => {
                if (object.Key) {
                    console.log(`[Fixture] Deleting object ${object.Key} from bucket ${bucketName}`);
                    return s3Client.send(new DeleteObjectCommand({ Bucket: bucketName, Key: object.Key }));
                }
                return Promise.resolve();
            });
            await Promise.all(deletePromises);
        }
        isTruncated = listResponse.IsTruncated ?? false;
        continuationToken = listResponse.NextContinuationToken;
    }
    console.log(`[Fixture] Bucket ${bucketName} emptied successfully`);
  } catch (error: any) {
      if (error.name === 'NoSuchBucket') {
          console.log(`[Fixture] Bucket ${bucketName} does not exist, skipping emptying.`);
          return; // Bucket doesn't exist, nothing to empty
      }
      console.error(`[Fixture] Error emptying bucket ${bucketName}:`, error);
      throw error; // Re-throw other errors
  }
}

// Helper function to create S3 client
function createS3Client(): S3Client {
  const credentials = fromIni({ profile: AWS_PROFILE });
  return new S3Client({ 
    region: AWS_REGION,
    credentials 
  });
}

// Define the types for our fixtures
type S3Fixtures = {
  s3BucketName: string;
  s3BucketCreation: string;
  s3BucketDeletion: void;
};

// Extend the base Playwright test fixture
export const test = base.extend<S3Fixtures>({
  // Fixture to create the S3 bucket before tests
  s3BucketCreation: [async ({ }, use, testInfo) => {
    const bucketName = generateRandomBucketName() + `-test-${testInfo.workerIndex}-${Date.now()}`;
    console.log(`[S3 Creation Fixture] Generated bucket name: ${bucketName}`);

    const s3Client = createS3Client();

    try {
      // Create the bucket
      console.log(`[S3 Creation Fixture] Creating bucket ${bucketName} in region ${AWS_REGION}...`);
      const createBucketParams: any = { Bucket: bucketName };
      if (AWS_REGION !== 'us-east-1') {
        createBucketParams.CreateBucketConfiguration = {
          LocationConstraint: AWS_REGION as BucketLocationConstraint
        };
      }
      await s3Client.send(new CreateBucketCommand(createBucketParams));
      console.log(`[S3 Creation Fixture] Bucket ${bucketName} created.`);

      // Wait for bucket to be available and verify multiple times
      let bucketReady = false;
      let attempts = 0;
      const maxAttempts = 10;
      
      while (!bucketReady && attempts < maxAttempts) {
        try {
          await new Promise(resolve => setTimeout(resolve, 2000)); 
          await s3Client.send(new HeadBucketCommand({ Bucket: bucketName }));
          bucketReady = true;
          console.log(`[S3 Creation Fixture] Bucket ${bucketName} confirmed to exist after ${attempts + 1} attempts.`);
        } catch (error) {
          attempts++;
          console.log(`[S3 Creation Fixture] Bucket ${bucketName} not ready yet, attempt ${attempts}/${maxAttempts}`);
          if (attempts === maxAttempts) {
            throw new Error(`Bucket ${bucketName} not available after ${maxAttempts} attempts`);
          }
        }
      }

      // Store the bucket name in the test context (we'll pass this to s3BucketName)
      await use(bucketName);

    } catch (error) {
        console.error(`[S3 Creation Fixture] Error setting up bucket ${bucketName}:`, error);
        throw error; // Fail the test if setup fails
    }
  }, { scope: 'test' }],

  // Fixture to provide the bucket name to tests
  s3BucketName: [async ({ s3BucketCreation }, use) => {
    console.log(`[S3 BucketName Fixture] Using bucket: ${s3BucketCreation}`);
    await use(s3BucketCreation);
  }, { scope: 'test' }],

  // Fixture to delete the S3 bucket after tests
  s3BucketDeletion: [async ({ s3BucketCreation }, use, testInfo) => {
    // This fixture runs after the test
    await use();

    // Now clean up the bucket
    const bucketName = s3BucketCreation;
    console.log(`[S3 Deletion Fixture] Cleaning up bucket ${bucketName}...`);
    
    const s3Client = createS3Client();
    
    try {
      await emptyBucket(s3Client, bucketName);
      await s3Client.send(new DeleteBucketCommand({ Bucket: bucketName }));
      console.log(`[S3 Deletion Fixture] Successfully deleted bucket ${bucketName}`);
    } catch (error: any) {
      if (error.name === 'NoSuchBucket') {
         console.log(`[S3 Deletion Fixture] Bucket ${bucketName} already deleted or never created.`);
      } else {
        console.error(`[S3 Deletion Fixture] Error deleting bucket ${bucketName}:`, error);
        // Log error but don't fail the teardown unless critical
      }
    }
  }, { scope: 'test' }], 
});

export { expect } from '@playwright/test'; 
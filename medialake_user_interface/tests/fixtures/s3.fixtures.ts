import { test as base } from "@playwright/test";
import {
  S3Client,
  CreateBucketCommand,
  DeleteBucketCommand,
  ListObjectsV2Command,
  DeleteObjectCommand,
  HeadBucketCommand,
  BucketLocationConstraint,
} from "@aws-sdk/client-s3";
import * as crypto from "crypto";
import { TestInfo } from "@playwright/test";

const AWS_REGION = process.env.AWS_REGION || "us-east-1";

// Generate a random bucket name
function generateRandomBucketName(): string {
  const randomId = crypto.randomBytes(4).toString("hex");
  return `medialake-pw-test-${randomId}`; // Prefix to identify test buckets
}

// Helper function to empty a bucket before deletion
async function emptyBucket(
  s3Client: S3Client,
  bucketName: string,
): Promise<void> {
  console.log(`[Fixture] Emptying bucket ${bucketName} before deletion`);
  try {
    const listCommand = new ListObjectsV2Command({ Bucket: bucketName });
    let isTruncated = true;
    let continuationToken: string | undefined;

    while (isTruncated) {
      const listResponse = await s3Client.send(
        new ListObjectsV2Command({
          Bucket: bucketName,
          ContinuationToken: continuationToken,
        }),
      );

      if (listResponse.Contents && listResponse.Contents.length > 0) {
        const deletePromises = listResponse.Contents.map((object) => {
          if (object.Key) {
            console.log(
              `[Fixture] Deleting object ${object.Key} from bucket ${bucketName}`,
            );
            return s3Client.send(
              new DeleteObjectCommand({ Bucket: bucketName, Key: object.Key }),
            );
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
    if (error.name === "NoSuchBucket") {
      console.log(
        `[Fixture] Bucket ${bucketName} does not exist, skipping emptying.`,
      );
      return; // Bucket doesn't exist, nothing to empty
    }
    console.error(`[Fixture] Error emptying bucket ${bucketName}:`, error);
    throw error; // Re-throw other errors
  }
}

// Define the type for our new fixture
type S3Fixtures = {
  s3BucketName: string;
  s3BucketDeletion: () => Promise<void>;
};

// Extend the base Playwright test fixture
// Exporting this as 'test' now, only contains S3 fixture
export const test = base.extend<S3Fixtures>({
  // @ts-expect-error - Playwright's type inference struggles with worker-scoped fixtures in extensions
  s3BucketName: [
    async (
      {
        /* No base fixtures needed here */
      },
      use,
      workerInfo,
    ) => {
      const bucketName =
        generateRandomBucketName() + `-worker-${workerInfo.workerIndex}`;
      console.log(
        `[Fixture Worker ${workerInfo.workerIndex}] Generated bucket name: ${bucketName}`,
      );

      // Initialize S3 client.
      // The AWS SDK automatically uses the standard credential chain:
      // 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
      // 2. Profile from AWS_PROFILE environment variable (if set)
      // 3. Shared credentials file (~/.aws/credentials)
      // 4. Shared config file (~/.aws/config)
      // 5. IAM role (if running on EC2/ECS/etc.)
      // To use a specific profile, run tests like:
      // AWS_PROFILE=your-profile npx playwright test
      const s3Client = new S3Client({ region: AWS_REGION });

      // Alternatively, force a profile (less flexible):
      // const credentials = fromIni({ profile: 'your-profile' });
      // const s3Client = new S3Client({ region: AWS_REGION, credentials });

      try {
        // Create the bucket
        console.log(
          `[Fixture Worker ${workerInfo.workerIndex}] Creating bucket ${bucketName} in region ${AWS_REGION}...`,
        );
        const createBucketParams: any = { Bucket: bucketName };
        if (AWS_REGION !== "us-east-1") {
          createBucketParams.CreateBucketConfiguration = {
            LocationConstraint: AWS_REGION as BucketLocationConstraint,
          };
        }
        await s3Client.send(new CreateBucketCommand(createBucketParams));
        console.log(
          `[Fixture Worker ${workerInfo.workerIndex}] Bucket ${bucketName} created.`,
        );

        // Wait briefly for bucket to be available
        await new Promise((resolve) => setTimeout(resolve, 2000));

        // Verify bucket exists
        await s3Client.send(new HeadBucketCommand({ Bucket: bucketName }));
        console.log(
          `[Fixture Worker ${workerInfo.workerIndex}] Bucket ${bucketName} confirmed to exist.`,
        );

        // Use the bucket name in the test
        await use(bucketName);
      } catch (error) {
        console.error(
          `[Fixture Worker ${workerInfo.workerIndex}] Error setting up bucket ${bucketName}:`,
          error,
        );
        // If setup fails, ensure cleanup still attempts (though bucket might not exist)
        throw error; // Fail the test if setup fails
      } finally {
        // Teardown: Delete the bucket after the tests for this worker are done
        console.log(
          `[Fixture Worker ${workerInfo.workerIndex}] Cleaning up bucket ${bucketName}...`,
        );
        try {
          await emptyBucket(s3Client, bucketName);
          await s3Client.send(new DeleteBucketCommand({ Bucket: bucketName }));
          console.log(
            `[Fixture Worker ${workerInfo.workerIndex}] Successfully deleted bucket ${bucketName}`,
          );
        } catch (error: any) {
          if (error.name === "NoSuchBucket") {
            console.log(
              `[Fixture Worker ${workerInfo.workerIndex}] Bucket ${bucketName} already deleted or never created.`,
            );
          } else {
            console.error(
              `[Fixture Worker ${workerInfo.workerIndex}] Error deleting bucket ${bucketName}:`,
              error,
            );
            // Log error but don't fail the teardown unless critical
          }
        }
      }
    },
    { scope: "worker" },
  ],

  s3BucketDeletion: [
    async ({ s3BucketName }, use) => {
      // Provide a cleanup function that can be called manually if needed
      const cleanup = async () => {
        console.log(
          `[Fixture] Manual cleanup requested for bucket ${s3BucketName}`,
        );
        const s3Client = new S3Client({ region: AWS_REGION });
        try {
          await emptyBucket(s3Client, s3BucketName);
          await s3Client.send(
            new DeleteBucketCommand({ Bucket: s3BucketName }),
          );
          console.log(
            `[Fixture] Successfully manually deleted bucket ${s3BucketName}`,
          );
        } catch (error: any) {
          if (error.name === "NoSuchBucket") {
            console.log(
              `[Fixture] Bucket ${s3BucketName} already deleted or never created.`,
            );
          } else {
            console.error(
              `[Fixture] Error manually deleting bucket ${s3BucketName}:`,
              error,
            );
          }
        }
      };

      await use(cleanup);
    },
    { scope: "test" },
  ],
});

export { expect } from "@playwright/test";

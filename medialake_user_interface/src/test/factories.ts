import { faker } from "@faker-js/faker";

/**
 * Test data factories using Faker.
 * Override only what the test cares about.
 */

export interface TestAsset {
  InventoryID: string;
  score?: number;
  DigitalSourceAsset: {
    Type: string;
    MainRepresentation: {
      StorageInfo: {
        PrimaryLocation: {
          ObjectKey: { Name: string };
        };
      };
    };
  };
  clips?: Array<{
    start_timecode?: string;
    end_timecode?: string;
    start?: number;
    end?: number;
    score?: number;
    model_version?: string;
  }>;
}

export function createTestAsset(overrides: Partial<TestAsset> = {}): TestAsset {
  return {
    InventoryID: faker.string.uuid(),
    score: faker.number.float({ min: 0, max: 1, fractionDigits: 3 }),
    DigitalSourceAsset: {
      Type: faker.helpers.arrayElement(["Video", "Image", "Audio"]),
      MainRepresentation: {
        StorageInfo: {
          PrimaryLocation: {
            ObjectKey: { Name: faker.system.fileName() },
          },
        },
      },
    },
    ...overrides,
  };
}

export function createVideoAssetWithClips(
  clipCount: number,
  overrides: Partial<TestAsset> = {}
): TestAsset {
  const clips = Array.from({ length: clipCount }, (_, i) => ({
    start: i * 10,
    end: (i + 1) * 10,
    start_timecode: `00:00:${String(i * 10).padStart(2, "0")}:00`,
    end_timecode: `00:00:${String((i + 1) * 10).padStart(2, "0")}:00`,
    score: faker.number.float({ min: 0, max: 1, fractionDigits: 3 }),
    model_version: "3.0",
  }));

  return createTestAsset({
    DigitalSourceAsset: {
      Type: "Video",
      MainRepresentation: {
        StorageInfo: {
          PrimaryLocation: {
            ObjectKey: { Name: faker.system.fileName({ extensionCount: 1 }) },
          },
        },
      },
    },
    clips,
    ...overrides,
  });
}

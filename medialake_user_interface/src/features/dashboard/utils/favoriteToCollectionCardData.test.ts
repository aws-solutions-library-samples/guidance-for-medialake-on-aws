import { describe, it, expect } from "vitest";
import { favoriteToCollectionCardData } from "./favoriteToCollectionCardData";
import type { Favorite } from "@/api/hooks/useFavorites";
import type { Collection } from "@/api/hooks/useCollections";

/**
 * Unit Tests for favoriteToCollectionCardData
 *
 * Feature: collection-favorites
 * **Validates: Requirements 3.2, 4.2**
 *
 * Tests cover:
 * - Full metadata → all fields populated from metadata
 * - Partial metadata → missing fields use safe defaults
 * - Missing/empty metadata → all fields use safe defaults, name falls back to itemId
 * - Type completeness → returned object has all required Collection fields
 * - Specific default values → ownerId="", status="active", childCount=0, etc.
 * - Type derivation → isPublic=true → type="public", isPublic=false/missing → type="private"
 */
describe("favoriteToCollectionCardData", () => {
  describe("full metadata", () => {
    it("should map all metadata fields to their corresponding Collection fields", () => {
      const fav: Favorite = {
        itemId: "col-123",
        itemType: "COLLECTION",
        metadata: {
          name: "My Collection",
          isPublic: true,
          itemCount: 42,
          childCollectionCount: 5,
          childCount: 3,
          collectionTypeId: "type-abc",
          thumbnailType: "icon",
          thumbnailValue: "star",
          thumbnailUrl: "https://cdn.example.com/thumb.png",
        },
      };

      const result = favoriteToCollectionCardData(fav);

      expect(result.id).toBe("col-123");
      expect(result.name).toBe("My Collection");
      expect(result.isPublic).toBe(true);
      expect(result.type).toBe("public");
      expect(result.itemCount).toBe(42);
      expect(result.childCollectionCount).toBe(5);
      expect(result.childCount).toBe(3);
      expect(result.collectionTypeId).toBe("type-abc");
      expect(result.thumbnailType).toBe("icon");
      expect(result.thumbnailValue).toBe("star");
      expect(result.thumbnailUrl).toBe("https://cdn.example.com/thumb.png");
      // Safe defaults for required fields not in metadata
      expect(result.ownerId).toBe("");
      expect(result.status).toBe("active");
      expect(result.createdAt).toBe("");
      expect(result.updatedAt).toBe("");
    });
  });

  describe("partial metadata", () => {
    it("should use safe defaults for missing metadata fields", () => {
      const fav: Favorite = {
        itemId: "col-456",
        itemType: "COLLECTION",
        metadata: {
          name: "Partial Collection",
          isPublic: true,
          // itemCount, childCollectionCount, childCount, etc. are missing
        },
      };

      const result = favoriteToCollectionCardData(fav);

      expect(result.id).toBe("col-456");
      expect(result.name).toBe("Partial Collection");
      expect(result.isPublic).toBe(true);
      expect(result.type).toBe("public");
      // Missing numeric fields default to 0
      expect(result.itemCount).toBe(0);
      expect(result.childCollectionCount).toBe(0);
      expect(result.childCount).toBe(0);
      // Missing optional fields are undefined
      expect(result.collectionTypeId).toBeUndefined();
      expect(result.thumbnailType).toBeUndefined();
      expect(result.thumbnailValue).toBeUndefined();
      expect(result.thumbnailUrl).toBeUndefined();
    });

    it("should handle metadata with only itemCount and childCollectionCount", () => {
      const fav: Favorite = {
        itemId: "col-789",
        itemType: "COLLECTION",
        metadata: {
          itemCount: 10,
          childCollectionCount: 2,
        },
      };

      const result = favoriteToCollectionCardData(fav);

      expect(result.id).toBe("col-789");
      // name falls back to itemId when not in metadata
      expect(result.name).toBe("col-789");
      expect(result.isPublic).toBe(false);
      expect(result.type).toBe("private");
      expect(result.itemCount).toBe(10);
      expect(result.childCollectionCount).toBe(2);
      expect(result.childCount).toBe(0);
    });
  });

  describe("missing/empty metadata", () => {
    it("should use safe defaults when metadata is an empty object", () => {
      const fav: Favorite = {
        itemId: "col-empty",
        itemType: "COLLECTION",
        metadata: {},
      };

      const result = favoriteToCollectionCardData(fav);

      expect(result.id).toBe("col-empty");
      expect(result.name).toBe("col-empty"); // falls back to itemId
      expect(result.isPublic).toBe(false);
      expect(result.type).toBe("private");
      expect(result.itemCount).toBe(0);
      expect(result.childCollectionCount).toBe(0);
      expect(result.childCount).toBe(0);
      expect(result.ownerId).toBe("");
      expect(result.status).toBe("active");
      expect(result.createdAt).toBe("");
      expect(result.updatedAt).toBe("");
    });

    it("should use safe defaults when metadata is undefined", () => {
      const fav: Favorite = {
        itemId: "col-no-meta",
        itemType: "COLLECTION",
        // metadata is undefined
      };

      const result = favoriteToCollectionCardData(fav);

      expect(result.id).toBe("col-no-meta");
      expect(result.name).toBe("col-no-meta"); // falls back to itemId
      expect(result.isPublic).toBe(false);
      expect(result.type).toBe("private");
      expect(result.itemCount).toBe(0);
      expect(result.childCollectionCount).toBe(0);
      expect(result.childCount).toBe(0);
      expect(result.ownerId).toBe("");
      expect(result.status).toBe("active");
      expect(result.createdAt).toBe("");
      expect(result.updatedAt).toBe("");
    });
  });

  describe("type completeness", () => {
    it("should return an object with all required Collection fields", () => {
      const fav: Favorite = {
        itemId: "col-type-check",
        itemType: "COLLECTION",
        metadata: {},
      };

      const result = favoriteToCollectionCardData(fav);

      // All required fields of Collection must be present and defined
      const requiredFields: Array<keyof Collection> = [
        "id",
        "name",
        "type",
        "ownerId",
        "status",
        "childCount",
        "createdAt",
        "updatedAt",
        "isPublic",
        "itemCount",
        "childCollectionCount",
      ];

      for (const field of requiredFields) {
        expect(result).toHaveProperty(field);
        expect(result[field]).toBeDefined();
      }
    });

    it("should satisfy the Collection type contract (assignable to Collection)", () => {
      const fav: Favorite = {
        itemId: "col-contract",
        itemType: "COLLECTION",
        metadata: { name: "Contract Test", isPublic: true },
      };

      // This assignment confirms type compatibility at compile time,
      // and at runtime we verify the shape is complete
      const result: Collection = favoriteToCollectionCardData(fav);

      expect(result.id).toBe("col-contract");
      expect(result.name).toBe("Contract Test");
      expect(typeof result.type).toBe("string");
      expect(typeof result.ownerId).toBe("string");
      expect(typeof result.status).toBe("string");
      expect(typeof result.childCount).toBe("number");
      expect(typeof result.createdAt).toBe("string");
      expect(typeof result.updatedAt).toBe("string");
      expect(typeof result.isPublic).toBe("boolean");
      expect(typeof result.itemCount).toBe("number");
      expect(typeof result.childCollectionCount).toBe("number");
    });
  });

  describe("specific default values", () => {
    it('should default ownerId to ""', () => {
      const fav: Favorite = { itemId: "x", itemType: "COLLECTION", metadata: {} };
      expect(favoriteToCollectionCardData(fav).ownerId).toBe("");
    });

    it('should default status to "active"', () => {
      const fav: Favorite = { itemId: "x", itemType: "COLLECTION", metadata: {} };
      expect(favoriteToCollectionCardData(fav).status).toBe("active");
    });

    it("should default childCount to 0", () => {
      const fav: Favorite = { itemId: "x", itemType: "COLLECTION", metadata: {} };
      expect(favoriteToCollectionCardData(fav).childCount).toBe(0);
    });

    it('should default createdAt to ""', () => {
      const fav: Favorite = { itemId: "x", itemType: "COLLECTION", metadata: {} };
      expect(favoriteToCollectionCardData(fav).createdAt).toBe("");
    });

    it('should default updatedAt to ""', () => {
      const fav: Favorite = { itemId: "x", itemType: "COLLECTION", metadata: {} };
      expect(favoriteToCollectionCardData(fav).updatedAt).toBe("");
    });

    it("should default itemCount to 0", () => {
      const fav: Favorite = { itemId: "x", itemType: "COLLECTION", metadata: {} };
      expect(favoriteToCollectionCardData(fav).itemCount).toBe(0);
    });

    it("should default childCollectionCount to 0", () => {
      const fav: Favorite = { itemId: "x", itemType: "COLLECTION", metadata: {} };
      expect(favoriteToCollectionCardData(fav).childCollectionCount).toBe(0);
    });

    it("should default isPublic to false", () => {
      const fav: Favorite = { itemId: "x", itemType: "COLLECTION", metadata: {} };
      expect(favoriteToCollectionCardData(fav).isPublic).toBe(false);
    });
  });

  describe("type derivation from isPublic", () => {
    it('should derive type="public" when isPublic is true', () => {
      const fav: Favorite = {
        itemId: "col-pub",
        itemType: "COLLECTION",
        metadata: { isPublic: true },
      };

      const result = favoriteToCollectionCardData(fav);

      expect(result.type).toBe("public");
      expect(result.isPublic).toBe(true);
    });

    it('should derive type="private" when isPublic is false', () => {
      const fav: Favorite = {
        itemId: "col-priv",
        itemType: "COLLECTION",
        metadata: { isPublic: false },
      };

      const result = favoriteToCollectionCardData(fav);

      expect(result.type).toBe("private");
      expect(result.isPublic).toBe(false);
    });

    it('should derive type="private" when isPublic is missing from metadata', () => {
      const fav: Favorite = {
        itemId: "col-missing-pub",
        itemType: "COLLECTION",
        metadata: { name: "No isPublic field" },
      };

      const result = favoriteToCollectionCardData(fav);

      expect(result.type).toBe("private");
      expect(result.isPublic).toBe(false);
    });

    it('should derive type="private" when metadata is undefined', () => {
      const fav: Favorite = {
        itemId: "col-no-meta-type",
        itemType: "COLLECTION",
      };

      const result = favoriteToCollectionCardData(fav);

      expect(result.type).toBe("private");
      expect(result.isPublic).toBe(false);
    });
  });
});

import { describe, it, expect } from "vitest";
import { API_ENDPOINTS } from "./endpoints";

describe("API_ENDPOINTS", () => {
  describe("static endpoints", () => {
    it("has correct search endpoint", () => {
      expect(API_ENDPOINTS.SEARCH).toBe("/search");
    });

    it("has correct connectors endpoint", () => {
      expect(API_ENDPOINTS.CONNECTORS).toBe("/connectors");
    });

    it("has correct pipelines endpoint", () => {
      expect(API_ENDPOINTS.PIPELINES).toBe("/pipelines");
    });
  });

  describe("ASSETS dynamic endpoints", () => {
    it("generates correct GET url", () => {
      expect(API_ENDPOINTS.ASSETS.GET("asset-123")).toBe("/assets/asset-123");
    });

    it("generates correct DELETE url", () => {
      expect(API_ENDPOINTS.ASSETS.DELETE("asset-456")).toBe("/assets/asset-456");
    });

    it("generates correct RENAME url", () => {
      expect(API_ENDPOINTS.ASSETS.RENAME("asset-789")).toBe("/assets/asset-789/rename");
    });

    it("generates correct BULK_DOWNLOAD_DELETE url", () => {
      expect(API_ENDPOINTS.ASSETS.BULK_DOWNLOAD_DELETE("job-1")).toBe(
        "/assets/download/bulk/job-1"
      );
    });

    it("generates correct BATCH_DELETE_CANCEL url", () => {
      expect(API_ENDPOINTS.ASSETS.BATCH_DELETE_CANCEL("job-2")).toBe("/assets/batch/job-2/cancel");
    });
  });

  describe("PIPELINE_EXECUTION_RETRY dynamic endpoints", () => {
    it("generates FROM_CURRENT url", () => {
      expect(API_ENDPOINTS.PIPELINE_EXECUTION_RETRY.FROM_CURRENT("exec-1")).toBe(
        "/pipelines/executions/exec-1/retry?type=from_current"
      );
    });

    it("generates FROM_START url", () => {
      expect(API_ENDPOINTS.PIPELINE_EXECUTION_RETRY.FROM_START("exec-2")).toBe(
        "/pipelines/executions/exec-2/retry?type=from_start"
      );
    });

    it("generates BASE url", () => {
      expect(API_ENDPOINTS.PIPELINE_EXECUTION_RETRY.BASE("exec-3")).toBe(
        "/pipelines/executions/exec-3/retry"
      );
    });
  });

  describe("GROUPS dynamic endpoints", () => {
    it("generates GET url", () => {
      expect(API_ENDPOINTS.GROUPS.GET("grp-1")).toBe("/groups/grp-1");
    });

    it("generates ADD_MEMBERS url", () => {
      expect(API_ENDPOINTS.GROUPS.ADD_MEMBERS("grp-1")).toBe("/groups/grp-1/members");
    });

    it("generates REMOVE_MEMBER url", () => {
      expect(API_ENDPOINTS.GROUPS.REMOVE_MEMBER("grp-1", "user-1")).toBe(
        "/groups/grp-1/members/user-1"
      );
    });
  });

  describe("COLLECTIONS dynamic endpoints", () => {
    it("generates GET url", () => {
      expect(API_ENDPOINTS.COLLECTIONS.GET("col-1")).toBe("/collections/col-1");
    });

    it("generates ANCESTORS url", () => {
      expect(API_ENDPOINTS.COLLECTIONS.ANCESTORS("col-1")).toBe("/collections/col-1/ancestors");
    });

    it("generates SHARE url", () => {
      expect(API_ENDPOINTS.COLLECTIONS.SHARE("col-1")).toBe("/collections/col-1/share");
    });

    it("generates UNSHARE url", () => {
      expect(API_ENDPOINTS.COLLECTIONS.UNSHARE("col-1", "user-1")).toBe(
        "/collections/col-1/share/user-1"
      );
    });

    it("generates ITEMS url", () => {
      expect(API_ENDPOINTS.COLLECTIONS.ITEMS("col-1")).toBe("/collections/col-1/items");
    });

    it("generates THUMBNAIL url", () => {
      expect(API_ENDPOINTS.COLLECTIONS.THUMBNAIL("col-1")).toBe("/collections/col-1/thumbnail");
    });
  });

  describe("DASHBOARD dynamic endpoints", () => {
    it("generates PRESET url", () => {
      expect(API_ENDPOINTS.DASHBOARD.PRESET("preset-1")).toBe("/dashboard/presets/preset-1");
    });

    it("generates PRESET_APPLY url", () => {
      expect(API_ENDPOINTS.DASHBOARD.PRESET_APPLY("preset-1")).toBe(
        "/dashboard/presets/preset-1/apply"
      );
    });
  });

  describe("API_KEYS dynamic endpoints", () => {
    it("generates GET url", () => {
      expect(API_ENDPOINTS.API_KEYS.GET("key-1")).toBe("/settings/api-keys/key-1");
    });

    it("generates PERMISSIONS url", () => {
      expect(API_ENDPOINTS.API_KEYS.PERMISSIONS("key-1")).toBe(
        "/settings/api-keys/key-1/permissions"
      );
    });
  });

  describe("COLLECTION_TYPES dynamic endpoints", () => {
    it("generates MIGRATE url", () => {
      expect(API_ENDPOINTS.COLLECTION_TYPES.MIGRATE("ct-1")).toBe(
        "/settings/collection-types/ct-1/migrate"
      );
    });
  });

  describe("FAVORITES dynamic endpoints", () => {
    it("generates DELETE url", () => {
      expect(API_ENDPOINTS.FAVORITES.DELETE("asset", "item-1")).toBe(
        "/users/favorites/asset/item-1"
      );
    });
  });
});

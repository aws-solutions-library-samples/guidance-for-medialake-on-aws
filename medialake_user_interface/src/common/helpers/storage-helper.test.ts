import { describe, it, expect, beforeEach } from "vitest";
import { StorageHelper } from "./storage-helper";

beforeEach(() => {
  localStorage.clear();
});

describe("StorageHelper", () => {
  describe("theme", () => {
    it("defaults to light", () => {
      expect(StorageHelper.getTheme()).toBe("light");
    });

    it("stores and retrieves dark theme", () => {
      StorageHelper.setTheme("dark");
      expect(StorageHelper.getTheme()).toBe("dark");
    });

    it("stores and retrieves light theme", () => {
      StorageHelper.setTheme("light");
      expect(StorageHelper.getTheme()).toBe("light");
    });
  });

  describe("navigation panel state", () => {
    it("returns default collapsed state", () => {
      const state = StorageHelper.getNavigationPanelState();
      expect(state.collapsed).toBe(true);
    });

    it("merges partial state updates", () => {
      StorageHelper.setNavigationPanelState({ collapsed: false });
      const state = StorageHelper.getNavigationPanelState();
      expect(state.collapsed).toBe(false);
    });
  });

  describe("token", () => {
    it("returns null when no token set", () => {
      expect(StorageHelper.getToken()).toBeNull();
    });

    it("stores and retrieves token", () => {
      StorageHelper.setToken("abc123");
      expect(StorageHelper.getToken()).toBe("abc123");
    });

    it("clears token", () => {
      StorageHelper.setToken("abc123");
      StorageHelper.clearToken();
      expect(StorageHelper.getToken()).toBeNull();
    });
  });

  describe("refresh token", () => {
    it("stores and retrieves refresh token", () => {
      StorageHelper.setRefreshToken("refresh-xyz");
      expect(StorageHelper.getRefreshToken()).toBe("refresh-xyz");
    });

    it("clears refresh token", () => {
      StorageHelper.setRefreshToken("refresh-xyz");
      StorageHelper.clearRefreshToken();
      expect(StorageHelper.getRefreshToken()).toBeNull();
    });
  });

  describe("username", () => {
    it("stores and retrieves username", () => {
      StorageHelper.setUsername("testuser");
      expect(StorageHelper.getUsername()).toBe("testuser");
    });

    it("clears username", () => {
      StorageHelper.setUsername("testuser");
      StorageHelper.clearUsername();
      expect(StorageHelper.getUsername()).toBeNull();
    });
  });

  describe("AWS config", () => {
    it("returns null when no config set", () => {
      expect(StorageHelper.getAwsConfig()).toBeNull();
    });

    it("stores and retrieves config object", () => {
      const config = { region: "us-east-1", bucket: "test" };
      StorageHelper.setAwsConfig(config);
      expect(StorageHelper.getAwsConfig()).toEqual(config);
    });

    it("clears config", () => {
      StorageHelper.setAwsConfig({ region: "us-east-1" });
      StorageHelper.clearAwsConfig();
      expect(StorageHelper.getAwsConfig()).toBeNull();
    });
  });
});

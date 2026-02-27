import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useViewPreferences } from "./useViewPreferences";

describe("useViewPreferences", () => {
  it("returns default values", () => {
    const { result } = renderHook(() => useViewPreferences());
    expect(result.current.viewMode).toBe("card");
    expect(result.current.cardSize).toBe("medium");
    expect(result.current.aspectRatio).toBe("square");
    expect(result.current.thumbnailScale).toBe("fit");
    expect(result.current.showMetadata).toBe(true);
    expect(result.current.groupByType).toBe(false);
    expect(result.current.sorting).toEqual([]);
  });

  it("accepts custom initial values", () => {
    const { result } = renderHook(() =>
      useViewPreferences({
        initialViewMode: "table",
        initialCardSize: "large",
        initialAspectRatio: "horizontal",
        initialThumbnailScale: "fill",
        initialShowMetadata: false,
        initialGroupByType: true,
      })
    );
    expect(result.current.viewMode).toBe("table");
    expect(result.current.cardSize).toBe("large");
    expect(result.current.aspectRatio).toBe("horizontal");
    expect(result.current.thumbnailScale).toBe("fill");
    expect(result.current.showMetadata).toBe(false);
    expect(result.current.groupByType).toBe(true);
  });

  it("handleCardSizeChange updates card size", () => {
    const { result } = renderHook(() => useViewPreferences());
    act(() => result.current.handleCardSizeChange("large"));
    expect(result.current.cardSize).toBe("large");
  });

  it("handleAspectRatioChange updates aspect ratio", () => {
    const { result } = renderHook(() => useViewPreferences());
    act(() => result.current.handleAspectRatioChange("horizontal"));
    expect(result.current.aspectRatio).toBe("horizontal");
  });

  it("handleThumbnailScaleChange updates scale", () => {
    const { result } = renderHook(() => useViewPreferences());
    act(() => result.current.handleThumbnailScaleChange("fill"));
    expect(result.current.thumbnailScale).toBe("fill");
  });

  it("handleShowMetadataChange updates metadata visibility", () => {
    const { result } = renderHook(() => useViewPreferences());
    act(() => result.current.handleShowMetadataChange(false));
    expect(result.current.showMetadata).toBe(false);
  });

  it("handleGroupByTypeChange updates grouping", () => {
    const { result } = renderHook(() => useViewPreferences());
    act(() => result.current.handleGroupByTypeChange(true));
    expect(result.current.groupByType).toBe(true);
  });

  it("handleSortChange updates sorting", () => {
    const { result } = renderHook(() => useViewPreferences());
    const newSorting = [{ id: "name", desc: false }];
    act(() => result.current.handleSortChange(newSorting));
    expect(result.current.sorting).toEqual(newSorting);
  });

  it("handleCardFieldToggle toggles field visibility", () => {
    const { result } = renderHook(() => useViewPreferences());
    const initialVisible = result.current.cardFields.find((f) => f.id === "type")?.visible;
    act(() => result.current.handleCardFieldToggle("type"));
    const afterToggle = result.current.cardFields.find((f) => f.id === "type")?.visible;
    expect(afterToggle).toBe(!initialVisible);
  });

  it("provides default card fields", () => {
    const { result } = renderHook(() => useViewPreferences());
    expect(result.current.cardFields.length).toBeGreaterThan(0);
    expect(result.current.cardFields[0].id).toBe("name");
  });
});

import { describe, it, expect } from "vitest";
import { createPlaceholderSvg, createTimecodePlaceholder } from "./placeholderSvg";

describe("createPlaceholderSvg", () => {
  it("returns a data URL", () => {
    const result = createPlaceholderSvg();
    expect(result).toMatch(/^data:image\/svg\+xml;base64,/);
  });

  it("uses default dimensions", () => {
    const result = createPlaceholderSvg();
    const svg = atob(result.split(",")[1]);
    expect(svg).toContain('width="300"');
    expect(svg).toContain('height="200"');
  });

  it("uses custom dimensions", () => {
    const result = createPlaceholderSvg(640, 480);
    const svg = atob(result.split(",")[1]);
    expect(svg).toContain('width="640"');
    expect(svg).toContain('height="480"');
  });

  it("includes custom text", () => {
    const result = createPlaceholderSvg(300, 200, "Hello");
    const svg = atob(result.split(",")[1]);
    expect(svg).toContain("Hello");
  });

  it("uses custom colors", () => {
    const result = createPlaceholderSvg(300, 200, "Test", "#FF0000", "#00FF00");
    const svg = atob(result.split(",")[1]);
    expect(svg).toContain("#FF0000");
    expect(svg).toContain("#00FF00");
  });
});

describe("createTimecodePlaceholder", () => {
  it("creates a small placeholder with timecode text", () => {
    const result = createTimecodePlaceholder("01:23:45");
    const svg = atob(result.split(",")[1]);
    expect(svg).toContain('width="100"');
    expect(svg).toContain('height="56"');
    expect(svg).toContain("01:23:45");
  });

  it("uses black background and white text", () => {
    const result = createTimecodePlaceholder("00:00");
    const svg = atob(result.split(",")[1]);
    expect(svg).toContain("#000000");
    expect(svg).toContain("#FFFFFF");
  });
});

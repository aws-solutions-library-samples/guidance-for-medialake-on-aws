import { describe, expect, it } from "vitest";
import { resolvePlayableMediaUrl } from "./playableMedia";

const proxy = (url: unknown) => ({
  DerivedRepresentations: [{ Purpose: "proxy", URL: url }],
});

describe("resolvePlayableMediaUrl", () => {
  it("returns the proxy representation's URL", () => {
    expect(resolvePlayableMediaUrl(proxy("https://cdn.example.test/videos/clip_proxy.mp4"))).toBe(
      "https://cdn.example.test/videos/clip_proxy.mp4"
    );
  });

  it("accepts http as well as https", () => {
    expect(resolvePlayableMediaUrl(proxy("http://cdn.example.test/a.mp4"))).toBe(
      "http://cdn.example.test/a.mp4"
    );
  });

  it("returns undefined when no proxy has been generated yet", () => {
    // The normal transient state for a freshly ingested asset: the thumbnail
    // exists but the proxy pipeline has not finished.
    const asset = {
      DerivedRepresentations: [{ Purpose: "thumbnail", URL: "https://cdn.example.test/thumb.jpg" }],
    };
    expect(resolvePlayableMediaUrl(asset)).toBeUndefined();
  });

  it("does not fall back to a bare S3 object key", () => {
    // The original defect: an object key is not a URL, and handing it to the
    // player produced "invalid url" where the media should be.
    const asset = {
      DerivedRepresentations: [],
      DigitalSourceAsset: {
        MainRepresentation: {
          StorageInfo: {
            PrimaryLocation: { ObjectKey: { FullPath: "videos/Agent_327.mp4" } },
          },
        },
      },
    };
    expect(resolvePlayableMediaUrl(asset)).toBeUndefined();
  });

  it("rejects a relative path even when it is on the proxy rep", () => {
    expect(resolvePlayableMediaUrl(proxy("videos/clip_proxy.mp4"))).toBeUndefined();
    expect(resolvePlayableMediaUrl(proxy("/videos/clip_proxy.mp4"))).toBeUndefined();
  });

  it("rejects an s3:// URI, which a media element cannot load", () => {
    expect(resolvePlayableMediaUrl(proxy("s3://bucket/videos/clip.mp4"))).toBeUndefined();
  });

  it("ignores a blank or whitespace-only URL", () => {
    expect(resolvePlayableMediaUrl(proxy(""))).toBeUndefined();
    expect(resolvePlayableMediaUrl(proxy("   "))).toBeUndefined();
  });

  it("ignores a non-string URL", () => {
    expect(resolvePlayableMediaUrl(proxy(null))).toBeUndefined();
    expect(resolvePlayableMediaUrl(proxy(42))).toBeUndefined();
  });

  it("skips a proxy rep with no usable URL and keeps looking", () => {
    const asset = {
      DerivedRepresentations: [
        { Purpose: "proxy", URL: "" },
        { Purpose: "proxy", URL: "https://cdn.example.test/second_proxy.mp4" },
      ],
    };
    expect(resolvePlayableMediaUrl(asset)).toBe("https://cdn.example.test/second_proxy.mp4");
  });

  it("tolerates a malformed asset without throwing", () => {
    expect(resolvePlayableMediaUrl(undefined)).toBeUndefined();
    expect(resolvePlayableMediaUrl(null)).toBeUndefined();
    expect(resolvePlayableMediaUrl({})).toBeUndefined();
    expect(resolvePlayableMediaUrl({ DerivedRepresentations: "nope" })).toBeUndefined();
    expect(resolvePlayableMediaUrl({ DerivedRepresentations: [null] })).toBeUndefined();
  });
});

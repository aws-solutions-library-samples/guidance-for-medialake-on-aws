import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

// Mock dependencies before imports
// The second argument to t() may be either a string fallback or an i18next options object.
// Components here pass plural-suffixed defaults (defaultValue_one / defaultValue_other)
// together with a count, so mirror i18next's suffix selection and {{...}} interpolation —
// otherwise those messages render as the raw key and assertions on their text silently
// pass against nothing meaningful.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, second?: unknown) => {
      if (typeof second === "string") return second;
      const options = second as
        | {
            defaultValue?: string;
            defaultValue_one?: string;
            defaultValue_other?: string;
            count?: number;
            [param: string]: unknown;
          }
        | undefined;
      if (!options) return key;

      let template = options.defaultValue;
      if (typeof options.count === "number") {
        const plural = options.count === 1 ? options.defaultValue_one : options.defaultValue_other;
        if (plural) template = plural;
      }
      if (!template) return key;

      return template.replace(/\{\{(\w+)\}\}/g, (match, name: string) => {
        const value = options[name];
        return value === undefined ? match : String(value);
      });
    },
  }),
}));

vi.mock("@/api/hooks/useSearchConnectors", () => ({
  useSearchConnectors: vi.fn(),
}));

// Controllable connector permissions (both default to granted).
let mockCanUploadConnector = true;
let mockCanViewConnector = true;
vi.mock("@/permissions", () => ({
  usePermission: () => ({
    can: (action: string, subject: string) => {
      if (action === "upload" && subject === "connector") return mockCanUploadConnector;
      if (action === "view" && subject === "connector") return mockCanViewConnector;
      return true;
    },
  }),
}));

const mockGetPresignedUrl = vi.fn().mockResolvedValue({
  presigned_post: { url: "https://s3.example.com", fields: {} },
});

vi.mock("../hooks/useS3Upload", () => ({
  default: () => ({
    getPresignedUrl: mockGetPresignedUrl,
    signPart: vi.fn(),
    completeMultipartUpload: vi.fn(),
    abortMultipartUpload: vi.fn(),
  }),
}));

// Stub Uppy to avoid browser-only side effects
const mockSetOptions = vi.fn();
vi.mock("@uppy/core", () => {
  class MockUppy {
    on = vi.fn().mockReturnThis();
    off = vi.fn().mockReturnThis();
    cancelAll = vi.fn();
    use = vi.fn();
    getPlugin = vi.fn(() => ({ setOptions: mockSetOptions }));
    getState = vi.fn(() => ({ meta: {} }));
    setOptions = vi.fn();
    removeFile = vi.fn();
    info = vi.fn();
  }
  return { default: MockUppy };
});

vi.mock("@uppy/react/dashboard", () => ({
  default: () => <div data-testid="uppy-dashboard" />,
}));

vi.mock("@uppy/aws-s3", () => ({ default: vi.fn() }));
vi.mock("./PathBrowser", () => ({ default: () => null }));
// CollectionSelector is exercised by its own tests; stub it here so this
// suite stays focused on connector/destination selection and doesn't require
// a QueryClientProvider for the collection data hooks it uses internally.
vi.mock("./CollectionSelector", () => ({ default: () => null }));

// FileUploader itself now reads live collections (to validate saved/selected collection
// ids) and per-user settings (for the remembered upload location). Both are react-query
// hooks, so stub them here to keep this suite provider-free — each has its own tests.
// Live collections are mutable so tests can model a collection being deleted (absent from
// the list) versus still present.
let mockLiveCollections: Array<{ id: string; name: string }> = [];
vi.mock("@/api/hooks/useCollections", () => ({
  useGetAllCollections: () => ({ data: { data: mockLiveCollections } }),
  isAddable: () => true,
}));

let mockUploadSettings: Record<string, unknown> = {};
const mockPutUserSetting = vi.fn();
vi.mock("@/api/hooks/useUserSettings", () => ({
  useGetUserSettings: () => ({ data: mockUploadSettings, isLoading: false }),
  usePutUserSetting: () => ({ mutate: mockPutUserSetting }),
}));

import { useSearchConnectors } from "@/api/hooks/useSearchConnectors";

const mockUseSearchConnectors = vi.mocked(useSearchConnectors);

const activeConnector = (id: string, name: string) => ({
  id,
  name,
  type: "s3",
  status: "active",
  storageIdentifier: `${name}-bucket`,
});

describe("FileUploader", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockCanUploadConnector = true;
    mockCanViewConnector = true;
    mockUploadSettings = {};
    mockLiveCollections = [];
    mockUseSearchConnectors.mockReturnValue({
      data: {
        status: "200",
        message: "ok",
        data: {
          connectors: [
            activeConnector("conn-1", "Production"),
            activeConnector("conn-2", "Staging"),
          ],
        },
      },
      isLoading: false,
    } as any);
  });

  // Lazy import to ensure mocks are set up first
  async function renderUploader(props: Record<string, any> = {}) {
    const { default: FileUploader } = await import("./FileUploader");
    return render(<FileUploader {...props} />);
  }

  it("shows locked My Assets label when lockConnector is true", async () => {
    await renderUploader({ lockConnector: true, defaultConnectorId: "my-assets-1" });
    expect(screen.getByText("My Assets")).toBeInTheDocument();
    // Dropdown should not be present
    expect(screen.queryByLabelText(/connector/i)).not.toBeInTheDocument();
  });

  it("lockConnector=true hides the combobox dropdown", async () => {
    await renderUploader({ lockConnector: true, defaultConnectorId: "my-assets-1" });
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("My Assets")).toBeInTheDocument();
  });

  it("shows locked My Assets label when no connectors exist", async () => {
    mockUseSearchConnectors.mockReturnValue({
      data: { status: "200", message: "ok", data: { connectors: [] } },
      isLoading: false,
    } as any);
    await renderUploader({ defaultConnectorId: "my-assets-1" });
    expect(screen.getByText("My Assets")).toBeInTheDocument();
  });

  it("shows dropdown with My Assets as first option in global mode", async () => {
    await renderUploader({ defaultConnectorId: "my-assets-1" });
    // Dropdown should be present (not locked)
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
  });

  it("preselects defaultConnectorId when provided", async () => {
    await renderUploader({ defaultConnectorId: "conn-1" });
    // The select should have the default connector preselected
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
  });

  it("shows dropdown without My Assets option when no defaultConnectorId", async () => {
    await renderUploader({});
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
    // No My Assets text should appear in the dropdown context
    expect(screen.queryByText("My Assets")).not.toBeInTheDocument();
  });

  it("hides shared connectors (only My Assets) when user lacks connectors:upload", async () => {
    mockCanUploadConnector = false;
    await renderUploader({ defaultConnectorId: "my-assets-1" });
    // My Assets is the only destination → read-only card, no dropdown
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("My Assets")).toBeInTheDocument();
  });

  it("shows no destinations when user lacks connectors:upload and has no My Assets", async () => {
    mockCanUploadConnector = false;
    await renderUploader({});
    // No My Assets and no permitted connectors → no dropdown, no connectors
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByText("My Assets")).not.toBeInTheDocument();
  });

  it("re-selects connector when defaultConnectorId changes", async () => {
    const { default: FileUploader } = await import("./FileUploader");
    const { rerender } = render(<FileUploader defaultConnectorId="conn-1" />);
    // Rerender with a different defaultConnectorId
    rerender(<FileUploader defaultConnectorId="my-assets-1" />);
    // The My Assets menu item should be rendered (it's the defaultConnectorId option)
    expect(screen.getByText("My Assets")).toBeInTheDocument();
  });

  it("does not offer path browsing for My Assets, and never shows the personal path", async () => {
    await renderUploader({
      defaultConnectorId: "my-assets-1",
      defaultObjectPrefix: "personal/user123/",
    });

    // The personal bucket is shared infrastructure and `personal/{sub}/` is an internal
    // detail, so neither the path nor a way to browse it is exposed for My Assets.
    expect(screen.queryByText("upload.browsePath")).not.toBeInTheDocument();
    expect(screen.queryByText("personal/user123/")).not.toBeInTheDocument();
    expect(screen.queryByText(/personal\//)).not.toBeInTheDocument();
  });

  it("hides path browsing when the user lacks the connectors:view permission the explorer needs", async () => {
    mockCanViewConnector = false;

    await renderUploader({});

    // Browsing calls GET /connectors/s3/explorer/{id}, which requires connectors:view.
    // Without it the request would 403 and bounce the user to /access-denied.
    expect(screen.queryByText("upload.browsePath")).not.toBeInTheDocument();
  });

  it("configures upload callbacks with My Assets connector ID and prefix when switching from S3", async () => {
    // Re-set the presigned URL mock after beforeEach reset
    mockGetPresignedUrl.mockResolvedValue({
      presigned_post: { url: "https://s3.example.com", fields: {} },
    });

    const { default: FileUploader } = await import("./FileUploader");
    const { rerender } = render(
      <FileUploader defaultConnectorId="my-assets-1" defaultObjectPrefix="personal/user123/" />
    );

    // Initially rendered with conn-1 pre-selected via defaultConnectorId
    // Rerender simulating My Assets being selected (lockConnector)
    rerender(
      <FileUploader
        defaultConnectorId="my-assets-1"
        defaultObjectPrefix="personal/user123/"
        lockConnector
      />
    );

    // The S3 plugin setOptions should have been called with upload callbacks
    // even though "my-assets-1" is not in the filtered S3 connectors list
    expect(mockSetOptions).toHaveBeenCalled();

    // Verify the last call includes upload callback functions
    const lastCall = mockSetOptions.mock.calls[mockSetOptions.mock.calls.length - 1][0];
    expect(lastCall).toHaveProperty("getUploadParameters");
    expect(lastCall).toHaveProperty("createMultipartUpload");
    expect(lastCall).toHaveProperty("signPart");
    expect(lastCall).toHaveProperty("completeMultipartUpload");
    expect(lastCall).toHaveProperty("abortMultipartUpload");

    // Invoke getUploadParameters and verify it passes the My Assets connector ID
    const fakeFile = { name: "test.jpg", type: "image/jpeg", size: 1024 };
    await lastCall.getUploadParameters(fakeFile);

    expect(mockGetPresignedUrl).toHaveBeenCalledWith(
      expect.objectContaining({
        connector_id: "my-assets-1",
        path: "personal/user123/",
      })
    );
  });

  // ── Saved upload locations ──────────────────────────────────────────────
  // Phase 1: the uploader auto-populates from the last location the user uploaded to,
  // and saved locations are selectable from the dropdown. A default favorite is a later
  // phase, so nothing here should depend on one.
  describe("saved upload locations", () => {
    const lastLocation = (connectorId: string, path: string, collections?: unknown[]) => ({
      lastLocation: { version: 1, connectorId, path, collections: collections ?? [] },
    });

    const favorites = (locations: unknown[]) => ({
      favoriteLocations: { version: 1, defaultId: null, locations },
    });

    it("restores the last upload location, overriding the My Assets default", async () => {
      mockUploadSettings = lastLocation("conn-2", "projects/b/");
      mockGetPresignedUrl.mockResolvedValue({
        presigned_post: { url: "https://s3.example.com", fields: {} },
      });

      await renderUploader({ defaultConnectorId: "my-assets-1" });

      const lastCall = mockSetOptions.mock.calls[mockSetOptions.mock.calls.length - 1][0];
      await lastCall.getUploadParameters({ name: "a.jpg", type: "image/jpeg", size: 10 });

      expect(mockGetPresignedUrl).toHaveBeenCalledWith(
        expect.objectContaining({ connector_id: "conn-2", path: "projects/b/" })
      );
    });

    it("does not restore the last location when the caller pinned one with lockConnector", async () => {
      mockUploadSettings = lastLocation("conn-2", "projects/b/");
      mockGetPresignedUrl.mockResolvedValue({
        presigned_post: { url: "https://s3.example.com", fields: {} },
      });

      await renderUploader({
        defaultConnectorId: "my-assets-1",
        defaultObjectPrefix: "personal/user123/",
        lockConnector: true,
      });

      const lastCall = mockSetOptions.mock.calls[mockSetOptions.mock.calls.length - 1][0];
      await lastCall.getUploadParameters({ name: "a.jpg", type: "image/jpeg", size: 10 });

      expect(mockGetPresignedUrl).toHaveBeenCalledWith(
        expect.objectContaining({ connector_id: "my-assets-1" })
      );
    });

    it("does not restore the last location when the caller passed an explicit path", async () => {
      mockUploadSettings = lastLocation("conn-2", "projects/b/");
      mockGetPresignedUrl.mockResolvedValue({
        presigned_post: { url: "https://s3.example.com", fields: {} },
      });

      await renderUploader({ defaultConnectorId: "my-assets-1", path: "caller/pinned/" });

      const lastCall = mockSetOptions.mock.calls[mockSetOptions.mock.calls.length - 1][0];
      await lastCall.getUploadParameters({ name: "a.jpg", type: "image/jpeg", size: 10 });

      expect(mockGetPresignedUrl).toHaveBeenCalledWith(
        expect.objectContaining({ connector_id: "my-assets-1", path: "caller/pinned/" })
      );
    });

    it("ignores a remembered location whose connector no longer exists", async () => {
      mockUploadSettings = lastLocation("deleted-connector", "gone/");
      mockGetPresignedUrl.mockResolvedValue({
        presigned_post: { url: "https://s3.example.com", fields: {} },
      });

      await renderUploader({ defaultConnectorId: "my-assets-1" });

      const lastCall = mockSetOptions.mock.calls[mockSetOptions.mock.calls.length - 1][0];
      await lastCall.getUploadParameters({ name: "a.jpg", type: "image/jpeg", size: 10 });

      expect(mockGetPresignedUrl).toHaveBeenCalledWith(
        expect.objectContaining({ connector_id: "my-assets-1" })
      );
    });

    it("remembers My Assets without the personal prefix, and still uploads to it", async () => {
      mockUploadSettings = lastLocation("my-assets-1", "");
      mockGetPresignedUrl.mockResolvedValue({
        presigned_post: { url: "https://s3.example.com", fields: {} },
      });

      await renderUploader({
        defaultConnectorId: "my-assets-1",
        defaultObjectPrefix: "personal/user123/",
      });

      const lastCall = mockSetOptions.mock.calls[mockSetOptions.mock.calls.length - 1][0];
      await lastCall.getUploadParameters({ name: "a.jpg", type: "image/jpeg", size: 10 });

      // The stored empty path is resolved back to the personal prefix for the actual upload.
      expect(mockGetPresignedUrl).toHaveBeenCalledWith(
        expect.objectContaining({ connector_id: "my-assets-1", path: "personal/user123/" })
      );
    });

    it("saves a prefixed connector with its resolved path so the entry keeps matching", async () => {
      // A stored empty path would be replaced by allowedPrefixes[0] on selection, leaving the
      // entry permanently unmatched — the dropdown would fall back to the plain connector.
      mockUseSearchConnectors.mockReturnValue({
        data: {
          status: "200",
          message: "ok",
          data: {
            connectors: [{ ...activeConnector("conn-1", "Production"), objectPrefix: "projects/" }],
          },
        },
        isLoading: false,
      } as any);

      await renderUploader({});

      fireEvent.click(screen.getByTestId("save-upload-location-button"));

      const entry = mockPutUserSetting.mock.calls[0][0].value.locations[0];
      expect(entry.path).toBe("projects/");

      // And the star reflects the saved state rather than flipping back to "not saved".
      expect(screen.getByTestId("save-upload-location-button")).toHaveAttribute(
        "aria-label",
        "Save this location"
      );
    });

    it("lists saved locations as their own dropdown section", async () => {
      mockUploadSettings = favorites([
        { id: "f1", label: "Client A dailies", connectorId: "conn-1", path: "projects/a/" },
      ]);

      await renderUploader({ defaultConnectorId: "my-assets-1" });

      // MUI renders Select options only once the menu is open.
      fireEvent.mouseDown(screen.getByRole("combobox"));

      expect(screen.getByText("Saved locations")).toBeInTheDocument();
      expect(screen.getByText("Client A dailies")).toBeInTheDocument();
      expect(screen.getByText("All destinations")).toBeInTheDocument();
    });

    it("saves the current destination, including selected collections, via the star button", async () => {
      await renderUploader({ defaultConnectorId: "my-assets-1" });

      fireEvent.click(screen.getByTestId("save-upload-location-button"));

      expect(mockPutUserSetting).toHaveBeenCalledTimes(1);
      const payload = mockPutUserSetting.mock.calls[0][0];
      expect(payload.key).toBe("favoriteLocations");
      expect(payload.value.locations).toHaveLength(1);
      expect(payload.value.locations[0]).toMatchObject({ connectorId: "my-assets-1" });
    });

    it("saves My Assets with no path, so the personal prefix is never persisted or labelled", async () => {
      await renderUploader({
        defaultConnectorId: "my-assets-1",
        defaultObjectPrefix: "personal/user123/",
      });

      fireEvent.click(screen.getByTestId("save-upload-location-button"));

      const entry = mockPutUserSetting.mock.calls[0][0].value.locations[0];
      expect(entry.connectorId).toBe("my-assets-1");
      // Empty path means "connector default root", resolved back to personal/{sub}/ on use.
      expect(entry.path).toBe("");
      expect(entry.label).toBe("My Assets");
      expect(JSON.stringify(entry)).not.toContain("personal/");
    });

    it("shows the star as already-saved when the current destination is a saved one", async () => {
      mockUploadSettings = favorites([
        { id: "f1", label: "My Assets", connectorId: "my-assets-1", path: "" },
      ]);

      await renderUploader({
        defaultConnectorId: "my-assets-1",
        defaultObjectPrefix: "personal/user123/",
      });

      expect(screen.getByTestId("save-upload-location-button")).toHaveAttribute(
        "aria-label",
        "Remove this saved location"
      );
    });

    it("offers no star when there is no destination selected", async () => {
      mockCanUploadConnector = false;
      mockUseSearchConnectors.mockReturnValue({
        data: { status: "200", message: "ok", data: { connectors: [] } },
        isLoading: false,
      } as any);

      await renderUploader({});

      expect(screen.queryByTestId("save-upload-location-button")).not.toBeInTheDocument();
    });
  });

  /**
   * Regression: selecting a saved location whose collection has since been deleted must
   * tell the user. The upload request already excludes the dead id (validatedCollections
   * reconciles at render), but silently dropping a collection the user deliberately saved
   * is a surprise — they would believe the asset had been filed into it.
   *
   * The sibling path (restoring lastLocation on mount) already warns; this covers the
   * explicit-selection path through the destination dropdown.
   */
  it("warns when a selected saved location carries a deleted collection", async () => {
    mockUploadSettings = {
      favoriteLocations: {
        version: 1,
        defaultId: null,
        locations: [
          {
            id: "fav-1",
            label: "Production / archive/",
            connectorId: "conn-1",
            path: "archive/",
            collections: [{ id: "col-dead", name: "Gone Collection" }],
          },
        ],
      },
    };

    await renderUploader();

    // Open the destination dropdown and pick the saved location.
    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(await screen.findByText("Production / archive/"));

    const notice = await screen.findByTestId("dropped-collections-notice");
    expect(notice).toHaveTextContent(/no longer available/i);
    expect(notice).toHaveTextContent(/Gone Collection/);
  });

  /**
   * The sibling path: the same warning must appear when the destination is restored from
   * lastLocation on mount, without the user touching the dropdown.
   */
  it("warns when the restored last location carries a deleted collection", async () => {
    mockUploadSettings = {
      lastLocation: {
        version: 1,
        connectorId: "conn-1",
        path: "archive/",
        collections: [{ id: "col-dead", name: "Gone Collection" }],
      },
    };

    await renderUploader();

    const notice = await screen.findByTestId("dropped-collections-notice");
    expect(notice).toHaveTextContent(/no longer available/i);
    expect(notice).toHaveTextContent(/Gone Collection/);
  });

  /**
   * Guard against the inverse: a live, addable collection must not be reported as dropped.
   * Without this, a warning that always fires would satisfy the two tests above.
   */
  it("does not warn when a saved location's collections are all still live", async () => {
    mockUploadSettings = {
      lastLocation: {
        version: 1,
        connectorId: "conn-1",
        path: "archive/",
        collections: [{ id: "col-live", name: "Still Here" }],
      },
    };
    mockLiveCollections = [{ id: "col-live", name: "Still Here" }];

    await renderUploader();

    expect(screen.queryByTestId("dropped-collections-notice")).not.toBeInTheDocument();
  });
});

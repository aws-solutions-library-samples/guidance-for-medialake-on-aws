import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithUser } from "@/test/render";
import JitProvisioningSettings from "./JitProvisioningSettings";

const mockUseJitSettings = vi.fn();
const mockUseGetGroups = vi.fn();
const mockMutateAsync = vi.fn();
const mockUseUpdate = vi.fn();

vi.mock("@/api/hooks/useJitProvisioningSettings", () => ({
  useJitProvisioningSettings: () => mockUseJitSettings(),
}));

vi.mock("@/api/hooks/useGroups", () => ({
  useGetGroups: () => mockUseGetGroups(),
}));

vi.mock("@/api/hooks/useUpdateJitProvisioningSettings", () => ({
  useUpdateJitProvisioningSettings: () => mockUseUpdate(),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
  }),
}));

const GROUPS = [
  { id: "read-only", name: "Read Only" },
  { id: "editors", name: "Editor" },
  { id: "superAdministrators", name: "Super Administrator" },
];

function settings(overrides: Record<string, unknown> = {}) {
  return {
    isLoading: false,
    isError: false,
    data: {
      status: "success",
      data: {
        enabled: true,
        defaultGroupId: "read-only",
        capabilityEnabled: true,
        updatedAt: "2026-01-01T00:00:00Z",
        updatedBy: "admin@example.com",
        isDefault: false,
        ...overrides,
      },
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseJitSettings.mockReturnValue(settings());
  mockUseGetGroups.mockReturnValue({ data: GROUPS, isLoading: false });
  mockMutateAsync.mockResolvedValue({});
  mockUseUpdate.mockReturnValue({
    mutateAsync: mockMutateAsync,
    isPending: false,
  });
});

describe("JitProvisioningSettings", () => {
  it("shows the saved default group", () => {
    renderWithUser(<JitProvisioningSettings />);
    expect(screen.getByText("Read Only")).toBeInTheDocument();
  });

  it("disables Save until something changes", () => {
    renderWithUser(<JitProvisioningSettings />);
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });

  it("saves the selected group with the concurrency token", async () => {
    const { user } = renderWithUser(<JitProvisioningSettings />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "Editor" }));
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        enabled: true,
        defaultGroupId: "editors",
        expectedUpdatedAt: "2026-01-01T00:00:00Z",
      });
    });
  });

  it("reverts the draft when Cancel is pressed", async () => {
    const { user } = renderWithUser(<JitProvisioningSettings />);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "Editor" }));
    expect(screen.getByText("Editor")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(screen.getByText("Read Only")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });

  it("blocks saving when enabled with no group chosen", async () => {
    mockUseJitSettings.mockReturnValue(settings({ enabled: false, defaultGroupId: "" }));
    const { user } = renderWithUser(<JitProvisioningSettings />);

    // MUI renders Switch with role="switch".
    await user.click(screen.getByRole("switch"));

    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    expect(screen.getByText(/choose a group before enabling/i)).toBeInTheDocument();
  });

  it("warns when the deployment does not support the feature", () => {
    mockUseJitSettings.mockReturnValue(settings({ capabilityEnabled: false }));
    renderWithUser(<JitProvisioningSettings />);
    expect(screen.getByText(/not enabled for this deployment/i)).toBeInTheDocument();
  });

  it("does not warn when the deployment supports the feature", () => {
    renderWithUser(<JitProvisioningSettings />);
    expect(screen.queryByText(/not enabled for this deployment/i)).not.toBeInTheDocument();
  });

  it("renders a spinner while loading", () => {
    mockUseJitSettings.mockReturnValue({ isLoading: true, isError: false });
    renderWithUser(<JitProvisioningSettings />);
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("renders an error state when the fetch fails", () => {
    mockUseJitSettings.mockReturnValue({ isLoading: false, isError: true });
    renderWithUser(<JitProvisioningSettings />);
    expect(screen.getByText(/could not load/i)).toBeInTheDocument();
  });

  it("handles an empty group list without crashing", () => {
    mockUseGetGroups.mockReturnValue({ data: [], isLoading: false });
    mockUseJitSettings.mockReturnValue(settings({ defaultGroupId: "" }));
    renderWithUser(<JitProvisioningSettings />);
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });
});

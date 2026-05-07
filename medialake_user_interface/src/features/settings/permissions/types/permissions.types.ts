export type PermissionType =
  | "view"
  | "create"
  | "edit"
  | "delete"
  | "upload"
  | "download"
  | "publish";

export type AreaId =
  | "dashboard"
  | "default_dashboard"
  | "assets"
  | "collections"
  | "pipelines"
  | "connectors"
  | "users"
  | "groups"
  | "settings"
  | "integrations";

export interface PermissionArea {
  id: AreaId;
  label: string;
  description: string;
}

// Matrix: Record<AreaId, Record<PermissionType, boolean>>
export type PermissionMatrix = Record<string, Record<string, boolean>>;

export const PERMISSION_TYPES: { id: PermissionType; label: string }[] = [
  { id: "view", label: "View" },
  { id: "create", label: "Create" },
  { id: "edit", label: "Edit" },
  { id: "delete", label: "Delete" },
  { id: "upload", label: "Upload" },
  { id: "download", label: "Download" },
  { id: "publish", label: "Publish" },
];

// Define which permissions apply to which areas
export const PERMISSION_APPLICABILITY: Record<PermissionType, AreaId[] | "all"> = {
  view: [
    "dashboard",
    "default_dashboard",
    "assets",
    "collections",
    "connectors",
    "pipelines",
    "users",
    "groups",
    "settings",
    "integrations",
  ],
  create: [
    "dashboard",
    "default_dashboard",
    "assets",
    "collections",
    "connectors",
    "pipelines",
    "users",
    "groups",
    "settings",
    "integrations",
  ],
  edit: "all",
  delete: [
    "dashboard",
    "default_dashboard",
    "assets",
    "collections",
    "connectors",
    "pipelines",
    "users",
    "groups",
    "settings",
    "integrations",
  ],
  upload: ["assets"],
  download: ["assets"],
  publish: ["assets"],
};

// Helper function to check if a permission applies to an area
export const isPermissionApplicable = (
  permissionType: PermissionType,
  areaId: AreaId | string
): boolean => {
  const applicability = PERMISSION_APPLICABILITY[permissionType];
  if (applicability === "all") return true;
  return applicability.includes(areaId as AreaId);
};

export const AREAS: PermissionArea[] = [
  { id: "dashboard", label: "Dashboard", description: "Overview and widgets" },
  {
    id: "default_dashboard",
    label: "Default Dashboard",
    description: "System default dashboard configuration",
  },
  { id: "assets", label: "Assets", description: "Digital asset management" },
  { id: "collections", label: "Collections", description: "Asset collections and organization" },
  { id: "connectors", label: "Connectors", description: "External storage integrations" },
  { id: "pipelines", label: "Pipelines", description: "Data processing workflows" },
  { id: "users", label: "Users", description: "User account management" },
  { id: "groups", label: "Groups", description: "Group management" },
  { id: "settings", label: "Settings", description: "System configuration" },
  { id: "integrations", label: "Integrations", description: "Third-party integrations" },
];

// Color palette for comparison view
export const GROUP_COLORS = [
  {
    bg: "rgba(33, 150, 243, 0.04)",
    border: "rgba(33, 150, 243, 0.2)",
    header: "rgba(33, 150, 243, 0.1)",
    text: "primary.main",
    headerHex: "#bbdefb",
  },
  {
    bg: "rgba(156, 39, 176, 0.04)",
    border: "rgba(156, 39, 176, 0.2)",
    header: "rgba(156, 39, 176, 0.1)",
    text: "secondary.main",
    headerHex: "#e1bee7",
  },
  {
    bg: "rgba(0, 150, 136, 0.04)",
    border: "rgba(0, 150, 136, 0.2)",
    header: "rgba(0, 150, 136, 0.1)",
    text: "success.main",
    headerHex: "#b2dfdb",
  },
];

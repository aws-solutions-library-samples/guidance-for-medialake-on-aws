import { StorageHelper } from "../common/helpers/storage-helper";

export interface PermissionDebugInfo {
  hasToken: boolean;
  tokenExpired: boolean;
  tokenExp?: number;
  currentTime: number;
  timeUntilExpiry?: number;
  userGroups?: string[];
  customPermissions?: string[];
}

/**
 * Get comprehensive debug information about the current permission state
 */
export function getPermissionDebugInfo(): PermissionDebugInfo {
  const info: PermissionDebugInfo = {
    hasToken: false,
    tokenExpired: false,
    currentTime: Math.floor(Date.now() / 1000),
  };

  try {
    const token = StorageHelper.getToken();

    if (!token) {
      console.log("Debug: No token found in storage");
      return info;
    }

    info.hasToken = true;

    // Parse token
    const tokenParts = token.split(".");
    if (tokenParts.length === 3) {
      const payload = JSON.parse(atob(tokenParts[1]));

      info.tokenExp = payload.exp;
      info.userGroups = payload["cognito:groups"] || [];

      if (payload["custom:permissions"]) {
        try {
          info.customPermissions = JSON.parse(payload["custom:permissions"]);
        } catch (e) {
          console.error("Failed to parse custom permissions for debug:", e);
          info.customPermissions = [];
        }
      }

      if (info.tokenExp) {
        info.timeUntilExpiry = info.tokenExp - info.currentTime;
        info.tokenExpired = info.timeUntilExpiry <= 0;
      }
    }
  } catch (error) {
    console.error("Error getting permission debug info:", error);
  }

  return info;
}

/**
 * Log detailed permission debug information
 */
export function logPermissionDebugInfo(): void {
  const info = getPermissionDebugInfo();

  console.log("=== Permission Debug Info ===");
  console.log("Has token:", info.hasToken);

  if (info.hasToken) {
    console.log("Token expired:", info.tokenExpired);
    if (info.timeUntilExpiry !== undefined) {
      console.log("Time until expiry (seconds):", info.timeUntilExpiry);
      console.log(
        "Time until expiry (minutes):",
        Math.round(info.timeUntilExpiry / 60),
      );
    }
    console.log("User groups:", info.userGroups);
    console.log("Custom permissions:", info.customPermissions);
  }

  console.log("Current time (unix):", info.currentTime);
  console.log("=============================");
}

/**
 * Check if token is expiring within the next N seconds
 */
export function isTokenExpiringSoon(bufferSeconds: number = 300): boolean {
  const info = getPermissionDebugInfo();

  if (!info.hasToken || !info.timeUntilExpiry) {
    return true; // Assume expiring if we can't determine
  }

  return info.timeUntilExpiry <= bufferSeconds;
}

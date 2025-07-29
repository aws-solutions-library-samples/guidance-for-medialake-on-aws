// src/permissions/utils/ability-factory.ts
import { AbilityBuilder, Ability } from "@casl/ability";
import { AppAbility, Actions, Subjects } from "../types/ability.types";
import { Permission, User } from "../types/permission.types";

/**
 * Creates a CASL ability instance based on user information and permissions
 *
 * @param user User information including groups
 * @param permissions Array of permissions from the API
 * @returns CASL ability instance
 */
export function defineAbilityFor(
  user: User,
  permissions: Permission[],
): AppAbility {
  const { can, cannot, build } = new AbilityBuilder<AppAbility>(Ability as any);

  if (!user) {
    // Default: no permissions
    return build();
  }

  // Check for custom permissions from JWT token first
  if (
    (user as any).customPermissions &&
    Array.isArray((user as any).customPermissions)
  ) {
    const customPermissions = (user as any).customPermissions as string[];
    console.log("Using custom permissions from JWT:", customPermissions);

    // Parse custom permissions (format: "resource:action")
    customPermissions.forEach((permission) => {
      const [resource, action] = permission.split(":");
      console.log(`Processing permission: ${resource}:${action}`);

      // Handle admin level permissions (full access)
      // if (action === 'admin' || action === 'full') {
      //   console.log(`Processing admin/full permission: ${resource}:${action}`);
      //   switch (resource) {
      //     case 'asset':
      //     case 'assets':
      //       can('manage', 'asset');
      //       can('view', 'asset');
      //       can('create', 'asset');
      //       can('edit', 'asset');
      //       can('delete', 'asset');
      //       break;
      //     case 'pipeline':
      //     case 'pipelines':
      //       can('manage', 'pipeline');
      //       can('view', 'pipeline');
      //       can('create', 'pipeline');
      //       can('edit', 'pipeline');
      //       can('delete', 'pipeline');
      //       break;
      //     case 'integration':
      //     case 'integrations':
      //       can('manage', 'integration');
      //       can('view', 'integration');
      //       can('create', 'integration');
      //       can('edit', 'integration');
      //       can('delete', 'integration');
      //       break;
      //     case 'settings':
      //       can('manage', 'settings');
      //       can('view', 'settings');
      //       // Settings sub-permissions
      //       can('manage', 'user');
      //       can('manage', 'group');
      //       can('manage', 'permission-set');
      //       can('manage', 'connector');
      //       can('manage', 'region');
      //       can('manage', 'system-settings');
      //       break;
      //     case 'admin':
      //       // Full admin access to everything
      //       can('manage', 'all');

      //       // Explicitly grant access to all resources for admin
      //       can('manage', 'asset');
      //       can('manage', 'pipeline');
      //       can('manage', 'connector');
      //       can('manage', 'user');
      //       can('manage', 'group');
      //       can('manage', 'settings');
      //       can('manage', 'permission-set');
      //       can('manage', 'integration');
      //       can('manage', 'region');
      //       can('manage', 'system-settings');

      //       // Also grant view permissions for sidebar visibility
      //       can('view', 'asset');
      //       can('view', 'pipeline');
      //       can('view', 'connector');
      //       can('view', 'user');
      //       can('view', 'group');
      //       can('view', 'settings');
      //       can('view', 'permission-set');
      //       can('view', 'integration');
      //       can('view', 'region');
      //       can('view', 'system-settings');

      //       // Grant settings.* permissions for sidebar visibility
      //       can('view', 'settings.users' as any);
      //       can('view', 'settings.connectors' as any);
      //       can('view', 'settings.integrations' as any);
      //       can('view', 'settings.permissions' as any);
      //       can('view', 'settings.system' as any);

      //       // Grant manage permissions for settings.* resources
      //       can('manage', 'settings.users' as any);
      //       can('manage', 'settings.connectors' as any);
      //       can('manage', 'settings.integrations' as any);
      //       can('manage', 'settings.permissions' as any);
      //       can('manage', 'settings.system' as any);

      //       console.log('Admin full permission granted - explicitly adding settings.* permissions');
      //       break;
      //   }
      // }
      // Handle specific action permissions
      if (action !== "full") {
        // Skip 'full' as it's handled in the admin section
        // Handle settings.* format (e.g., settings.users:edit) FIRST
        if (resource.startsWith("settings.")) {
          const [_, settingsResource] = resource.split(".");

          // Map settings resources to CASL subjects
          const settingsMapping: { [key: string]: string } = {
            users: "user",
            system: "settings", // Changed from system-settings to generic settings
            permissions: "permission-set",
            connectors: "connector",
            integrations: "integration",
            groups: "group",
            regions: "region",
          };

          const caslResource =
            settingsMapping[settingsResource] || settingsResource;

          // Enable view on the parent settings menu
          can("view", "settings");

          // Enable view on the specific settings resource
          can("view", caslResource as Subjects);

          // Also enable view on the settings.* resource for sidebar menu visibility
          can("view", `settings.${settingsResource}` as any);

          // For users specifically, ensure the menu is visible and route access works
          if (settingsResource === "users") {
            console.log(
              "Explicitly granting permissions on user and group for settings.users",
            );
            can("view", "user" as Subjects);
            can("view", "group" as Subjects);
            // Grant manage on group for the users-groups route
            if (action === "edit") {
              can("manage", "group" as Subjects);
            }
          }

          // For groups specifically, ensure the menu is visible
          if (settingsResource === "groups") {
            console.log(
              "Explicitly granting view permission on group for settings.groups",
            );
            can("view", "group" as Subjects);
          }

          // For connectors specifically, ensure the menu is visible
          if (settingsResource === "connectors") {
            console.log(
              "Explicitly granting view permission on connector for settings.connectors",
            );
            can("view", "connector" as Subjects);
          }

          // For integrations specifically, ensure the menu is visible
          if (settingsResource === "integrations") {
            console.log(
              "Explicitly granting view permission on integration for settings.integrations",
            );
            can("view", "integration" as Subjects);
          }

          // Enable the specific action on the settings resource
          console.log(
            `Granting ${action} permission on ${caslResource} (from settings.${settingsResource})`,
          );
          can(action as Actions, caslResource as Subjects);

          // For edit permissions, also grant view and manage permissions to ensure route access
          if (action === "edit") {
            console.log(
              `Also granting view and manage permissions on ${caslResource} for menu visibility and route access`,
            );
            can("view", caslResource as Subjects);
            can("manage", caslResource as Subjects);
            can("view", `settings.${settingsResource}` as any);
          }

          // For manage permissions, also grant view permission
          if (action === "manage") {
            console.log(
              `Also granting view permission on ${caslResource} for menu visibility`,
            );
            can("view", caslResource as Subjects);
            can("view", `settings.${settingsResource}` as any);
          }
        }
        // Handle standard resource:action format
        else if (
          action === "view" ||
          action === "edit" ||
          action === "delete" ||
          action === "create" ||
          action === "full"
        ) {
          // Map plural resource names to singular for CASL
          const resourceMapping: { [key: string]: string } = {
            assets: "asset",
            pipelines: "pipeline",
            collections: "collection",
            integrations: "integration",
            users: "user",
            groups: "group",
            connectors: "connector",
            permissions: "permission-set",
            systems: "settings",
          };

          const caslResource = resourceMapping[resource] || resource;
          const caslAction = action === "full" ? "manage" : action;

          console.log(`Granting ${caslAction} permission on ${caslResource}`);
          can(caslAction as Actions, caslResource as Subjects);

          // For view permissions, always add the ability to view the parent resource
          if (action === "view" && resource === "pipelines") {
            can("view", "pipeline");
          }
        }
      }
    });

    // Return early if using custom permissions
    return build();
  }

  // Fallback to group-based permissions
  // Users in the "administrators" group can manage all settings and resources
  if (user.groups && user.groups.includes("administrators")) {
    // Settings permissions
    can("manage", "settings");
    can("view", "settings");

    // User and group management permissions
    can("manage", "user");
    can("manage", "group");

    // Permission management
    can("manage", "permission-set");

    // Resource management
    can("manage", "connector");
    can("manage", "pipeline");
    can("create", "pipeline");
    can("edit", "pipeline");

    // Additional specific permissions for settings

    // System settings
    can("manage", "settings");

    // Connector settings
    can("create", "connector");
    can("edit", "connector");
    can("delete", "connector");

    // User settings
    can("create", "user");
    can("edit", "user");
    can("disable", "user");
    can("delete", "user");

    // Permission settings
    can("create", "permission-set");
    can("edit", "permission-set");
    can("delete", "permission-set");

    // Integration settings
    can("create", "integration");
    can("edit", "integration");
    can("delete", "integration");

    console.log("Added administrator permissions for user:", user.username);
  }

  // If no permissions are provided, just use the group-based permissions
  if (!permissions || permissions.length === 0) {
    console.log("No permissions provided, using only group-based permissions");
    return build();
  }

  // Process permissions based on principal type
  const userPermissions = permissions.filter(
    (p) => p.principalType === "USER" && p.principalId === user.id,
  );

  // Get group permissions for groups the user belongs to
  const groupPermissions = permissions.filter(
    (p) =>
      p.principalType === "GROUP" &&
      user.groups &&
      user.groups.includes(p.principalId),
  );

  // Apply permissions in the correct order to implement "most explicit deny wins" rule

  // First apply all "Allow" permissions (group permissions first, then user-specific ones)
  [...groupPermissions, ...userPermissions]
    .filter((p) => p.effect === "Allow")
    .forEach((permission) => {
      if (permission.conditions) {
        can(
          permission.action as Actions,
          permission.resource as Subjects,
          permission.conditions,
        );
      } else {
        can(permission.action as Actions, permission.resource as Subjects);
      }
    });

  // Then apply all "Deny" permissions (these will override allows)
  [...groupPermissions, ...userPermissions]
    .filter((p) => p.effect === "Deny")
    .forEach((permission) => {
      if (permission.conditions) {
        cannot(
          permission.action as Actions,
          permission.resource as Subjects,
          permission.conditions,
        );
      } else {
        cannot(permission.action as Actions, permission.resource as Subjects);
      }
    });

  return build();
}

/**
 * Transforms permission sets from the API into the format expected by CASL
 *
 * @param permissionSets Permission sets from the API
 * @returns Array of permissions in the format expected by CASL
 */
export function transformPermissionSets(permissionSets: any[]): Permission[] {
  if (!permissionSets || !Array.isArray(permissionSets)) {
    return [];
  }

  // Flatten permission sets into a single array of permissions
  const permissions: Permission[] = [];

  permissionSets.forEach((ps) => {
    if (ps.permissions && Array.isArray(ps.permissions)) {
      permissions.push(...ps.permissions);
    }
  });

  return permissions;
}

/**
 * Extract user information from JWT token claims
 *
 * @param claims JWT token claims
 * @returns User object with id, username, and groups
 */
export function extractUserFromClaims(claims: any): User {
  if (!claims) {
    console.log("extractUserFromClaims: No claims provided");
    return { id: "", username: "", groups: [] };
  }

  console.log("=== Extracting User from Claims ===");
  console.log("claims.sub:", claims.sub);
  console.log('claims["cognito:username"]:', claims["cognito:username"]);
  console.log('claims["cognito:groups"]:', claims["cognito:groups"]);
  console.log("claims.email:", claims.email);
  console.log("================================");

  const user = {
    id: claims.sub || "",
    username: claims["cognito:username"] || claims.email || claims.sub || "",
    groups: claims["cognito:groups"] || [],
  };

  console.log("Extracted user object:", user);
  return user;
}

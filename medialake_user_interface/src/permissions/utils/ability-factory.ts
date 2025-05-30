// src/permissions/utils/ability-factory.ts
import { AbilityBuilder, Ability } from '@casl/ability';
import { AppAbility, Actions, Subjects } from '../types/ability.types';
import { Permission, User } from '../types/permission.types';

/**
 * Creates a CASL ability instance based on user information and permissions
 * 
 * @param user User information including groups
 * @param permissions Array of permissions from the API
 * @returns CASL ability instance
 */
export function defineAbilityFor(user: User, permissions: Permission[]): AppAbility {
  const { can, cannot, build } = new AbilityBuilder<AppAbility>(Ability as any);
  
  if (!user) {
    // Default: no permissions
    return build();
  }

  // Check for custom permissions from JWT token first
  if ((user as any).customPermissions && Array.isArray((user as any).customPermissions)) {
    const customPermissions = (user as any).customPermissions as string[];
    console.log('Using custom permissions from JWT:', customPermissions);
    
    // Parse custom permissions (format: "resource:level")
    customPermissions.forEach(permission => {
      const [resource, level] = permission.split(':');
      
      if (level === 'admin') {
        // Admin level - full manage permissions
        switch (resource) {
          case 'asset':
            can('manage', 'asset');
            can('view', 'asset');
            can('create', 'asset');
            can('edit', 'asset');
            can('delete', 'asset');
            break;
          case 'pipeline':
            can('manage', 'pipeline');
            can('view', 'pipeline');
            can('create', 'pipeline');
            can('edit', 'pipeline');
            can('delete', 'pipeline');
            break;
          case 'integration':
            can('manage', 'integration');
            can('view', 'integration');
            can('create', 'integration');
            can('edit', 'integration');
            can('delete', 'integration');
            break;
          case 'settings':
            can('manage', 'settings');
            can('view', 'settings');
            // Settings sub-permissions
            can('manage', 'user');
            can('manage', 'group');
            can('manage', 'permission-set');
            can('manage', 'connector');
            can('manage', 'region');
            can('manage', 'system-settings');
            break;
        }
      }
    });
    
    // Return early if using custom permissions
    return build();
  }

  // Fallback to group-based permissions
  // Users in the "administrators" group can manage all settings and resources
  if (user.groups && user.groups.includes('administrators')) {
    // Settings permissions
    can('manage', 'settings');
    can('view', 'settings');
    
    // User and group management permissions
    can('manage', 'user');
    can('manage', 'group');
    
    // Permission management
    can('manage', 'permission-set');
    
    // Resource management
    can('manage', 'connector');
    can('manage', 'pipeline');
    can('create', 'pipeline');
    can('edit', 'pipeline');
    
    console.log('Added administrator permissions for user:', user.username);
  }

  // If no permissions are provided, just use the group-based permissions
  if (!permissions || permissions.length === 0) {
    console.log('No permissions provided, using only group-based permissions');
    return build();
  }

  // Process permissions based on principal type
  const userPermissions = permissions.filter(p => p.principalType === 'USER' && p.principalId === user.id);
  
  // Get group permissions for groups the user belongs to
  const groupPermissions = permissions.filter(p =>
    p.principalType === 'GROUP' && user.groups && user.groups.includes(p.principalId)
  );
  
  // Apply permissions in the correct order to implement "most explicit deny wins" rule
  
  // First apply all "Allow" permissions (group permissions first, then user-specific ones)
  [...groupPermissions, ...userPermissions]
    .filter(p => p.effect === 'Allow')
    .forEach(permission => {
      if (permission.conditions) {
        can(permission.action, permission.resource, permission.conditions);
      } else {
        can(permission.action, permission.resource);
      }
    });
  
  // Then apply all "Deny" permissions (these will override allows)
  [...groupPermissions, ...userPermissions]
    .filter(p => p.effect === 'Deny')
    .forEach(permission => {
      if (permission.conditions) {
        cannot(permission.action, permission.resource, permission.conditions);
      } else {
        cannot(permission.action, permission.resource);
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
  
  permissionSets.forEach(ps => {
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
    console.log('extractUserFromClaims: No claims provided');
    return { id: '', username: '', groups: [] };
  }
  
  console.log('=== Extracting User from Claims ===');
  console.log('claims.sub:', claims.sub);
  console.log('claims["cognito:username"]:', claims['cognito:username']);
  console.log('claims["cognito:groups"]:', claims['cognito:groups']);
  console.log('claims.email:', claims.email);
  console.log('================================');
  
  const user = {
    id: claims.sub || '',
    username: claims['cognito:username'] || claims.email || claims.sub || '',
    groups: claims['cognito:groups'] || [],
  };
  
  console.log('Extracted user object:', user);
  return user;
}
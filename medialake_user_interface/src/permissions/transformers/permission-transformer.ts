// src/permissions/transformers/permission-transformer.ts
import { Permission } from '../types/permission.types';

/**
 * Transforms permission sets from the API into the format expected by CASL
 * 
 * @param permissionSets Permission sets from the API
 * @returns Array of permissions in the format expected by CASL
 */
export function transformPermissions(permissionSets: any[]): Permission[] {
  if (!permissionSets || !Array.isArray(permissionSets)) {
    return [];
  }
  
  const permissions: Permission[] = [];
  
  permissionSets.forEach(ps => {
    // Handle different API response formats
    const permissionSet = ps.data ? ps.data : ps;
    
    if (!permissionSet || !permissionSet.permissions) {
      return;
    }
    
    // Map each permission to our internal format
    const mappedPermissions = permissionSet.permissions.map((p: any) => {
      // Extract action and resource from API format
      // The API might return them in different formats
      const action = p.action || p.actionId || '';
      const resource = p.resource || p.resourceId || '';
      
      return {
        id: p.id || `${action}-${resource}`,
        principalId: p.principalId || permissionSet.principalId || '',
        principalType: p.principalType || permissionSet.principalType || 'USER',
        action: mapAction(action),
        resource: mapResource(resource),
        effect: p.effect || 'Allow',
        conditions: p.conditions || undefined
      };
    });
    
    permissions.push(...mappedPermissions);
  });
  
  return permissions;
}

/**
 * Maps API action names to our internal action types
 * 
 * @param action Action name from API
 * @returns Mapped action name
 */
function mapAction(action: string): any {
  // Map API action names to our internal action types
  const actionMap: Record<string, string> = {
    'ViewAsset': 'view',
    'EditAsset': 'edit',
    'DeleteAsset': 'delete',
    'CreateAsset': 'create',
    'UploadAsset': 'upload',
    'DownloadAsset': 'download',
    'ShareAsset': 'share',
    'ViewPipeline': 'view',
    'EditPipeline': 'edit',
    'DeletePipeline': 'delete',
    'CreatePipeline': 'create',
    'RunPipeline': 'run',
    'ManageUsers': 'manage',
    'ManageGroups': 'manage',
    'ManagePermissions': 'manage',
    'ManageSettings': 'manage',
    // Add more mappings as needed
  };
  
  // Handle action names with method and path format (e.g., "get /assets")
  if (action.includes(' ')) {
    const [method, path] = action.split(' ');
    
    // Map HTTP methods to actions
    if (path.includes('/assets')) {
      if (method === 'get') return 'view';
      if (method === 'post') return 'create';
      if (method === 'put') return 'edit';
      if (method === 'delete') return 'delete';
    }
    
    if (path.includes('/pipelines')) {
      if (method === 'get') return 'view';
      if (method === 'post') return 'create';
      if (method === 'put') return 'edit';
      if (method === 'delete') return 'delete';
    }
    
    // Default mapping based on HTTP method
    if (method === 'get') return 'view';
    if (method === 'post') return 'create';
    if (method === 'put' || method === 'patch') return 'edit';
    if (method === 'delete') return 'delete';
  }
  
  return actionMap[action] || action;
}

/**
 * Maps API resource names to our internal resource types
 * 
 * @param resource Resource name from API
 * @returns Mapped resource name
 */
function mapResource(resource: string): any {
  // Map API resource names to our internal resource types
  const resourceMap: Record<string, string> = {
    'Asset': 'asset',
    'Pipeline': 'pipeline',
    'Connector': 'connector',
    'User': 'user',
    'Group': 'group',
    'Settings': 'settings',
    'PermissionSet': 'permission-set',
    'ApplicationConfiguration': 'all',
    // Add more mappings as needed
  };
  
  // Handle resource paths (e.g., "/assets/{id}")
  if (resource.startsWith('/')) {
    if (resource.includes('/assets')) return 'asset';
    if (resource.includes('/pipelines')) return 'pipeline';
    if (resource.includes('/connectors')) return 'connector';
    if (resource.includes('/users')) return 'user';
    if (resource.includes('/groups')) return 'group';
    if (resource.includes('/settings')) return 'settings';
    if (resource.includes('/permission-sets')) return 'permission-set';
    if (resource.includes('/permissions')) return 'permission-set';
  }
  
  return resourceMap[resource] || resource;
}
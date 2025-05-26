# CASL v5 Authorization System

This directory contains the implementation of the CASL v5 authorization system for the MediaLake React frontend. The system provides fine-grained authorization controls throughout the application, with a mix of hiding and disabling UI elements based on permissions, while ensuring good performance through caching.

## Architecture

The authorization system follows this architecture:

```
JWT Token --> Extract User & Group Info --> Ability Factory --> Permission Provider
                                              ^
Permission Sets API --> Transform Permissions -|
                                              |
Permission Provider --> usePermission Hook & Can Component --> UI Components
                    |
                    v
             Permission Cache
```

## Core Components

### Types

- `ability.types.ts`: Defines TypeScript types for CASL, including actions, subjects, and conditions.
- `permission.types.ts`: Defines permission-related types, including Permission, PermissionSet, and User.

### Utils

- `ability-factory.ts`: Creates CASL ability instances from JWT claims and permission sets.
- `permission-cache.ts`: Provides a caching mechanism for permission checks to improve performance.

### Transformers

- `permission-transformer.ts`: Transforms API permissions to the format expected by CASL.

### Context

- `permission-context.tsx`: Provides a React context provider for the ability instance.

### Hooks

- `usePermission.ts`: Provides hooks for checking permissions in components.
  - `usePermission()`: General permission checking hook.
  - `useSubjectPermission(subject)`: Hook for checking permissions on a specific subject.

### Components

- `Can.tsx`: Component for conditional rendering based on permissions.
- `PermissionGuard.tsx`: Components for protecting routes based on permissions.
  - `PermissionGuard`: Basic component for protecting content.
  - `withPermission`: Higher-order component for creating a route guard.
  - `RoutePermissionGuard`: Component for protecting routes in a router configuration.

## Usage

### Setting Up

1. Wrap your application with the `PermissionProvider`:

```tsx
import { PermissionProvider } from './permissions';

function App() {
  return (
    <PermissionProvider>
      <YourApp />
    </PermissionProvider>
  );
}
```

### Conditional Rendering

Use the `Can` component to conditionally render UI elements based on permissions:

```tsx
import { Can } from './permissions';

function AssetActions({ asset }) {
  return (
    <div>
      <Can I="view" a="asset" subject={asset}>
        <button>View Details</button>
      </Can>
      
      <Can I="edit" a="asset" subject={asset}>
        <button>Edit</button>
      </Can>
      
      <Can I="delete" a="asset" subject={asset} passThrough>
        {(allowed) => (
          <button 
            disabled={!allowed}
            title={!allowed ? "You don't have permission to delete this asset" : ""}
          >
            Delete
          </button>
        )}
      </Can>
    </div>
  );
}
```

### Using Hooks

Use the `usePermission` hook to check permissions in your components:

```tsx
import { usePermission } from './permissions';

function AssetHeader({ asset }) {
  const { can } = usePermission();
  
  const canShare = can('share', 'asset', asset);
  
  return (
    <div>
      <h1>{asset.name}</h1>
      
      {canShare && (
        <button>Share</button>
      )}
    </div>
  );
}
```

### Protecting Routes

Use the `PermissionGuard` component to protect routes:

```tsx
import { PermissionGuard } from './permissions';

function SettingsPage() {
  return (
    <div>
      <h1>Settings</h1>
      
      <PermissionGuard action="manage" subject="user">
        <div>
          <h2>User Management</h2>
          <p>Manage users and permissions</p>
        </div>
      </PermissionGuard>
    </div>
  );
}
```

Or use the `RoutePermissionGuard` component in your router configuration:

```tsx
import { RoutePermissionGuard } from './permissions';

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<div>Home Page</div>} />
      
      <Route 
        path="/assets" 
        element={
          <RoutePermissionGuard 
            permission={{ action: 'view', subject: 'asset' }}
            element={<div>Assets Page</div>}
          />
        } 
      />
    </Routes>
  );
}
```

## Best Practices

1. **Use the Can component for conditional rendering**: This provides a clear and declarative way to show or hide UI elements based on permissions.

2. **Use the passThrough prop for disabled states**: When you want to show a UI element but disable it based on permissions, use the `passThrough` prop with a render function.

3. **Use the usePermission hook for complex logic**: When you need to check permissions in more complex scenarios, use the `usePermission` hook.

4. **Use the PermissionGuard component for protecting routes**: This ensures that users can only access routes they have permission to view.

5. **Keep permission checks close to the UI**: Place permission checks as close as possible to the UI elements they protect to make the code more maintainable.

## Examples

See the `examples/integration-example.tsx` file for a complete example of how to integrate the CASL v5 authorization system into your application.
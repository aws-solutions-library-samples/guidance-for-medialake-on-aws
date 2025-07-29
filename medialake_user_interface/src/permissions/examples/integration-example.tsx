// src/permissions/examples/integration-example.tsx
import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { PermissionProvider } from "../context/permission-context";
import { Can } from "../components/Can";
import {
  PermissionGuard,
  RoutePermissionGuard,
} from "../components/PermissionGuard";
import { usePermission } from "../hooks/usePermission";

/**
 * Example component showing how to use the Can component for conditional rendering
 */
function AssetActions({ asset }: { asset: any }) {
  return (
    <div className="asset-actions">
      {/* Show View button only if user has 'view' permission on 'asset' */}
      <Can I="view" a="asset" subject={asset}>
        <button>View Details</button>
      </Can>

      {/* Show Edit button only if user has 'edit' permission on 'asset' */}
      <Can I="edit" a="asset" subject={asset}>
        <button>Edit</button>
      </Can>

      {/* Show Delete button but disable it if user doesn't have 'delete' permission */}
      <Can I="delete" a="asset" subject={asset} passThrough>
        {(allowed) => (
          <button
            disabled={!allowed}
            title={
              !allowed ? "You don't have permission to delete this asset" : ""
            }
          >
            Delete
          </button>
        )}
      </Can>
    </div>
  );
}

/**
 * Example component showing how to use the usePermission hook
 */
function AssetHeader({ asset }: { asset: any }) {
  const { can } = usePermission();

  // Check if user can share the asset
  const canShare = can("share", "asset", asset);

  return (
    <div className="asset-header">
      <h1>{asset.name}</h1>

      {/* Conditionally render share button based on permissions */}
      {canShare && <button>Share</button>}
    </div>
  );
}

/**
 * Example component showing how to use the PermissionGuard component
 */
function SettingsPage() {
  return (
    <div className="settings-page">
      <h1>Settings</h1>

      {/* Only show user management section if user has 'manage' permission on 'user' */}
      <PermissionGuard action="manage" subject="user">
        <div className="settings-section">
          <h2>User Management</h2>
          <p>Manage users and permissions</p>
        </div>
      </PermissionGuard>

      {/* Only show group management section if user has 'manage' permission on 'group' */}
      <PermissionGuard action="manage" subject="group">
        <div className="settings-section">
          <h2>Group Management</h2>
          <p>Manage groups and memberships</p>
        </div>
      </PermissionGuard>
    </div>
  );
}

/**
 * Example showing how to protect routes with permissions
 */
function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<div>Home Page</div>} />
      <Route path="/login" element={<div>Login Page</div>} />

      {/* Protected routes using RoutePermissionGuard */}
      <Route
        path="/assets"
        element={
          <RoutePermissionGuard
            permission={{ action: "view", subject: "asset" }}
            element={<div>Assets Page</div>}
          />
        }
      />

      <Route
        path="/settings"
        element={
          <RoutePermissionGuard
            permission={{ action: "manage", subject: "settings" }}
            element={<SettingsPage />}
          />
        }
      />

      {/* Access denied page */}
      <Route path="/access-denied" element={<div>Access Denied</div>} />
    </Routes>
  );
}

/**
 * Example App component showing how to integrate the PermissionProvider
 */
export function ExampleApp() {
  return (
    <BrowserRouter>
      <PermissionProvider>
        <div className="app">
          <header>
            <h1>MediaLake</h1>
          </header>
          <main>
            <AppRoutes />
          </main>
        </div>
      </PermissionProvider>
    </BrowserRouter>
  );
}

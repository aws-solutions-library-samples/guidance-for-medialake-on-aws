// src/permissions/examples/integration-example.tsx
import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { PermissionProvider } from "../context/permission-context";
import { PermissionGuard, RoutePermissionGuard } from "../components/PermissionGuard";

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

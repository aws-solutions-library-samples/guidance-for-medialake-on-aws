import React from "react";
import { createBrowserRouter, Navigate, useParams } from "react-router-dom";
import AuthPage from "@/components/AuthPage";
import AppLayout from "@/components/AppLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RouteErrorBoundary } from "@/shared/ui/errors";
import { RoutePermissionGuard } from "@/permissions";
import AccessDeniedPage from "@/pages/AccessDeniedPage";
import Home from "@/pages/Home";
import SearchPage from "@/pages/SearchPage";
import AssetsPage from "@/pages/AssetsPage";
import CollectionsPage from "@/pages/CollectionsPage";
import CollectionViewPage from "@/pages/CollectionViewPage";
import { CollectionGroupDetailPage } from "@/features/collection-groups";
import { S3Explorer } from "@/features/home/S3Explorer";
import { ExecutionsPage } from "@/features/executions";
import { PipelinesPage, PipelineEditorPage } from "@/features/pipelines/pages";
import ImageDetailPage from "@/pages/ImageDetailPage";
import MediaDetailPage from "@/pages/MediaDetailPage";
import ConnectorsPage from "@/pages/settings/ConnectorsPage";
import ProfilePage from "@/pages/settings/ProfilePage";
import UserManagement from "@/pages/settings/UserManagement";
import RoleManagement from "@/pages/settings/RoleManagement";
import PermissionsPage from "@/pages/settings/PermissionsPage";
import IntegrationsPage from "@/pages/settings/IntegrationsPage";
import EnvironmentsPage from "@/pages/settings/EnvironmentsPage";
import SystemSettingsPage from "@/pages/settings/SystemSettingsPage";

const S3ExplorerWrapper = () => {
  const { connectorId } = useParams<{ connectorId: string }>();
  return <S3Explorer connectorId={connectorId!} />;
};

// Redirect component for old collection-groups detail route
const CollectionGroupDetailRedirect = () => {
  const { groupId } = useParams<{ groupId: string }>();
  return <Navigate to={`/collections/groups/${groupId}`} replace />;
};

export const router = createBrowserRouter([
  {
    path: "/sign-in",
    element: <AuthPage />,
    errorElement: <RouteErrorBoundary />,
  },
  {
    path: "/access-denied",
    element: <AccessDeniedPage />,
    errorElement: <RouteErrorBoundary />,
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        index: true,
        element: <Home />,
      },
      {
        path: "search",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "asset" }}
            element={<SearchPage />}
          />
        ),
      },
      {
        path: "s3/explorer/:connectorId",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "connector" }}
            element={<S3ExplorerWrapper />}
          />
        ),
      },
      {
        path: "assets",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "asset" }}
            element={<AssetsPage />}
          />
        ),
      },

      {
        path: "collections",
        element: <CollectionsPage />,
      },
      {
        path: "collections/:id/view",
        element: <CollectionViewPage />,
      },
      {
        path: "collections/groups/:groupId",
        element: <CollectionGroupDetailPage />,
      },
      {
        // Redirect old collection-groups route to new location
        path: "collection-groups",
        element: <Navigate to="/collections?filter=groups" replace />,
      },
      {
        // Redirect old collection-groups detail route to new location
        path: "collection-groups/:groupId",
        element: <CollectionGroupDetailRedirect />,
      },
      {
        path: "executions",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "pipeline" }}
            element={<ExecutionsPage />}
          />
        ),
      },
      {
        path: "pipelines",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "pipeline" }}
            element={<PipelinesPage />}
          />
        ),
      },
      {
        path: "pipelines/new",
        element: (
          <RoutePermissionGuard
            permission={{ action: "create", subject: "pipeline" }}
            element={<PipelineEditorPage />}
          />
        ),
      },
      {
        path: "images/:id",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "asset" }}
            element={<ImageDetailPage />}
          />
        ),
      },
      {
        path: "videos/:id",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "asset" }}
            element={<MediaDetailPage />}
          />
        ),
      },
      {
        path: "audio/:id",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "asset" }}
            element={<MediaDetailPage />}
          />
        ),
      },
      {
        path: "settings/profile",
        element: <ProfilePage />,
      },
      {
        path: "settings/connectors",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "connector" }}
            element={<ConnectorsPage />}
          />
        ),
      },
      {
        path: "settings/users",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "user" }}
            element={<UserManagement />}
          />
        ),
      },
      {
        path: "settings/roles",
        element: (
          <RoutePermissionGuard
            permission={{ action: "manage", subject: "permission-set" }}
            element={<RoleManagement />}
          />
        ),
      },
      {
        path: "settings/permissions",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "permission-set" }}
            element={<PermissionsPage />}
          />
        ),
      },
      {
        path: "settings/integrations",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "integration" }}
            element={<IntegrationsPage />}
          />
        ),
      },
      {
        path: "settings/environments",
        element: (
          <RoutePermissionGuard
            permission={{ action: "manage", subject: "settings" }}
            element={<EnvironmentsPage />}
          />
        ),
      },
      {
        path: "settings/pipelines",
        element: (
          <RoutePermissionGuard
            permission={{ action: "manage", subject: "pipeline" }}
            element={<PipelinesPage />}
          />
        ),
      },
      {
        path: "settings/pipelines/new",
        element: (
          <RoutePermissionGuard
            permission={{ action: "create", subject: "pipeline" }}
            element={<PipelineEditorPage />}
          />
        ),
      },
      {
        path: "settings/pipelines/edit/:id",
        element: (
          <RoutePermissionGuard
            permission={{ action: "edit", subject: "pipeline" }}
            element={<PipelineEditorPage />}
          />
        ),
      },
      {
        path: "settings/system",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "settings" }}
            element={<SystemSettingsPage />}
          />
        ),
      },

      {
        path: "settings",
        element: <Navigate to="settings/profile" replace />,
      },
      {
        path: "*",
        element: <Navigate to="/" replace />,
        errorElement: <RouteErrorBoundary />,
      },
    ],
  },
]);

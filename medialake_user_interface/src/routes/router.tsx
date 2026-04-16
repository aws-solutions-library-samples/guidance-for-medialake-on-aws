import React, { Suspense } from "react";
import { createBrowserRouter, Navigate, useParams } from "react-router";
import { Box, CircularProgress } from "@mui/material";
import AppLayout from "@/components/AppLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RouteErrorBoundary } from "@/shared/ui/errors";
import { RoutePermissionGuard } from "@/permissions";

// Lightweight loading spinner for lazy route transitions
const RouteFallback = () => (
  <Box
    sx={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      height: "60vh",
    }}
  >
    <CircularProgress size={32} />
  </Box>
);

// Helper to wrap a lazy component with Suspense.
// Retries once on chunk load failure (e.g. after a deploy swaps hashed filenames).
function lazyLoad(factory: () => Promise<{ default: React.ComponentType<any> }>) {
  const Component = React.lazy(() =>
    factory().catch(() => {
      // First import failed — likely a stale chunk hash. Reload to pick up the new index.html.
      const reloadedKey = "chunk-reload";
      if (!sessionStorage.getItem(reloadedKey)) {
        sessionStorage.setItem(reloadedKey, "1");
        window.location.reload();
      }
      // If we already reloaded and it still fails, surface the error to the error boundary.
      return factory();
    })
  );
  return (
    <Suspense fallback={<RouteFallback />}>
      <Component />
    </Suspense>
  );
}

// Auth page is always the first page loaded — keep eager
import AuthPage from "@/components/AuthPage";
import AccessDeniedPage from "@/pages/AccessDeniedPage";
// Lazy page elements — each creates its own code-split chunk
const LazyHome = lazyLoad(() => import("@/pages/Home"));
const LazySearchPage = lazyLoad(() => import("@/pages/SearchPage"));
const LazyAssetsPage = lazyLoad(() => import("@/pages/AssetsPage"));
const LazyCollectionsPage = lazyLoad(() => import("@/pages/CollectionsPage"));
const LazyCollectionViewPage = lazyLoad(() => import("@/pages/CollectionViewPage"));
const LazyImageDetailPage = lazyLoad(() => import("@/pages/ImageDetailPage"));
const LazyMediaDetailPage = lazyLoad(() => import("@/pages/MediaDetailPage"));

// Settings pages — rarely visited
const LazyConnectorsPage = lazyLoad(() => import("@/pages/settings/ConnectorsPage"));
const LazyProfilePage = lazyLoad(() => import("@/pages/settings/ProfilePage"));
const LazyUserManagement = lazyLoad(() => import("@/pages/settings/UserManagement"));
const LazyRoleManagement = lazyLoad(() => import("@/pages/settings/RoleManagement"));
const LazyPermissionsPage = lazyLoad(() => import("@/pages/settings/PermissionsPage"));
const LazyIntegrationsPage = lazyLoad(() => import("@/pages/settings/IntegrationsPage"));
const LazyEnvironmentsPage = lazyLoad(() => import("@/pages/settings/EnvironmentsPage"));
const LazySystemSettingsPage = lazyLoad(() => import("@/pages/settings/SystemSettingsPage"));

// Heavy feature pages — pipeline editor pulls in xyflow (~150KB)
const LazyPipelinesPage = lazyLoad(() => import("@/features/pipelines/pages/PipelinesPage"));
const LazyPipelineEditorPage = lazyLoad(
  () => import("@/features/pipelines/pages/PipelineEditorPage")
);
const LazyExecutionsPage = lazyLoad(() => import("@/features/executions/pages/ExecutionsPage"));

// Collection groups
const LazyCollectionGroupDetailPage = lazyLoad(() =>
  import("@/features/collection-groups/pages/CollectionGroupDetailPage").then((m) => ({
    default: m.CollectionGroupDetailPage,
  }))
);

const S3ExplorerWrapper = () => {
  const { connectorId } = useParams<{ connectorId: string }>();
  const S3ExplorerLazy = React.lazy(() =>
    import("@/features/home/S3Explorer").then((m) => ({
      default: () => <m.S3Explorer connectorId={connectorId!} />,
    }))
  );
  return (
    <Suspense fallback={<RouteFallback />}>
      <S3ExplorerLazy />
    </Suspense>
  );
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
      { index: true, element: LazyHome },
      {
        path: "search",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "asset" }}
            element={LazySearchPage}
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
            element={LazyAssetsPage}
          />
        ),
      },
      { path: "collections", element: LazyCollectionsPage },
      { path: "collections/:id/view", element: LazyCollectionViewPage },
      { path: "collections/groups/:groupId", element: LazyCollectionGroupDetailPage },
      {
        path: "collection-groups",
        element: <Navigate to="/collections?filter=groups" replace />,
      },
      {
        path: "collection-groups/:groupId",
        element: <CollectionGroupDetailRedirect />,
      },
      {
        path: "executions",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "pipeline" }}
            element={LazyExecutionsPage}
          />
        ),
      },
      {
        path: "pipelines",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "pipeline" }}
            element={LazyPipelinesPage}
          />
        ),
      },
      {
        path: "pipelines/new",
        element: (
          <RoutePermissionGuard
            permission={{ action: "create", subject: "pipeline" }}
            element={LazyPipelineEditorPage}
          />
        ),
      },
      {
        path: "images/:id",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "asset" }}
            element={LazyImageDetailPage}
          />
        ),
      },
      {
        path: "videos/:id",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "asset" }}
            element={LazyMediaDetailPage}
          />
        ),
      },
      {
        path: "audio/:id",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "asset" }}
            element={LazyMediaDetailPage}
          />
        ),
      },
      { path: "settings/profile", element: LazyProfilePage },
      {
        path: "settings/connectors",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "connector" }}
            element={LazyConnectorsPage}
          />
        ),
      },
      {
        path: "settings/users",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "user" }}
            element={LazyUserManagement}
          />
        ),
      },
      {
        path: "settings/roles",
        element: (
          <RoutePermissionGuard
            permission={{ action: "manage", subject: "permission-set" }}
            element={LazyRoleManagement}
          />
        ),
      },
      {
        path: "settings/permissions",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "permission-set" }}
            element={LazyPermissionsPage}
          />
        ),
      },
      {
        path: "settings/integrations",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "integration" }}
            element={LazyIntegrationsPage}
          />
        ),
      },
      {
        path: "settings/environments",
        element: (
          <RoutePermissionGuard
            permission={{ action: "manage", subject: "settings" }}
            element={LazyEnvironmentsPage}
          />
        ),
      },
      {
        path: "settings/pipelines",
        element: (
          <RoutePermissionGuard
            permission={{ action: "manage", subject: "pipeline" }}
            element={LazyPipelinesPage}
          />
        ),
      },
      {
        path: "settings/pipelines/new",
        element: (
          <RoutePermissionGuard
            permission={{ action: "create", subject: "pipeline" }}
            element={LazyPipelineEditorPage}
          />
        ),
      },
      {
        path: "settings/pipelines/edit/:id",
        element: (
          <RoutePermissionGuard
            permission={{ action: "edit", subject: "pipeline" }}
            element={LazyPipelineEditorPage}
          />
        ),
      },
      {
        path: "settings/system",
        element: (
          <RoutePermissionGuard
            permission={{ action: "view", subject: "settings" }}
            element={LazySystemSettingsPage}
          />
        ),
      },
      { path: "settings", element: <Navigate to="settings/profile" replace /> },
      {
        path: "*",
        element: <Navigate to="/" replace />,
        errorElement: <RouteErrorBoundary />,
      },
    ],
  },
]);

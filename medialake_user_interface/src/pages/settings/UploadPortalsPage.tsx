import React, { useState } from "react";
import { Alert, Box, Button, Snackbar } from "@mui/material";
import { Add as AddIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { PageHeader, PageContent } from "@/components/common/layout";
import { useActionPermission } from "@/permissions/hooks/useActionPermission";
import PortalsList from "@/features/settings/upload-portals/components/PortalsList";
import TokenManager from "@/features/settings/upload-portals/components/TokenManager";
import type { PortalListItem } from "@/api/types/api.types";

/**
 * UploadPortalsPage
 *
 * List + entry-point for upload portal administration. The Create button
 * and PortalsList row-level Edit controls navigate directly to the
 * full-page portal visual editor (`/settings/upload-portals/new` and
 * `/settings/upload-portals/:id/edit`) — there is no legacy dialog path.
 *
 * TokenManager remains inline as a dialog since it is a narrowly scoped
 * secondary flow; moving it to a route is out of scope for the editor work.
 */
const UploadPortalsPage: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const createPermission = useActionPermission("manage", "settings");

  const [isTokenManagerOpen, setIsTokenManagerOpen] = useState(false);
  const [tokenManagerPortal, setTokenManagerPortal] = useState<{
    id: string;
    slug: string;
    portal?: PortalListItem;
  }>({ id: "", slug: "" });
  const [alert, setAlert] = useState<{ message: string; severity: "success" | "error" } | null>(
    null
  );

  const handleCreateClick = () => navigate("/settings/upload-portals/new");

  const handleOpenTokenManager = (
    portalId: string,
    portalSlug: string,
    portal?: PortalListItem
  ) => {
    setTokenManagerPortal({ id: portalId, slug: portalSlug, portal });
    setIsTokenManagerOpen(true);
  };

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <PageHeader
        title={t("uploadPortals.pageTitle")}
        description={t("uploadPortals.pageDescription")}
        action={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateClick}
            disabled={createPermission.disabled}
            title={createPermission.tooltip}
          >
            {t("uploadPortals.createPortal")}
          </Button>
        }
      />

      <PageContent>
        <PortalsList onOpenTokenManager={handleOpenTokenManager} />
      </PageContent>

      {isTokenManagerOpen && (
        <TokenManager
          open={isTokenManagerOpen}
          onClose={() => setIsTokenManagerOpen(false)}
          portalId={tokenManagerPortal.id}
          portalSlug={tokenManagerPortal.slug}
          portal={tokenManagerPortal.portal}
        />
      )}

      <Snackbar
        open={!!alert}
        autoHideDuration={6000}
        onClose={() => setAlert(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <Alert onClose={() => setAlert(null)} severity={alert?.severity} sx={{ width: "100%" }}>
          {alert?.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default UploadPortalsPage;

import React, { useState, useMemo } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  DialogContentText,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  Paper,
} from "@mui/material";
import { ContentCopy as CopyIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import {
  useGetPortalTokens,
  useGeneratePortalToken,
  useRevokePortalToken,
} from "@/api/hooks/usePortals";
import type { PortalListItem, PortalToken } from "@/api/types/api.types";

interface Props {
  open: boolean;
  onClose: () => void;
  portalId: string;
  portalSlug: string;
  portal?: PortalListItem;
}

const getTokenStatus = (token: PortalToken) => {
  if (token.isRevoked) return <Chip label="Revoked" size="small" color="error" />;
  if (token.expiresAt && new Date(token.expiresAt) < new Date())
    return <Chip label="Expired" size="small" color="warning" />;
  return <Chip label="Active" size="small" color="success" />;
};

const TokenManager: React.FC<Props> = ({ open, onClose, portalId, portalSlug, portal }) => {
  const { t } = useTranslation();
  const { data: response } = useGetPortalTokens(portalId);
  const { mutateAsync: generateToken, isPending: isGenerating } = useGeneratePortalToken();
  const { mutateAsync: revokeToken } = useRevokePortalToken();

  const [email, setEmail] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [generatedUrl, setGeneratedUrl] = useState("");
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null);
  const [prePopulatedParams, setPrePopulatedParams] = useState<Record<string, string>>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Backend returns flat array in data
  const tokens = response?.data ?? [];

  // Derive available pre-populated param fields from portal config
  const paramFields = useMemo(() => {
    const fields: { key: string; label: string }[] = [];
    if (portal?.metadataFields) {
      for (const f of portal.metadataFields) {
        fields.push({ key: f.label, label: f.label });
      }
    }
    if (portal?.destinations) {
      for (const dest of portal.destinations) {
        if (dest.pathSegments) {
          for (const seg of dest.pathSegments) {
            if (!fields.some((f) => f.key === seg.label)) {
              fields.push({ key: seg.label, label: seg.label });
            }
          }
        }
      }
    }
    return fields;
  }, [portal]);

  const handleParamChange = (key: string, value: string) => {
    setPrePopulatedParams((prev) => {
      const next = { ...prev };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
  };

  const handleGenerate = async () => {
    setErrorMessage(null);
    const params = Object.keys(prePopulatedParams).length > 0 ? prePopulatedParams : undefined;
    try {
      const result = await generateToken({
        portalId,
        data: {
          associatedEmail: email,
          ...(expiresAt ? { expiresAt } : {}),
          ...(params ? { prePopulatedParams: params } : {}),
        },
      });
      // Backend returns shareableUrl directly in data
      const url = result?.data?.shareableUrl;
      if (typeof url === "string" && url.length > 0) {
        setGeneratedUrl(url);
      } else {
        setErrorMessage("Token generated but no shareable URL was returned.");
      }
      setEmail("");
      setExpiresAt("");
      setPrePopulatedParams({});
    } catch (err) {
      console.error("Failed to generate token", err);
      setErrorMessage((err as Error)?.message || "Failed to generate token. Please try again.");
      // Intentionally leave email/expiresAt/prePopulatedParams untouched
      // so the user can retry without re-entering their input.
    }
  };

  const handleRevoke = async (tokenId: string) => {
    setErrorMessage(null);
    try {
      await revokeToken({ portalId, tokenId });
      setRevokeTarget(null);
    } catch (err) {
      console.error("Failed to revoke token", err);
      setErrorMessage((err as Error)?.message || "Failed to revoke token. Please try again.");
      // Keep the dialog open so the user can see the error and retry.
    }
  };

  return (
    <>
      <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
        <DialogTitle>Manage Tokens — {portalSlug}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
            {errorMessage && (
              <Typography variant="body2" color="error" role="alert">
                {errorMessage}
              </Typography>
            )}
            {/* Generate section */}
            <Box sx={{ display: "flex", gap: 1, alignItems: "flex-end" }}>
              <TextField
                label="Email"
                required
                size="small"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                sx={{ flex: 1 }}
              />
              <TextField
                label="Expiry"
                type="date"
                size="small"
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <Button
                variant="contained"
                size="small"
                onClick={handleGenerate}
                disabled={!email || isGenerating}
              >
                Generate
              </Button>
            </Box>

            {/* Pre-populated parameters */}
            {paramFields.length > 0 && (
              <Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ mb: 0.5, display: "block" }}
                >
                  Pre-populated Parameters
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                  {paramFields.map((f) => (
                    <TextField
                      key={f.key}
                      label={f.label}
                      size="small"
                      value={prePopulatedParams[f.key] ?? ""}
                      onChange={(e) => handleParamChange(f.key, e.target.value)}
                      sx={{ minWidth: 160 }}
                    />
                  ))}
                </Box>
              </Box>
            )}

            {generatedUrl && (
              <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
                <TextField
                  size="small"
                  fullWidth
                  value={generatedUrl}
                  slotProps={{ input: { readOnly: true } }}
                />
                <Tooltip title={t("uploadPortals.tokens.copyUrl")}>
                  <IconButton onClick={() => navigator.clipboard.writeText(generatedUrl)}>
                    <CopyIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            )}

            {/* Token list */}
            {tokens.length > 0 && (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Email</TableCell>
                      <TableCell>Created</TableCell>
                      <TableCell>Expiry</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {tokens.map((token) => (
                      <TableRow key={token.tokenId}>
                        <TableCell>{token.associatedEmail}</TableCell>
                        <TableCell>{new Date(token.createdAt).toLocaleDateString()}</TableCell>
                        <TableCell>
                          {token.expiresAt ? new Date(token.expiresAt).toLocaleDateString() : "—"}
                        </TableCell>
                        <TableCell>{getTokenStatus(token)}</TableCell>
                        <TableCell align="right">
                          {!token.isRevoked && (
                            <Button
                              size="small"
                              color="error"
                              onClick={() => setRevokeTarget(token.tokenId)}
                            >
                              Revoke
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {tokens.length === 0 && (
              <Typography variant="body2" color="text.secondary" textAlign="center">
                No tokens generated yet.
              </Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={revokeTarget !== null} onClose={() => setRevokeTarget(null)} maxWidth="xs">
        <DialogTitle>{t("uploadPortals.tokens.revokeToken")}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to revoke this token? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRevokeTarget(null)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={() => handleRevoke(revokeTarget!)}>
            Revoke
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default TokenManager;

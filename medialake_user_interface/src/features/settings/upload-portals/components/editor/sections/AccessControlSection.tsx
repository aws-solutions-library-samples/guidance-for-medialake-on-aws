import React, { useCallback, useMemo, useState } from "react";
import {
  Autocomplete,
  Box,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDateFns } from "@mui/x-date-pickers/AdapterDateFns";
import { useTranslation } from "react-i18next";

import { useGetGroups } from "@/api/hooks/useGroups";

import { usePortalEditorStore } from "../../../stores/usePortalEditorStore";

/**
 * Valid access-mode values used by the radio group.
 */
type AccessMode = "public" | "token-protected" | "cognito-groups";

/**
 * Stable empty-array references used as selector defaults. Returning a
 * literal `[]` inside a Zustand selector creates a new reference on every
 * render, which `useSyncExternalStore` interprets as "state changed" and
 * triggers an infinite re-render loop. Module-level constants are
 * referentially stable across renders.
 */
const EMPTY_STRING_ARRAY: string[] = [];
const EMPTY_GROUPS: string[] = [];

/**
 * AccessControlSection
 *
 * Ports the legacy `PortalFormStep2AccessControl` dialog step into an
 * accordion section for the visual editor. Preserves every control from
 * the original: access-mode radio, conditional passphrase (with show/hide
 * and `tokenBypassesPassphrase` toggle), CAPTCHA toggle, IP allowlist
 * chip/multi-line input, expiry date picker, active/inactive toggle, and
 * allowed-groups editor (Requirement 9.1).
 *
 * Store integration:
 *   Reads fields via narrow selectors from `portalData` (the loose
 *   `[key: string]: unknown` slice on the editor store) and writes them // i18n-ignore
 *   back through `updatePortalData({ ... })`. The legacy component // i18n-ignore
 *   accepted an `errors` prop that rendered field-level error text; this
 *   is intentionally omitted here — field-level errors wire up in task
 *   5.9 once `store.validate()` (task 5.6) lands.
 *
 * Date picker wrapping:
 *   The expiry `DatePicker` still needs a `LocalizationProvider` in scope,
 *   so the whole section body is wrapped in one. This mirrors the legacy
 *   step exactly and keeps the picker usable regardless of whether an
 *   ancestor provider exists.
 */
const AccessControlSection: React.FC = () => {
  const { t } = useTranslation();
  const { data: groups = [] } = useGetGroups();

  const accessMode = usePortalEditorStore(
    (s) => (s.portalData?.accessMode as AccessMode | undefined) ?? "public"
  );
  const passphrase = usePortalEditorStore(
    (s) => (s.portalData?.passphrase as string | undefined) ?? ""
  );
  const tokenBypassesPassphrase = usePortalEditorStore(
    (s) => (s.portalData?.tokenBypassesPassphrase as boolean | undefined) ?? false
  );
  const allowedGroups = usePortalEditorStore(
    (s) => (s.portalData?.allowedGroups as string[] | undefined) ?? EMPTY_GROUPS
  );
  const ipAllowlist = usePortalEditorStore(
    (s) => (s.portalData?.ipAllowlist as string[] | undefined) ?? EMPTY_STRING_ARRAY
  );
  const isActive = usePortalEditorStore(
    (s) => (s.portalData?.isActive as boolean | undefined) ?? true
  );
  const expiresAt = usePortalEditorStore(
    (s) => (s.portalData?.expiresAt as string | undefined) ?? ""
  );
  const captchaEnabled = usePortalEditorStore(
    (s) => (s.portalData?.captchaEnabled as boolean | undefined) ?? false
  );

  const updatePortalData = usePortalEditorStore((s) => s.updatePortalData);

  // Local UI-only state (not persisted): passphrase visibility and whether
  // the IP allowlist input is enabled. Mirror the legacy behavior where
  // disabling the switch clears the list.
  const [showPassword, setShowPassword] = useState(false);
  const [ipEnabled, setIpEnabled] = useState(ipAllowlist.length > 0);

  // Derive a stable list of group names. `useGetGroups` returns typed
  // objects; the legacy code fell back to `g.name || g.id || g` and we
  // preserve that behavior for resilience against partial server data.
  const groupNames = useMemo(
    () =>
      groups
        .map((g) => {
          const record = g as unknown as Record<string, unknown>;
          if (typeof record.name === "string") return record.name;
          if (typeof record.id === "string") return record.id;
          return "";
        })
        .filter(Boolean),
    [groups]
  );

  const handleAccessModeChange = useCallback(
    (_event: React.ChangeEvent<HTMLInputElement>, value: string) => {
      updatePortalData({ accessMode: value as AccessMode });
    },
    [updatePortalData]
  );

  const handlePassphraseChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      updatePortalData({ passphrase: event.target.value });
    },
    [updatePortalData]
  );

  const handleTokenBypassChange = useCallback(
    (_event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
      updatePortalData({ tokenBypassesPassphrase: checked });
    },
    [updatePortalData]
  );

  const handleAllowedGroupsChange = useCallback(
    (_event: React.SyntheticEvent, value: string[]) => {
      updatePortalData({ allowedGroups: value });
    },
    [updatePortalData]
  );

  const handleIpEnabledChange = useCallback(
    (_event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
      setIpEnabled(checked);
      // Legacy parity: flipping the switch off also clears the list so the
      // backend does not receive a stale allowlist from a hidden field.
      if (!checked) {
        updatePortalData({ ipAllowlist: [] });
      }
    },
    [updatePortalData]
  );

  const handleIpAllowlistChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      // Split on newlines and drop empty entries so trailing `\n` does not
      // produce a phantom empty item. Matches the legacy behavior.
      const next = event.target.value.split("\n").filter(Boolean);
      updatePortalData({ ipAllowlist: next });
    },
    [updatePortalData]
  );

  const handleIsActiveChange = useCallback(
    (_event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
      updatePortalData({ isActive: checked });
    },
    [updatePortalData]
  );

  const handleCaptchaEnabledChange = useCallback(
    (_event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
      updatePortalData({ captchaEnabled: checked });
    },
    [updatePortalData]
  );

  const handleExpiresAtChange = useCallback(
    (date: Date | null) => {
      updatePortalData({ expiresAt: date ? date.toISOString() : undefined });
    },
    [updatePortalData]
  );

  const expiresAtDate = expiresAt ? new Date(expiresAt) : null;

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Stack spacing={3}>
        {/* Access-mode radio group */}
        <Box>
          <FormLabel>{t("uploadPortals.form.accessMode")}</FormLabel>
          <RadioGroup value={accessMode} onChange={handleAccessModeChange}>
            <FormControlLabel value="public" control={<Radio />} label="Public" />
            <FormControlLabel value="token-protected" control={<Radio />} label="Token Protected" />
            <FormControlLabel
              value="cognito-groups"
              control={<Radio />}
              label="Authenticated (Cognito)"
            />
          </RadioGroup>
        </Box>

        {/* Conditional passphrase + tokenBypassesPassphrase toggle */}
        {accessMode === "token-protected" && (
          <Stack spacing={2} sx={{ pl: 2 }}>
            <TextField
              label="Passphrase"
              type={showPassword ? "text" : "password"}
              value={passphrase}
              onChange={handlePassphraseChange}
              fullWidth
              size="small"
              slotProps={{
                input: {
                  endAdornment: (
                    <Typography
                      sx={{
                        cursor: "pointer",
                        whiteSpace: "nowrap",
                        fontSize: "0.8rem",
                      }}
                      onClick={() => setShowPassword((prev) => !prev)}
                    >
                      {showPassword ? "Hide" : "Show"}
                    </Typography>
                  ),
                },
              }}
            />
            <FormControlLabel
              control={
                <Switch checked={tokenBypassesPassphrase} onChange={handleTokenBypassChange} />
              }
              label="Token bypasses passphrase"
            />
          </Stack>
        )}

        {/* Allowed groups (Cognito mode only) */}
        {accessMode === "cognito-groups" && (
          <Autocomplete
            multiple
            options={groupNames}
            value={allowedGroups}
            onChange={handleAllowedGroupsChange}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Allowed Groups"
                placeholder={t("uploadPortals.form.selectGroups")}
                size="small"
              />
            )}
          />
        )}

        {/* IP allowlist */}
        <Box>
          <FormControlLabel
            control={<Switch checked={ipEnabled} onChange={handleIpEnabledChange} />}
            label="IP Allowlist"
          />
          {ipEnabled && (
            <TextField
              multiline
              rows={3}
              fullWidth
              size="small"
              placeholder={t("uploadPortals.form.ipPlaceholder")}
              value={ipAllowlist.join("\n")}
              onChange={handleIpAllowlistChange}
              sx={{ mt: 1 }}
            />
          )}
        </Box>

        {/* Active / CAPTCHA / expiry row */}
        <Stack direction="row" spacing={3} alignItems="center" flexWrap="wrap" useFlexGap>
          <FormControlLabel
            control={<Switch checked={isActive} onChange={handleIsActiveChange} />}
            label="Active"
          />
          <FormControlLabel
            control={<Switch checked={captchaEnabled} onChange={handleCaptchaEnabledChange} />}
            label="CAPTCHA"
          />
          <DatePicker
            label="Expiry (optional)"
            value={expiresAtDate}
            onChange={handleExpiresAtChange}
            slotProps={{ textField: { size: "small" } }}
          />
        </Stack>
      </Stack>
    </LocalizationProvider>
  );
};

export { AccessControlSection };
export default React.memo(AccessControlSection);

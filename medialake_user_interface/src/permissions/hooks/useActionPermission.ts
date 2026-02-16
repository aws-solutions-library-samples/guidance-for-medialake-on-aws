import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { usePermission } from "./usePermission";
import { Actions, Subjects } from "../types/ability.types";

interface ActionPermissionResult {
  /** Whether the action is allowed */
  allowed: boolean;
  /** Whether the UI element should be disabled (inverse of allowed) */
  disabled: boolean;
  /** Tooltip text to show when disabled */
  tooltip: string;
  /** Props spread helper — spread onto MUI Button/IconButton */
  disabledProps: {
    disabled: boolean;
    title: string;
  };
}

/**
 * Convenience hook that returns disabled state + tooltip for a given action/subject.
 *
 * Usage:
 * ```tsx
 * const deletePermission = useActionPermission("delete", "asset");
 * <Button {...deletePermission.disabledProps} onClick={handleDelete}>Delete</Button>
 * ```
 */
export function useActionPermission(
  action: Actions,
  subject: Subjects,
  field?: string
): ActionPermissionResult {
  const { can, loading } = usePermission();
  const { t } = useTranslation();

  return useMemo(() => {
    // While loading, default to disabled to prevent unauthorized flashes
    const allowed = loading ? false : can(action, subject, field);
    const disabled = !allowed;
    const tooltip = disabled
      ? t("permissions.noPermission", "You don't have permission to perform this action")
      : "";

    return {
      allowed,
      disabled,
      tooltip,
      disabledProps: {
        disabled,
        title: tooltip,
      },
    };
  }, [action, subject, field, can, loading, t]);
}

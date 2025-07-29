import React from "react";
import { Column } from "@tanstack/react-table";
import { Environment } from "@/types/environment";
import { useTranslation } from "react-i18next";
import { BaseFilterPopover } from "@/components/common/table/BaseFilterPopover";

interface EnvironmentFilterPopoverProps {
  anchorEl: HTMLElement | null;
  column: Column<Environment, unknown> | null;
  onClose: () => void;
  environments: Environment[];
}

export const EnvironmentFilterPopover: React.FC<
  EnvironmentFilterPopoverProps
> = ({ anchorEl, column, onClose, environments }) => {
  const { t } = useTranslation();

  const formatDateOnly = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString();
  };

  const getUniqueValues = (columnId: string, data: Environment[]) => {
    const values = new Set<string>();
    data.forEach((env) => {
      let value: any;
      if (columnId === "team" || columnId === "cost-center") {
        value = env.tags?.[columnId];
      } else {
        value = env[columnId as keyof Environment];
      }

      if (value != null) {
        if (columnId === "created_at" || columnId === "updated_at") {
          values.add(formatDateOnly(String(value)));
        } else {
          values.add(String(value));
        }
      }
    });
    return Array.from(values).sort();
  };

  const formatValue = (columnId: string, value: string) => {
    if (columnId === "status") {
      return value === "active"
        ? t("settings.environments.status.active")
        : t("settings.environments.status.disabled");
    }
    return value;
  };

  return (
    <BaseFilterPopover<Environment>
      anchorEl={anchorEl}
      column={column}
      onClose={onClose}
      data={environments}
      getUniqueValues={getUniqueValues}
      formatValue={formatValue}
    />
  );
};

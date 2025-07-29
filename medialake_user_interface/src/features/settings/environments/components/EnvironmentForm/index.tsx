import React from "react";
import { Dialog, DialogTitle, DialogContent } from "@mui/material";
import { useTranslation } from "react-i18next";
import { Environment, EnvironmentCreate } from "@/types/environment";
import { Form } from "@/forms/components/Form";
import { FormField } from "@/forms/components/FormField";
import { FormSelect } from "@/forms/components/FormSelect";
import { useFormWithValidation } from "@/forms/hooks/useFormWithValidation";
import {
  environmentFormSchema,
  EnvironmentFormData,
  defaultEnvironmentFormData,
  EnvironmentStatus,
} from "../../schemas/environmentFormSchema";

interface EnvironmentFormProps {
  open: boolean;
  onClose: () => void;
  onSave: (data: EnvironmentCreate) => Promise<void>;
  environment?: Environment;
}

export const EnvironmentForm: React.FC<EnvironmentFormProps> = ({
  open,
  onClose,
  onSave,
  environment,
}) => {
  const { t } = useTranslation();

  const form = useFormWithValidation<EnvironmentFormData>({
    validationSchema: environmentFormSchema,
    defaultValues: environment
      ? {
          name: environment.name,
          region: environment.region,
          status: environment.status,
          tags: {
            "cost-center": environment.tags?.["cost-center"] || "",
            team: environment.tags?.team || "default",
          },
        }
      : defaultEnvironmentFormData,
    translationPrefix: "settings.environments.form",
  });

  const handleSubmit = async (data: EnvironmentFormData) => {
    const environmentData: EnvironmentCreate & { status: EnvironmentStatus } = {
      name: data.name,
      status: data.status,
      region: data.region,
      tags: {
        "cost-center": data.tags["cost-center"],
        team: data.tags.team,
      },
    };
    await onSave(environmentData);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {environment
          ? t("settings.environments.editTitle")
          : t("settings.environments.createTitle")}
      </DialogTitle>
      <DialogContent>
        <Form
          form={form}
          onSubmit={handleSubmit}
          onCancel={onClose}
          submitLabel={t("common.save")}
        >
          <FormField
            name="name"
            control={form.control}
            label={t("settings.environments.form.name")}
            required
          />
          <FormField
            name="region"
            control={form.control}
            label={t("settings.environments.form.region")}
            required
          />
          <FormSelect
            name="status"
            control={form.control}
            label={t("settings.environments.form.status.name")}
            options={[
              {
                label: t("settings.environments.form.status.active"),
                value: EnvironmentStatus.Active,
              },
              {
                label: t("settings.environments.form.status.disabled"),
                value: EnvironmentStatus.Disabled,
              },
            ]}
            required
          />
          <FormField
            name="tags.cost-center"
            control={form.control}
            label={t("settings.environments.form.costCenter")}
            required
          />
          <FormField
            name="tags.team"
            control={form.control}
            label={t("settings.environments.form.team")}
            required
          />
        </Form>
      </DialogContent>
    </Dialog>
  );
};

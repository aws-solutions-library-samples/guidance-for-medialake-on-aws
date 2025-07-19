import React from "react";
import { Dialog, DialogTitle, DialogContent, Box } from "@mui/material";
import { User, CreateUserRequest } from "@/api/types/api.types";
import { Form } from "@/forms/components/Form";
import { FormField } from "@/forms/components/FormField";
import { FormSelect } from "@/forms/components/FormSelect";
import { useFormWithValidation } from "@/forms/hooks/useFormWithValidation";
import {
  UserFormData,
  userFormSchema,
  createUserFormDefaults,
} from "../schemas/userFormSchema";
import { useTranslation } from "react-i18next";

interface UserFormProps {
  open: boolean;
  onClose: () => void;
  onSave: (user: CreateUserRequest) => Promise<any>;
  user?: User;
  availableGroups?: { id: string; name: string }[];
  isLoadingGroups?: boolean;
}

export const UserForm: React.FC<UserFormProps> = ({
  open,
  onClose,
  onSave,
  user,
  availableGroups = [],
  isLoadingGroups = false,
}) => {
  const { t } = useTranslation();

  // Debug logs
  console.log("UserForm props:", { user, availableGroups });

  const form = useFormWithValidation<UserFormData>({
    defaultValues: user
      ? {
          given_name: user.given_name || user.name || "",
          family_name: user.family_name || "",
          email: user.email || "",
          groups:
            user.groups && user.groups.length > 0
              ? (() => {
                  // Convert first group name to group ID for the form
                  const group = availableGroups.find(
                    (g) => g.name === user.groups[0],
                  );
                  return group ? group.id : "editors";
                })()
              : "editors",
        }
      : createUserFormDefaults,
    validationSchema: userFormSchema,
    mode: "onChange",
    translationPrefix: "users.form",
  });

  React.useEffect(() => {
    if (open) {
      const defaultVals = user
        ? {
            given_name: user.given_name || user.name || "",
            family_name: user.family_name || "",
            email: user.email || "",
            groups:
              user.groups && user.groups.length > 0
                ? (() => {
                    // Convert first group name to group ID for the form
                    const group = availableGroups.find(
                      (g) => g.name === user.groups[0],
                    );
                    return group ? group.id : "editors";
                  })()
                : "editors",
          }
        : createUserFormDefaults;
      form.reset(defaultVals);
    } else {
      // Optionally reset to blank defaults when closed, if desired
      // form.reset(createUserFormDefaults);
    }
  }, [user, open, form.reset, availableGroups]);

  const handleSubmit = async (data: UserFormData) => {
    try {
      const requestData: CreateUserRequest = {
        username: data.email,
        email: data.email,
        given_name: data.given_name,
        family_name: data.family_name,
        permissions: [], // Set empty array for permissions
        groups: [data.groups], // Convert single group ID back to array
        enabled: true, // Default to enabled
      };

      console.log("Submitting user creation request:", requestData);
      await onSave(requestData);
      onClose();
      form.reset();
    } catch (error) {
      // Error handling is done at the parent level
      throw error;
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {user ? t("users.form.title.edit") : t("users.form.title.add")}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          <Form
            form={form}
            onSubmit={handleSubmit}
            submitLabel={
              user ? t("common.actions.save") : t("common.actions.add")
            }
            onCancel={onClose}
          >
            <FormField
              name="given_name"
              control={form.control}
              label={t("users.form.fields.given_name.label")}
              tooltip={t("users.form.fields.given_name.tooltip")}
              required
              translationPrefix="users.form"
            />
            <FormField
              name="family_name"
              control={form.control}
              label={t("users.form.fields.family_name.label")}
              tooltip={t("users.form.fields.family_name.tooltip")}
              required
              translationPrefix="users.form"
            />
            <FormField
              name="email"
              control={form.control}
              label={t("users.form.fields.email.label")}
              tooltip={t("users.form.fields.email.tooltip")}
              type="email"
              required
              translationPrefix="users.form"
            />
            <FormSelect
              name="groups"
              control={form.control}
              label={t("users.form.fields.groups.label", "Group")}
              tooltip={
                isLoadingGroups
                  ? "Loading groups..."
                  : t(
                      "users.form.fields.groups.tooltip",
                      "Select a group for this user",
                    )
              }
              options={availableGroups.map((group) => {
                console.log("Mapping group in FormSelect:", group);
                return {
                  label: group.name,
                  value: group.id,
                };
              })}
              disabled={
                isLoadingGroups ||
                !availableGroups ||
                availableGroups.length === 0
              }
              translationPrefix="users.form"
            />
          </Form>
        </Box>
      </DialogContent>
    </Dialog>
  );
};

export default UserForm;

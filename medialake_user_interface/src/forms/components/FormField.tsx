import React from "react";
import { Controller, Control, FieldValues, Path } from "react-hook-form";
import {
  TextField,
  TextFieldProps,
  Tooltip,
  IconButton,
  Box,
  InputAdornment,
} from "@mui/material";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import { useTranslation } from "react-i18next";

export type FormFieldProps<T extends FieldValues> = {
  name: Path<T>;
  control: Control<T>;
  label?: string;
  type?: string;
  required?: boolean;
  fullWidth?: boolean;
  tooltip?: string;
  translationPrefix?: string;
  useDirectLabels?: boolean;
  showHelper?: boolean;
} & Omit<TextFieldProps, "name">;

export const FormField = <T extends FieldValues>({
  name,
  control,
  label,
  type = "text",
  required = false,
  fullWidth = true,
  tooltip,
  translationPrefix,
  useDirectLabels = false,
  showHelper = false,
  ...rest
}: FormFieldProps<T>) => {
  const { t } = useTranslation();

  // Use direct label if useDirectLabels is true, otherwise use translation
  const fieldLabel = useDirectLabels
    ? label
    : translationPrefix
      ? t(`${translationPrefix}.fields.${name}.label`, label || "")
      : label;

  const helperText = useDirectLabels
    ? undefined
    : translationPrefix
      ? t(`${translationPrefix}.fields.${name}.helper`, "")
      : undefined;

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => (
        <TextField
          {...field}
          {...rest}
          type={type}
          label={fieldLabel}
          required={required}
          fullWidth={fullWidth}
          error={!!error}
          helperText={
            error
              ? useDirectLabels
                ? error.message
                : t(
                    `${translationPrefix}.errors.${error.type}`,
                    error.message || "",
                  )
              : helperText
          }
          InputProps={{
            ...rest.InputProps,
            endAdornment: tooltip ? (
              <InputAdornment position="end">
                <Tooltip title={tooltip}>
                  <IconButton edge="end" size="small">
                    <HelpOutlineIcon />
                  </IconButton>
                </Tooltip>
              </InputAdornment>
            ) : (
              rest.InputProps?.endAdornment
            ),
          }}
        />
      )}
    />
  );
};

FormField.displayName = "FormField";

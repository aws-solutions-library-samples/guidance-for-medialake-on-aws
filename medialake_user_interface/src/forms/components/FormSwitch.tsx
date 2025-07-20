import React from "react";
import { Controller, Control, FieldValues, Path } from "react-hook-form";
import {
  FormControlLabel,
  Switch,
  SwitchProps,
  FormHelperText,
  FormControl,
  Tooltip,
  IconButton,
  Box,
} from "@mui/material";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import { useTranslation } from "react-i18next";

export type FormSwitchProps<T extends FieldValues> = {
  name: Path<T>;
  control: Control<T>;
  label: string;
  tooltip?: string;
  translationPrefix?: string;
  showHelper?: boolean;
} & Omit<SwitchProps, "name" | "value" | "onChange">;

export const FormSwitch = <T extends FieldValues>({
  name,
  control,
  label,
  tooltip,
  translationPrefix,
  showHelper = false,
  ...rest
}: FormSwitchProps<T>) => {
  const { t } = useTranslation();

  // Handle translations
  const translatedLabel = translationPrefix
    ? t(`${translationPrefix}.fields.${name}.label`, label)
    : label;

  const translatedTooltip =
    translationPrefix && tooltip
      ? t(`${translationPrefix}.fields.${name}.tooltip`, tooltip)
      : tooltip;

  const translatedHelperText =
    translationPrefix && showHelper
      ? t(`${translationPrefix}.fields.${name}.helper`, "")
      : undefined;

  return (
    <Controller
      name={name}
      control={control}
      render={({ field: { onChange, value, ref }, fieldState: { error } }) => (
        <FormControl error={!!error}>
          <Box sx={{ display: "flex", alignItems: "center" }}>
            <FormControlLabel
              control={
                <Switch
                  {...rest}
                  checked={!!value}
                  onChange={(e) => onChange(e.target.checked)}
                  inputRef={ref}
                />
              }
              label={translatedLabel}
            />
            {translatedTooltip && (
              <Tooltip title={translatedTooltip} arrow>
                <IconButton
                  size="small"
                  aria-label={t("common.moreInfo", "More information")}
                  tabIndex={-1}
                  sx={{ ml: 0.5 }}
                >
                  <HelpOutlineIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
          {(error || (showHelper && translatedHelperText)) && (
            <FormHelperText>
              {error
                ? translationPrefix
                  ? t(
                      `${translationPrefix}.errors.${error.type}`,
                      error.message || "",
                    )
                  : error.message
                : translatedHelperText}
            </FormHelperText>
          )}
        </FormControl>
      )}
    />
  );
};

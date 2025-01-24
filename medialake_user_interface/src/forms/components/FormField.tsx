import React from 'react';
import { Controller, Control, FieldValues, Path } from 'react-hook-form';
import {
    TextField,
    TextFieldProps,
    Tooltip,
    IconButton,
    Box,
    InputAdornment,
} from '@mui/material';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { useTranslation } from 'react-i18next';

export type FormFieldProps<T extends FieldValues> = {
    name: Path<T>;
    control: Control<T>;
    label?: string;
    type?: string;
    required?: boolean;
    fullWidth?: boolean;
    tooltip?: string;
    translationPrefix?: string;
    showHelper?: boolean;
} & Omit<TextFieldProps, 'name'>;

export const FormField = <T extends FieldValues>({
    name,
    control,
    label,
    type = 'text',
    required = false,
    fullWidth = true,
    tooltip,
    translationPrefix,
    showHelper = false,
    ...rest
}: FormFieldProps<T>) => {
    const { t } = useTranslation();

    // If translationPrefix is provided, use it to look up translations
    const translatedLabel = translationPrefix
        ? t(`${translationPrefix}.fields.${name}.label`, label || name)
        : label || name;

    const translatedTooltip = translationPrefix && tooltip
        ? t(`${translationPrefix}.fields.${name}.tooltip`, tooltip)
        : tooltip;

    const translatedHelperText = translationPrefix && showHelper
        ? t(`${translationPrefix}.fields.${name}.helper`, '')
        : rest.helperText;

    const tooltipIcon = translatedTooltip && (
        <InputAdornment position="end">
            <Tooltip title={translatedTooltip} arrow>
                <IconButton
                    size="small"
                    aria-label={t('common.moreInfo', 'More information')}
                    tabIndex={-1} // Prevent tab focus as it's just informational
                >
                    <HelpOutlineIcon fontSize="small" />
                </IconButton>
            </Tooltip>
        </InputAdornment>
    );

    return (
        <Controller
            name={name}
            control={control}
            render={({ field, fieldState: { error } }) => (
                <TextField
                    {...field}
                    {...rest}
                    label={translatedLabel}
                    type={type}
                    required={required}
                    fullWidth={fullWidth}
                    error={!!error}
                    helperText={error ? (
                        translationPrefix
                            ? t(`${translationPrefix}.errors.${error.type}`, error.message || '')
                            : error.message
                    ) : translatedHelperText}
                    InputProps={{
                        ...rest.InputProps,
                        endAdornment: (
                            <>
                                {rest.InputProps?.endAdornment}
                                {tooltipIcon}
                            </>
                        ),
                    }}
                />
            )}
        />
    );
};

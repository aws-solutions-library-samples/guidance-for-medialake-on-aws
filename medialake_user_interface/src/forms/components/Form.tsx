import React from 'react';
import { FieldValues, UseFormReturn } from 'react-hook-form';
import { Box, Button, Stack } from '@mui/material';

export type FormProps<T extends FieldValues> = {
    form: UseFormReturn<T>;
    onSubmit: (data: T) => void | Promise<void>;
    children: React.ReactNode;
    submitLabel?: string;
    isSubmitting?: boolean;
    showCancelButton?: boolean;
    onCancel?: () => void;
};

export const Form = <T extends FieldValues>({
    form,
    onSubmit,
    children,
    submitLabel = 'Submit',
    isSubmitting = false,
    showCancelButton = false,
    onCancel,
}: FormProps<T>) => {
    const handleSubmit = form.handleSubmit(async (data) => {
        try {
            await onSubmit(data);
        } catch (error) {
            // Handle error if needed
            console.error('Form submission error:', error);
        }
    });

    return (
        <Box component="form" onSubmit={handleSubmit} noValidate>
            <Stack spacing={2}>
                {children}
                <Stack direction="row" spacing={2} justifyContent="flex-end">
                    {showCancelButton && (
                        <Button
                            type="button"
                            onClick={onCancel}
                            variant="outlined"
                            disabled={isSubmitting}
                        >
                            Cancel
                        </Button>
                    )}
                    <Button
                        type="submit"
                        variant="contained"
                        disabled={isSubmitting || !form.formState.isDirty}
                    >
                        {submitLabel}
                    </Button>
                </Stack>
            </Stack>
        </Box>
    );
};

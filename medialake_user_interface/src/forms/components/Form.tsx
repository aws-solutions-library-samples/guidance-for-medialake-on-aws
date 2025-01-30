import React from 'react';
import { Box, Button, Stack } from '@mui/material';
import { UseFormReturn } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

interface FormProps {
    form: UseFormReturn<any>;
    onSubmit: (data: any) => Promise<void>;
    onCancel?: () => void;
    submitLabel?: string;
    children: React.ReactNode;
}

export const Form: React.FC<FormProps> = ({
    form,
    onSubmit,
    onCancel,
    submitLabel = 'common.save',
    children,
}) => {
    const { t } = useTranslation();

    const handleSubmit = React.useCallback(async (data: any) => {
        console.log('[Form] Form submit triggered with data:', data);
        try {
            await onSubmit(data);
            console.log('[Form] Form submission completed successfully');
        } catch (error) {
            console.error('[Form] Form submission error:', error);
            // Handle error (could show error message, etc.)
        }
    }, [onSubmit]);

    return (
        <Box
            component="form"
            onSubmit={(e) => {
                console.log('[Form] Native form submit event triggered');
                form.handleSubmit(handleSubmit)(e);
            }}
            noValidate
            sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
            }}
        >
            {children}
            <Stack direction="row" spacing={2} justifyContent="flex-end" sx={{ mt: 2 }}>
                {onCancel && (
                    <Button onClick={onCancel} variant="outlined">
                        {t('common.cancel')}
                    </Button>
                )}
                <Button type="submit" variant="contained" color="primary">
                    {t(submitLabel)}
                </Button>
            </Stack>
        </Box>
    );
};

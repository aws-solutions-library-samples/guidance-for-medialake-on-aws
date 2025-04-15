import React from 'react';
import {
    Box,
    Button,
    IconButton,
    InputAdornment,
    FormControlLabel,
    Switch,
} from '@mui/material';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { Form } from '@/forms/components/Form';
import { FormField } from '@/forms/components/FormField';
import { FormSelect } from '@/forms/components/FormSelect';
import { useFormWithValidation } from '@/forms/hooks/useFormWithValidation';
import { IntegrationConfigurationProps, IntegrationFormData } from '@/features/settings/integrations/components/IntegrationForm/types';
import { useCreateIntegration } from '../../../api/integrations.controller';

export const IntegrationConfiguration: React.FC<IntegrationConfigurationProps> = ({
    formData,
    onSubmit,
    onBack,
    onClose,
}) => {
    const { t } = useTranslation();
    const [showApiKey, setShowApiKey] = React.useState(false);
    const [enabled, setEnabled] = React.useState(true);

    const createIntegrationMutation = useCreateIntegration();

    // Define schema directly with Zod
    const validationSchema = React.useMemo(() => {
        return z.object({
            nodeId: z.string().min(1, 'Integration selection is required'),
            description: z.string().min(1, 'Description is required'),
            auth: z.object({
                type: z.enum(['apiKey', 'awsIam']),
                credentials: z.object({
                    apiKey: z.string().optional(),
                    iamRole: z.string().optional()
                })
            })
        }).strict();
    }, []);

    // Ensure form data matches schema structure exactly
    const initialFormData = React.useMemo(() => {
        console.log('[IntegrationConfiguration] Received form data:', formData);
        const cleanData = {
            nodeId: formData.nodeId || '',
            description: formData.description || '',
            auth: {
                type: formData.auth?.type || 'apiKey',
                credentials: {
                    apiKey: formData.auth?.credentials?.apiKey || '',
                    iamRole: formData.auth?.credentials?.iamRole || ''
                }
            }
        };
        console.log('[IntegrationConfiguration] Cleaned form data:', cleanData);
        return cleanData;
    }, [formData]);

    const form = useFormWithValidation({
        defaultValues: initialFormData,
        validationSchema,
        mode: 'onChange',
        translationPrefix: 'integrations.form',
    });

    React.useEffect(() => {
        // Log form state changes
        const subscription = form.watch((value) => {
            console.log('[IntegrationConfiguration] Form values changed:', value);
        });
        return () => subscription.unsubscribe();
    }, [form]);

    console.log('[IntegrationConfiguration] Current form state:', {
        values: form.getValues(),
        isValid: form.formState.isValid,
        isDirty: form.formState.isDirty,
        errors: form.formState.errors
    });

    const handleSubmit = React.useCallback(async (data: IntegrationFormData) => {
        console.log('[IntegrationConfiguration] Starting submission with data:', data);
        try {
            const now = new Date().toISOString();

            // Add metadata to the form data before submitting
            const submissionData = {
                ...data, // This includes all required fields from IntegrationFormData
                integrationType: data.nodeId.replace('node-', '').replace('-api', ''),
                integrationEnabled: enabled,
                createdDate: now,
                modifiedDate: now,
            };
            
            console.log('[IntegrationConfiguration] Prepared submission data:', submissionData);

            await onSubmit(data);
            console.log('[IntegrationConfiguration] Submission completed');
        } catch (error) {
            console.error('[IntegrationConfiguration] Error during submission:', error);
        }
    }, [onSubmit, enabled]);

    const authMethod = formData.auth.type;

    return (
        <Form
            form={form}
            onSubmit={handleSubmit}
            showButtons={false}
        >
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <FormControlLabel
                    control={
                        <Switch
                            checked={enabled}
                            onChange={(e) => setEnabled(e.target.checked)}
                            color="primary"
                        />
                    }
                    label={t('integrations.form.fields.enabled.label')}
                />
                <FormField
                    name="description"
                    control={form.control}
                    label={t('integrations.form.fields.description.label')}
                    tooltip={t('integrations.form.fields.description.tooltip')}
                    multiline
                    rows={3}
                    required
                    translationPrefix="integrations.form"
                />
                {authMethod === 'awsIam' && (
                    <FormField
                        name="auth.credentials.iamRole"
                        control={form.control}
                        label={t('integrations.form.fields.iamRole.label')}
                        tooltip={t('integrations.form.fields.iamRole.tooltip')}
                        disabled
                        value="IAM Role will be generated"
                        translationPrefix="integrations.form"
                    />
                )}
                {authMethod === 'apiKey' && (
                    <FormField
                        name="auth.credentials.apiKey"
                        control={form.control}
                        label={t('integrations.form.fields.apiKey.label')}
                        tooltip={t('integrations.form.fields.apiKey.tooltip')}
                        type={showApiKey ? 'text' : 'password'}
                        required
                        translationPrefix="integrations.form"
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <IconButton
                                        onClick={() => setShowApiKey(!showApiKey)}
                                        edge="end"
                                    >
                                        {showApiKey ? <VisibilityOff /> : <Visibility />}
                                    </IconButton>
                                </InputAdornment>
                            ),
                        }}
                    />
                )}
            </Box>

            <Box sx={{ mt: 4, display: 'flex', justifyContent: 'space-between' }}>
                <Button onClick={onBack} variant="outlined">
                    {t('common.back')}
                </Button>
                <Box sx={{ display: 'flex', gap: 2 }}>
                    <Button onClick={onClose} variant="outlined">
                        {t('common.cancel')}
                    </Button>
                    <Button
                        type="submit"
                        variant="contained"
                        disabled={!form.formState.isValid}
                    >
                        {t('common.save')}
                    </Button>
                </Box>
            </Box>
        </Form>
    );
};

export default React.memo(IntegrationConfiguration);

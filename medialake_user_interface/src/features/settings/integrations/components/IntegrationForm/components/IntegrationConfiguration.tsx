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
    environments,
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
            environmentId: z.string().min(1, 'Environment selection is required'),
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
            environmentId: formData.environmentId || '',
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

            const submissionData = {
                nodeId: data.nodeId,
                integrationType: data.nodeId.replace('node-', '').replace('-api', ''),
                description: data.description,
                environmentId: data.environmentId,
                integrationEnabled: enabled,
                createdDate: now,
                modifiedDate: now,
                auth: {
                    type: data.auth.type,
                    credentials: {
                        apiKey: data.auth.type === 'apiKey' ? data.auth.credentials.apiKey : undefined,
                        iamRole: data.auth.type === 'awsIam' ? data.auth.credentials.iamRole : undefined
                    }
                }
            };
            console.log('[IntegrationConfiguration] Cleaned submission data:', submissionData);

            if (createIntegrationMutation) {
                console.log('[IntegrationConfiguration] Calling mutation');
                await createIntegrationMutation.mutateAsync(submissionData);
                console.log('[IntegrationConfiguration] Mutation completed');
            }

            console.log('[IntegrationConfiguration] Calling parent onSubmit');
            await onSubmit(submissionData);
            console.log('[IntegrationConfiguration] Parent onSubmit completed');

            if (onClose) {
                console.log('[IntegrationConfiguration] Closing form');
                onClose();
            }
        } catch (error) {
            console.error('[IntegrationConfiguration] Error during submission:', error);
        }
    }, [createIntegrationMutation, onSubmit, onClose, enabled]);

    const authMethod = formData.auth.type;

    return (
        <Form
            form={form}
            onSubmit={handleSubmit}
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
                <FormSelect
                    name="environmentId"
                    control={form.control}
                    label={t('integrations.form.fields.environment.label')}
                    tooltip={t('integrations.form.fields.environment.tooltip')}
                    options={environments.map((env) => ({
                        label: env.name,
                        value: env.environment_id,
                    }))}
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
            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
                <Button onClick={onBack}>
                    {t('common.back')}
                </Button>
                <Button
                    type="submit"
                    variant="contained"
                    color="primary"
                    onClick={() => {
                        console.log('[IntegrationConfiguration] Submit button clicked');
                    }}
                >
                    {t('common.create')}
                </Button>
            </Box>
        </Form>
    );
};

export default React.memo(IntegrationConfiguration);

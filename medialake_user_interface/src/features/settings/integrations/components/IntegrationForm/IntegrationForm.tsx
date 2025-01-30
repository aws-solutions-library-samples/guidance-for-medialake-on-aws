import React from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    Box,
    Typography,
    Stepper,
    Step,
    StepLabel,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Avatar,
    Button,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Form } from '@/forms/components/Form';
import { FormField } from '@/forms/components/FormField';
import { FormSelect } from '@/forms/components/FormSelect';
import { useFormWithValidation } from '@/forms/hooks/useFormWithValidation';
import { IntegrationFormProps, IntegrationFormData } from './types';
import { integrationFormSchema, createIntegrationFormDefaults } from './schemas/integrationFormSchema';
import { useCreateIntegration } from '@/features/settings/integrations/api/integrations.controller';
import { IntegrationsNodesService } from '@/features/settings/integrations/services/integrations-nodes.service';
import { IntegrationsEnvironmentsService } from '@/features/settings/integrations/services/integrations-environments.service';
import { IntegrationNode } from '@/features/settings/integrations/types';
import { IntegrationConfiguration } from './components/IntegrationConfiguration';

const steps = ['integrations.selectIntegration', 'integrations.configureIntegration'];

export const IntegrationForm: React.FC<IntegrationFormProps> = ({
    open,
    onClose,
}) => {
    const { t } = useTranslation();
    const [activeStep, setActiveStep] = React.useState(0);
    const [selectedNodeId, setSelectedNodeId] = React.useState<string>('');
    const createIntegration = useCreateIntegration();
    const { nodes: rawNodes = [], isLoading: isLoadingNodes } = IntegrationsNodesService.useNodes();
    const { environments = [], isLoading: isLoadingEnvironments } = IntegrationsEnvironmentsService.useEnvironments();

    const defaultFormValues: IntegrationFormData = {
        nodeId: '',
        description: '',
        environmentId: '',
        auth: {
            type: 'apiKey',
            credentials: {},
        }
    };

    const form = useFormWithValidation<IntegrationFormData>({
        defaultValues: defaultFormValues,
        validationSchema: integrationFormSchema,
        mode: 'onChange',
    });

    // Process nodes only when rawNodes changes
    const nodes: IntegrationNode[] = React.useMemo(() => {
        if (!rawNodes.length) return [];
        return rawNodes.map(node => {
            const authMethod = node.auth?.authMethod;
            return {
                nodeId: node.nodeId || `node-${node.info.title.toLowerCase().replace(/\s+/g, '-')}`,
                info: {
                    title: node.info.title,
                    description: node.info.description,
                },
                auth: (authMethod === 'awsIam' || authMethod === 'apiKey')
                    ? { authMethod: authMethod as 'awsIam' | 'apiKey' }
                    : { authMethod: 'apiKey' as const },
            };
        });
    }, [rawNodes]);

    const handleSubmit = React.useCallback(async (data: IntegrationFormData) => {
        try {
            console.log('Starting integration creation with data:', data);

            const result = await createIntegration.mutateAsync(data);

            console.log('Integration created successfully:', result);
            onClose();
        } catch (error) {
            console.error('Failed to create integration:', {
                error,
                formData: data,
                selectedNodeId,
                formState: form.formState
            });
            throw error;
        }
    }, [createIntegration, onClose, selectedNodeId, form.formState]);

    const handleBack = React.useCallback(() => {
        setActiveStep(0);
    }, []);

    const handleNext = React.useCallback(() => {
        if (selectedNodeId) {
            setActiveStep(prev => prev + 1);
        }
    }, [selectedNodeId]);

    const handleReset = React.useCallback(() => {
        setActiveStep(0);
        setSelectedNodeId('');
        form.reset(defaultFormValues);
    }, [form]);

    const handleNodeSelect = React.useCallback((node: IntegrationNode) => {
        if (!node?.nodeId) return;

        const nodeId = node.nodeId;
        setSelectedNodeId(nodeId);

        const authType = node.auth?.authMethod || 'apiKey';
        if (authType !== 'apiKey' && authType !== 'awsIam') return;

        form.reset({
            nodeId: nodeId,
            description: '',
            environmentId: '',
            auth: {
                type: authType,
                credentials: {},
            }
        });
    }, [form]);

    // Reset form when modal closes
    React.useEffect(() => {
        if (!open) {
            handleReset();
        }
    }, [open, handleReset]);

    const renderContent = () => {
        if (isLoadingNodes || isLoadingEnvironments) {
            return (
                <Box sx={{ p: 2, textAlign: 'center' }}>
                    <Typography>{t('common.loading')}</Typography>
                </Box>
            );
        }

        if (activeStep === 0) {
            return (
                <Box>
                    <List sx={{
                        maxHeight: 400,
                        overflow: 'auto',
                        border: '1px solid',
                        borderColor: 'divider',
                        borderRadius: 1,
                        p: 0,
                        mb: 3,
                    }}>
                        {nodes.map((node) => {
                            return (
                                <ListItem key={node.nodeId} disablePadding>
                                    <ListItemButton
                                        selected={node.nodeId === selectedNodeId}
                                        onClick={() => {
                                            handleNodeSelect(node);
                                        }}
                                        sx={{
                                            py: 2,
                                            '&.Mui-selected': {
                                                backgroundColor: 'action.selected',
                                                borderLeft: 4,
                                                borderLeftColor: 'primary.main',
                                                pl: '12px',
                                            },
                                            '&:hover': {
                                                backgroundColor: 'action.hover',
                                            },
                                        }}
                                    >
                                        <ListItemIcon sx={{ minWidth: 56 }}>
                                            <Avatar
                                                alt={node.info.title}
                                                src={`/icons/${node.nodeId}.svg`}
                                                sx={{
                                                    width: 40,
                                                    height: 40,
                                                    bgcolor: 'primary.main'
                                                }}
                                            >
                                                {node.info.title?.charAt(0) || '?'}
                                            </Avatar>
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={node.info.title}
                                            secondary={node.info.description}
                                            primaryTypographyProps={{
                                                variant: 'subtitle1',
                                                fontWeight: node.nodeId === selectedNodeId ? 600 : 500,
                                                color: node.nodeId === selectedNodeId ? 'primary.main' : 'text.primary',
                                            }}
                                            secondaryTypographyProps={{
                                                variant: 'body2',
                                                sx: {
                                                    display: '-webkit-box',
                                                    WebkitLineClamp: 2,
                                                    WebkitBoxOrient: 'vertical',
                                                    overflow: 'hidden',
                                                },
                                            }}
                                        />
                                    </ListItemButton>
                                </ListItem>
                            );
                        })}
                    </List>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
                        <Button onClick={onClose} variant="outlined">
                            {t('common.cancel')}
                        </Button>
                        <Button
                            variant="contained"
                            onClick={handleNext}
                            disabled={!selectedNodeId}
                            color="primary"
                        >
                            {t('common.next')}
                        </Button>
                    </Box>
                </Box>
            );
        }

        return (
            <IntegrationConfiguration
                formData={form.getValues()}
                onSubmit={handleSubmit}
                onBack={handleBack}
                onClose={onClose}
                environments={environments}
            />
        );
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="sm"
            fullWidth
            PaperProps={{
                sx: {
                    borderRadius: '12px',
                    minHeight: 400,
                }
            }}
        >
            <DialogTitle>
                <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
                    {t('integrations.form.title')}
                </Typography>
            </DialogTitle>
            <DialogContent>
                <Box sx={{ mt: 2, mb: 4 }}>
                    <Stepper activeStep={activeStep}>
                        {steps.map((label) => (
                            <Step key={label}>
                                <StepLabel>{t(label)}</StepLabel>
                            </Step>
                        ))}
                    </Stepper>
                </Box>
                {renderContent()}
            </DialogContent>
        </Dialog>
    );
};

export default IntegrationForm;

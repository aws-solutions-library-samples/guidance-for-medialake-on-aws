import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Button,
    Box,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Snackbar,
    Alert,
    Stepper,
    Step,
    StepLabel,
    Card,
    CardContent,
    Typography,
    Grid,
} from '@mui/material';
import { Extension as IntegrationIcon } from '@mui/icons-material';

interface IntegrationFormData {
    nodeName: string;
    environment: string;
    description: string;
}

interface IntegrationFormProps {
    open: boolean;
    onClose: () => void;
    onSave: (data: IntegrationFormData) => Promise<any>;
}

const steps = ['integrations.selectIntegration', 'integrations.configureIntegration'];

const environments = ['Development', 'Staging', 'Production'];

const nodes = [
    {
        id: 'twelve-labs',
        name: 'TwelveLabs',
        description: 'AI-powered video understanding platform'
    },
    {
        id: 'aws-rekognition',
        name: 'AWS Rekognition',
        description: 'Image and video analysis service'
    },
    {
        id: 'azure-cognitive',
        name: 'Azure Cognitive Services',
        description: 'AI services and cognitive APIs'
    },
    {
        id: 'google-vision',
        name: 'Google Cloud Vision',
        description: 'Machine learning-powered image analysis'
    },
    {
        id: 'openai',
        name: 'OpenAI',
        description: 'Advanced AI and language models'
    }
];

const initialFormData: IntegrationFormData = {
    nodeName: '',
    environment: '',
    description: '',
};

const IntegrationForm: React.FC<IntegrationFormProps> = ({
    open,
    onClose,
    onSave,
}) => {
    const { t } = useTranslation();
    const [activeStep, setActiveStep] = useState(0);
    const [formData, setFormData] = useState<IntegrationFormData>(initialFormData);
    const [snackbar, setSnackbar] = useState<{
        open: boolean;
        message: string;
        severity: 'success' | 'error';
    }>({
        open: false,
        message: '',
        severity: 'success',
    });

    useEffect(() => {
        if (open) {
            setFormData(initialFormData);
            setActiveStep(0);
        }
    }, [open]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });
    };

    const handleNodeSelect = (node: typeof nodes[0]) => {
        setFormData({
            ...formData,
            nodeName: node.name,
        });
        setActiveStep(1);
    };

    const handleBack = () => {
        setActiveStep((prevStep) => prevStep - 1);
    };

    const handleClose = () => {
        setFormData(initialFormData);
        onClose();
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const response = await onSave(formData);

            if (response?.status === 201 || response?.status === 200) {
                setSnackbar({
                    open: true,
                    message: response.message || t('integrations.status.created'),
                    severity: 'success',
                });
                handleClose();
            } else {
                throw new Error(response?.message || t('integrations.status.createFailed'));
            }
        } catch (error) {
            console.error('Error in handleSubmit:', error);
            setSnackbar({
                open: true,
                message: t('integrations.status.createFailed') + ': ' + (error instanceof Error ? error.message : t('common.error')),
                severity: 'error',
            });
        }
    };

    const handleSnackbarClose = () => {
        setSnackbar({ ...snackbar, open: false });
    };

    const renderStepContent = () => {
        switch (activeStep) {
            case 0:
                return (
                    <Grid container spacing={2} sx={{ mt: 1 }}>
                        {nodes.map((node) => (
                            <Grid item xs={12} sm={6} key={node.id}>
                                <Card
                                    sx={{
                                        cursor: 'pointer',
                                        '&:hover': {
                                            boxShadow: 6,
                                            transform: 'translateY(-2px)',
                                            transition: 'all 0.2s ease-in-out'
                                        }
                                    }}
                                    onClick={() => handleNodeSelect(node)}
                                >
                                    <CardContent>
                                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                            <IntegrationIcon sx={{ mr: 1 }} />
                                            <Typography variant="h6" component="div">
                                                {node.name}
                                            </Typography>
                                        </Box>
                                        <Typography variant="body2" color="text.secondary">
                                            {node.description}
                                        </Typography>
                                    </CardContent>
                                </Card>
                            </Grid>
                        ))}
                    </Grid>
                );
            case 1:
                return (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                        <FormControl fullWidth>
                            <InputLabel id="environment-label">{t('integrations.form.environment')}</InputLabel>
                            <Select
                                labelId="environment-label"
                                name="environment"
                                value={formData.environment}
                                onChange={handleChange as any}
                                label={t('integrations.form.environment')}
                                required
                            >
                                {environments.map((env) => (
                                    <MenuItem key={env} value={env}>
                                        {env}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <TextField
                            name="description"
                            label={t('integrations.form.description')}
                            value={formData.description}
                            onChange={handleChange}
                            multiline
                            rows={3}
                            fullWidth
                        />
                    </Box>
                );
            default:
                return null;
        }
    };

    return (
        <>
            <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
                <form onSubmit={handleSubmit}>
                    <DialogTitle>{t('integrations.addIntegration')}</DialogTitle>
                    <DialogContent>
                        <Stepper activeStep={activeStep} sx={{ pt: 3, pb: 5 }}>
                            {steps.map((label) => (
                                <Step key={label}>
                                    <StepLabel>{t(label)}</StepLabel>
                                </Step>
                            ))}
                        </Stepper>
                        {renderStepContent()}
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={handleClose}>{t('common.cancel')}</Button>
                        {activeStep > 0 && (
                            <Button onClick={handleBack}>
                                {t('common.previous')}
                            </Button>
                        )}
                        {activeStep === 1 && (
                            <Button type="submit" variant="contained" color="primary">
                                {t('integrations.addIntegration')}
                            </Button>
                        )}
                    </DialogActions>
                </form>
            </Dialog>
            <Snackbar
                open={snackbar.open}
                autoHideDuration={6000}
                onClose={handleSnackbarClose}
                anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            >
                <Alert onClose={handleSnackbarClose} severity={snackbar.severity}>
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </>
    );
};

IntegrationForm.displayName = 'IntegrationForm';

export default React.memo(IntegrationForm);

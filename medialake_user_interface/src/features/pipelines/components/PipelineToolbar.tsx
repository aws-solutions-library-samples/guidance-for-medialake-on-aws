import React from 'react';
import {
    Box,
    Typography,
    Button,
    Stack,
    useTheme,
    alpha,
    Tooltip,
    CircularProgress,
    useMediaQuery,
} from '@mui/material';
import {
    Add as AddIcon,
    RocketLaunch as RocketLaunchIcon,
    ViewColumn as ViewColumnIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { SearchField } from '@/components/common/SearchField';

interface PipelineToolbarProps {
    isCreatingPipeline: boolean;
    globalFilter: string;
    onGlobalFilterChange: (value: string) => void;
    onCreatePipeline: () => void;
    onAddNew: () => void;
    onColumnMenuOpen: (event: React.MouseEvent<HTMLElement>) => void;
}

export const PipelineToolbar: React.FC<PipelineToolbarProps> = ({
    isCreatingPipeline,
    globalFilter,
    onGlobalFilterChange,
    onCreatePipeline,
    onAddNew,
    onColumnMenuOpen,
}) => {
    const { t } = useTranslation();
    const theme = useTheme();
    const isSmallScreen = useMediaQuery(theme.breakpoints.down('lg'));

    return (
        <Box sx={{ mb: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                <Box>
                    <Typography variant="h4" sx={{
                        fontWeight: 700,
                        mb: 1,
                        background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                        backgroundClip: 'text',
                        WebkitBackgroundClip: 'text',
                        color: 'transparent',
                    }}>
                        {t('pipelines.title')}
                    </Typography>
                    <Typography variant="body1" sx={{ color: theme.palette.text.secondary }}>
                        {t('pipelines.description')}
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    <Stack direction="row" spacing={2}>
                        <Tooltip title={isCreatingPipeline ? t('pipelines.deploying') : t('pipelines.deploy')}>
                            {isSmallScreen ? (
                                <Button
                                    onClick={onCreatePipeline}
                                    disabled={isCreatingPipeline}
                                    sx={{
                                        minWidth: 0,
                                        p: 1,
                                        height: '40px',
                                        width: '40px',
                                        borderRadius: '8px',
                                        color: theme.palette.secondary.contrastText,
                                        backgroundColor: theme.palette.secondary.main,
                                        '&:hover': {
                                            backgroundColor: theme.palette.secondary.dark,
                                        },
                                    }}
                                >
                                    {isCreatingPipeline ? (
                                        <CircularProgress size={24} color="inherit" />
                                    ) : (
                                        <RocketLaunchIcon />
                                    )}
                                </Button>
                            ) : (
                                <Button
                                    variant="contained"
                                    color="secondary"
                                    startIcon={isCreatingPipeline ? <CircularProgress size={24} color="inherit" /> : <RocketLaunchIcon />}
                                    onClick={onCreatePipeline}
                                    disabled={isCreatingPipeline}
                                    sx={{
                                        height: '40px',
                                        borderRadius: '8px',
                                        textTransform: 'none',
                                        px: 3,
                                    }}
                                >
                                    {isCreatingPipeline ? t('pipelines.deploying') : t('pipelines.deploy')}
                                </Button>
                            )}
                        </Tooltip>

                        <Tooltip title={t('pipelines.addNew')}>
                            {isSmallScreen ? (
                                <Button
                                    onClick={onAddNew}
                                    sx={{
                                        minWidth: 0,
                                        p: 1,
                                        height: '40px',
                                        width: '40px',
                                        borderRadius: '8px',
                                        color: theme.palette.primary.contrastText,
                                        backgroundColor: theme.palette.primary.main,
                                        '&:hover': {
                                            backgroundColor: theme.palette.primary.dark,
                                        },
                                    }}
                                >
                                    <AddIcon />
                                </Button>
                            ) : (
                                <Button
                                    variant="contained"
                                    color="primary"
                                    startIcon={<AddIcon />}
                                    onClick={onAddNew}
                                    sx={{
                                        height: '40px',
                                        borderRadius: '8px',
                                        textTransform: 'none',
                                        px: 3,
                                    }}
                                >
                                    {t('pipelines.addNew')}
                                </Button>
                            )}
                        </Tooltip>
                    </Stack>
                </Box>
            </Box>

            <Box sx={{
                display: 'flex',
                gap: 2,
                mb: 2,
                alignItems: 'center',
                height: '40px',
            }}>
                <SearchField
                    value={globalFilter ?? ''}
                    onChange={onGlobalFilterChange}
                    placeholder={t('pipelines.search')}
                />
                <Box sx={{ flex: 1 }} />
                <Button
                    variant="outlined"
                    startIcon={<ViewColumnIcon />}
                    onClick={onColumnMenuOpen}
                    sx={{
                        height: '40px',
                        borderRadius: '8px',
                        textTransform: 'none',
                        borderColor: alpha(theme.palette.divider, 0.2),
                        px: 3,
                    }}
                >
                    {t('common.columns')}
                </Button>
            </Box>
        </Box>
    );
};

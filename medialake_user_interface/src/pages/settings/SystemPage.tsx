import React from 'react';
import {
    Box,
    Typography,
    Paper,
    Grid,
    Button,
    Card,
    CardContent,
    LinearProgress,
    useTheme,
} from '@mui/material';
import {
    Backup as BackupIcon,
    CloudDownload as CloudDownloadIcon,
    Delete as DeleteIcon,
    Settings as SettingsIcon,
} from '@mui/icons-material';

const SystemPage: React.FC = () => {
    const theme = useTheme();

    const systemMetrics = [
        { label: 'CPU Usage', value: '45%', color: theme.palette.primary.main },
        { label: 'Memory Usage', value: '60%', color: theme.palette.success.main },
        { label: 'Storage Usage', value: '75%', color: theme.palette.warning.main },
        { label: 'Network Usage', value: '30%', color: theme.palette.info.main },
    ];

    return (
        <Box>
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                    System Settings
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Manage system configuration and maintenance
                </Typography>
            </Box>

            {/* System Metrics */}
            <Grid container spacing={3} sx={{ mb: 4 }}>
                {systemMetrics.map((metric) => (
                    <Grid item xs={12} sm={6} md={3} key={metric.label}>
                        <Card>
                            <CardContent>
                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                    {metric.label}
                                </Typography>
                                <Typography variant="h4" sx={{ mb: 1 }}>
                                    {metric.value}
                                </Typography>
                                <LinearProgress
                                    variant="determinate"
                                    value={parseInt(metric.value)}
                                    sx={{
                                        height: 6,
                                        borderRadius: 3,
                                        backgroundColor: `${metric.color}20`,
                                        '& .MuiLinearProgress-bar': {
                                            borderRadius: 3,
                                            backgroundColor: metric.color,
                                        },
                                    }}
                                />
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>

            {/* System Actions */}
            <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Maintenance
                        </Typography>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <Button
                                variant="outlined"
                                startIcon={<BackupIcon />}
                                fullWidth
                            >
                                Backup System
                            </Button>
                            <Button
                                variant="outlined"
                                startIcon={<CloudDownloadIcon />}
                                fullWidth
                            >
                                Download Logs
                            </Button>
                            <Button
                                variant="outlined"
                                startIcon={<DeleteIcon />}
                                color="error"
                                fullWidth
                            >
                                Clear Cache
                            </Button>
                        </Box>
                    </Paper>
                </Grid>
                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Configuration
                        </Typography>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <Button
                                variant="outlined"
                                startIcon={<SettingsIcon />}
                                fullWidth
                            >
                                System Configuration
                            </Button>
                            <Button
                                variant="outlined"
                                startIcon={<SettingsIcon />}
                                fullWidth
                            >
                                API Settings
                            </Button>
                            <Button
                                variant="outlined"
                                startIcon={<SettingsIcon />}
                                fullWidth
                            >
                                Security Settings
                            </Button>
                        </Box>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default SystemPage;

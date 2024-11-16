import React, { useState } from 'react';
import {
    Box,
    Typography,
    Grid,
    Button,
    TextField,
    InputAdornment,
    MenuItem,
    Select,
    FormControl,
    InputLabel,
    Chip,
    useTheme,
    Paper,
} from '@mui/material';
import {
    Add as AddIcon,
    Search as SearchIcon,
    FilterList as FilterIcon,
} from '@mui/icons-material';
import IntegrationCard from './IntegrationCard';
import { Integration } from '@/api/types/api.types';

interface IntegrationsViewProps {
    integrations: Integration[];
    onAddIntegration: () => void;
    onEditIntegration: (integration: Integration) => void;
    onDeleteIntegration: (id: string) => void;
    onConfigureIntegration: (integration: Integration) => void;
}

const IntegrationsView: React.FC<IntegrationsViewProps> = ({
    integrations,
    onAddIntegration,
    onEditIntegration,
    onDeleteIntegration,
    onConfigureIntegration,
}) => {
    const theme = useTheme();
    const [searchQuery, setSearchQuery] = useState('');
    const [filterType, setFilterType] = useState<string>('all');
    const [sortBy, setSortBy] = useState<string>('newest');

    const integrationTypes = ['All', ...new Set(integrations.map(i => i.type))];

    const filteredIntegrations = integrations
        .filter(integration => {
            const matchesSearch = integration.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                integration.type.toLowerCase().includes(searchQuery.toLowerCase());
            const matchesType = filterType === 'all' || integration.type === filterType;
            return matchesSearch && matchesType;
        })
        .sort((a, b) => {
            switch (sortBy) {
                case 'newest':
                    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
                case 'oldest':
                    return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
                case 'name':
                    return a.name.localeCompare(b.name);
                default:
                    return 0;
            }
        });

    const handleAddClick = () => {
        console.log('Add Integration button clicked'); // Debug log
        onAddIntegration();
    };

    return (
        <Box>
            {/* Header */}
            <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                </Box>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={handleAddClick}
                    sx={{
                        backgroundColor: theme.palette.primary.main,
                        '&:hover': {
                            backgroundColor: theme.palette.primary.dark,
                        },
                    }}
                >
                    Add Integration
                </Button>
            </Box>

            {/* Filters */}
            <Paper
                elevation={0}
                sx={{
                    p: 2,
                    mb: 3,
                    backgroundColor: theme.palette.background.default,
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: '12px',
                }}
            >
                <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} md={4}>
                        <TextField
                            fullWidth
                            placeholder="Search integrations..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <SearchIcon color="action" />
                                    </InputAdornment>
                                ),
                            }}
                            size="small"
                        />
                    </Grid>
                    <Grid item xs={12} md={4}>
                        <FormControl fullWidth size="small">
                            <InputLabel>Filter by Type</InputLabel>
                            <Select
                                value={filterType}
                                onChange={(e) => setFilterType(e.target.value)}
                                label="Filter by Type"
                                startAdornment={
                                    <InputAdornment position="start">
                                        <FilterIcon color="action" />
                                    </InputAdornment>
                                }
                            >
                                <MenuItem value="all">All Types</MenuItem>
                                {integrationTypes.map((type) => (
                                    <MenuItem key={type} value={type.toLowerCase()}>
                                        {type}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Grid>
                    <Grid item xs={12} md={4}>
                        <FormControl fullWidth size="small">
                            <InputLabel>Sort by</InputLabel>
                            <Select
                                value={sortBy}
                                onChange={(e) => setSortBy(e.target.value)}
                                label="Sort by"
                            >
                                <MenuItem value="newest">Newest First</MenuItem>
                                <MenuItem value="oldest">Oldest First</MenuItem>
                                <MenuItem value="name">Name</MenuItem>
                            </Select>
                        </FormControl>
                    </Grid>
                </Grid>
            </Paper>

            {/* Integration Cards */}
            <Grid container spacing={3}>
                {filteredIntegrations.map((integration) => (
                    <Grid item xs={12} sm={6} md={4} key={integration.id}>
                        <IntegrationCard
                            integration={integration}
                            onEdit={onEditIntegration}
                            onDelete={onDeleteIntegration}
                            onConfigure={onConfigureIntegration}
                        />
                    </Grid>
                ))}
            </Grid>

            {/* Empty State */}
            {filteredIntegrations.length === 0 && (
                <Box
                    sx={{
                        textAlign: 'center',
                        py: 8,
                        px: 2,
                        backgroundColor: theme.palette.background.default,
                        borderRadius: '12px',
                        border: `1px dashed ${theme.palette.divider}`,
                    }}
                >
                    <Typography variant="h6" color="text.secondary" gutterBottom>
                        No integrations found
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        {searchQuery || filterType !== 'all'
                            ? 'Try adjusting your search or filters'
                            : 'Get started by adding your first integration'}
                    </Typography>
                </Box>
            )}
        </Box>
    );
};

export default IntegrationsView;

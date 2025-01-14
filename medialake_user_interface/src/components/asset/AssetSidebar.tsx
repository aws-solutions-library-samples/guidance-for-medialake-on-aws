import React, { useState } from 'react';
import { Box, Typography, Tabs, Tab } from '@mui/material';
import HistoryIcon from '@mui/icons-material/History';
import { RightSidebar } from '../common/RightSidebar';
import AssetVersions from './AssetVersions';

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

const TabPanel = (props: TabPanelProps) => {
    const { children, value, index, ...other } = props;

    return (
        <Box
            role="tabpanel"
            hidden={value !== index}
            id={`sidebar-tabpanel-${index}`}
            aria-labelledby={`sidebar-tab-${index}`}
            sx={{ height: 'calc(100% - 96px)', overflow: 'hidden' }}
            {...other}
        >
            {value === index && (
                <Box sx={{ height: '100%' }}>
                    {children}
                </Box>
            )}
        </Box>
    );
};

interface Representation {
    id: string;
    src: string;
    type: string;
    format: string;
    fileSize: string;
    description: string;
}

interface AssetSidebarProps {
    versions: Representation[];
    comments?: {
        user: string;
        avatar: string;
        content: string;
        timestamp: string;
    }[];
    onAddComment?: (comment: string) => void;
}

const AssetSidebar: React.FC<AssetSidebarProps> = ({
    versions
}) => {
    const [currentTab, setCurrentTab] = useState(0);

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setCurrentTab(newValue);
    };

    return (
        <RightSidebar>
            <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <Typography variant="h6" sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
                    Asset Details
                </Typography>
                <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', alignItems: 'center' }}>
                    <HistoryIcon sx={{ mr: 1 }} />
                    <Typography>Representations</Typography>
                </Box>
                <Box sx={{ height: 'calc(100% - 96px)', overflow: 'auto' }}>
                    <AssetVersions versions={versions} />
                </Box>
            </Box>
        </RightSidebar>
    );
};

export default AssetSidebar;

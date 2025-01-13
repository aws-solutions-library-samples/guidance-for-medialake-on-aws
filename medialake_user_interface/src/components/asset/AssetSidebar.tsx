import React, { useState } from 'react';
import { Box, Typography, Tabs, Tab } from '@mui/material';
import HistoryIcon from '@mui/icons-material/History';
import CommentIcon from '@mui/icons-material/Comment';
import { RightSidebar } from '../common/RightSidebar';
import AssetVersions from './AssetVersions';
import AssetReviews from './AssetReviews';

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

interface Version {
    id: string;
    src: string;
    type: string;
    description: string;
}

interface Comment {
    user: string;
    avatar: string;
    content: string;
    timestamp: string;
}

interface AssetSidebarProps {
    versions: Version[];
    comments: Comment[];
    onAddComment: (comment: string) => void;
}

const AssetSidebar: React.FC<AssetSidebarProps> = ({
    versions,
    comments,
    onAddComment
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
                <Tabs
                    value={currentTab}
                    onChange={handleTabChange}
                    aria-label="asset details tabs"
                    sx={{ borderBottom: 1, borderColor: 'divider' }}
                >
                    <Tab
                        icon={<HistoryIcon />}
                        label="Versions"
                        id="sidebar-tab-0"
                        aria-controls="sidebar-tabpanel-0"
                    />
                    <Tab
                        icon={<CommentIcon />}
                        label="Reviews"
                        id="sidebar-tab-1"
                        aria-controls="sidebar-tabpanel-1"
                    />
                </Tabs>
                <TabPanel value={currentTab} index={0}>
                    <AssetVersions versions={versions} />
                </TabPanel>
                <TabPanel value={currentTab} index={1}>
                    <AssetReviews
                        comments={comments}
                        onAddComment={onAddComment}
                    />
                </TabPanel>
            </Box>
        </RightSidebar>
    );
};

export default AssetSidebar;

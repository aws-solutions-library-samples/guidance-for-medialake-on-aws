import React from 'react';
import { Box, Typography, Tabs, Tab, Paper } from '@mui/material';

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
            id={`metadata-tabpanel-${index}`}
            aria-labelledby={`metadata-tab-${index}`}
            sx={{
                flex: 1,
                overflow: 'auto',
                p: 3
            }}
            {...other}
        >
            {value === index && children}
        </Box>
    );
};

interface MetadataTab {
    label: string;
    content: React.ReactNode;
}

interface MetadataSectionProps {
    tabs: MetadataTab[];
    defaultTab?: number;
    onTabChange?: (newValue: number) => void;
}

const MetadataSection: React.FC<MetadataSectionProps> = ({
    tabs,
    defaultTab = 0,
    onTabChange
}) => {
    const [value, setValue] = React.useState(defaultTab);

    const handleChange = (event: React.SyntheticEvent, newValue: number) => {
        setValue(newValue);
        if (onTabChange) {
            onTabChange(newValue);
        }
    };

    return (
        <Paper
            elevation={0}
            sx={{
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                bgcolor: 'background.default'
            }}
        >
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                <Tabs
                    value={value}
                    onChange={handleChange}
                    aria-label="metadata tabs"
                    sx={{
                        '& .MuiTab-root': {
                            textTransform: 'none',
                            fontSize: '1rem',
                            fontWeight: 'normal',
                            minWidth: 120,
                        }
                    }}
                >
                    {tabs.map((tab, index) => (
                        <Tab
                            key={index}
                            label={tab.label}
                            id={`metadata-tab-${index}`}
                            aria-controls={`metadata-tabpanel-${index}`}
                        />
                    ))}
                </Tabs>
            </Box>

            {tabs.map((tab, index) => (
                <TabPanel key={index} value={value} index={index}>
                    {tab.content}
                </TabPanel>
            ))}
        </Paper>
    );
};

export default MetadataSection;

import React, { useState } from 'react';
import { Typography, Tabs, Tab, Box, Paper, Grid, Card, CardContent, Divider, Button } from '@mui/material';
import { Assessment, CompareArrows, HighQuality, CheckCircle, Timer } from '@mui/icons-material';
import DeduplicationComponent from './deduplicationReview';
import QualityCheckComponent from './videoReview';
import VideoReviewInterface from '../components/VideoReviewInterface';

interface DashboardData {
    totalPendingReviews: number;
    deduplicationReviews: number;
    qualityCheckReviews: number;
    completedToday: number;
    averageReviewTime: string;
}

interface DashboardCardProps {
    title: string;
    value: number | string;
    icon: React.ReactNode;
    onClick?: () => void;
}

interface TabPanelProps {
    children?: React.ReactNode;
    value: number;
    index: number;
}

const ReviewQueue: React.FC = () => {
    const [value, setValue] = useState(0);
    const [showVideoReview, setShowVideoReview] = useState(false);

    const handleChange = (event: React.SyntheticEvent, newValue: number) => {
        setValue(newValue);
    };

    // Sample data for the dashboard
    const dashboardData: DashboardData = {
        totalPendingReviews: 8,
        deduplicationReviews: 5,
        qualityCheckReviews: 3,
        completedToday: 12,
        averageReviewTime: '5 minutes',
    };

    const DashboardCard: React.FC<DashboardCardProps> = ({ title, value, icon, onClick }) => (
        <Card
            elevation={3}
            sx={{
                height: '100%',
                cursor: onClick ? 'pointer' : 'default',
                '&:hover': onClick ? {
                    backgroundColor: 'action.hover',
                } : {}
            }}
            onClick={onClick}
        >
            <CardContent sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
                {icon}
                <Typography variant="h6" component="div" sx={{ mt: 2, mb: 1 }}>
                    {title}
                </Typography>
                <Typography variant="h4" color="primary">
                    {value}
                </Typography>
                {onClick && (
                    <Button
                        variant="text"
                        color="primary"
                        sx={{ mt: 1 }}
                    >
                        View Queue
                    </Button>
                )}
            </CardContent>
        </Card>
    );

    if (showVideoReview) {
        return <VideoReviewInterface onClose={() => setShowVideoReview(false)} />;
    }

    return (
        <Box sx={{ pt: 8, px: 4 }}>
            <Typography variant="h4" gutterBottom>
                Review Queue Dashboard
            </Typography>

            {/* Dashboard Section */}
            <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid item xs={12} sm={6} md={4} lg={2.4}>
                    <DashboardCard
                        title="Total Pending Reviews"
                        value={dashboardData.totalPendingReviews}
                        icon={<Assessment fontSize="large" color="primary" />}
                    />
                </Grid>
                <Grid item xs={12} sm={6} md={4} lg={2.4}>
                    <DashboardCard
                        title="Deduplication Reviews"
                        value={dashboardData.deduplicationReviews}
                        icon={<CompareArrows fontSize="large" color="primary" />}
                    />
                </Grid>
                <Grid item xs={12} sm={6} md={4} lg={2.4}>
                    <DashboardCard
                        title="Quality Check Reviews"
                        value={dashboardData.qualityCheckReviews}
                        icon={<HighQuality fontSize="large" color="primary" />}
                        onClick={() => setShowVideoReview(true)}
                    />
                </Grid>
                <Grid item xs={12} sm={6} md={4} lg={2.4}>
                    <DashboardCard
                        title="Completed Today"
                        value={dashboardData.completedToday}
                        icon={<CheckCircle fontSize="large" color="primary" />}
                    />
                </Grid>
                <Grid item xs={12} sm={6} md={4} lg={2.4}>
                    <DashboardCard
                        title="Average Review Time"
                        value={dashboardData.averageReviewTime}
                        icon={<Timer fontSize="large" color="primary" />}
                    />
                </Grid>
            </Grid>

            <Divider sx={{ mb: 4 }} />

            {/* Review Tabs */}
            <Paper sx={{ mb: 4 }}>
                <Tabs value={value} onChange={handleChange} aria-label="review types">
                    <Tab label="Deduplication" />
                    <Tab label="Quality Check" />
                </Tabs>
                <Box sx={{ p: 3 }}>
                    <TabPanel value={value} index={0}>
                        <DeduplicationComponent />
                    </TabPanel>
                    <TabPanel value={value} index={1}>
                        <QualityCheckComponent />
                    </TabPanel>
                </Box>
            </Paper>
        </Box>
    );
};

const TabPanel: React.FC<TabPanelProps> = (props) => {
    const { children, value, index, ...other } = props;

    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`simple-tabpanel-${index}`}
            aria-labelledby={`simple-tab-${index}`}
            {...other}
        >
            {value === index && (
                <Box sx={{ p: 3 }}>
                    {children}
                </Box>
            )}
        </div>
    );
};

export default ReviewQueue;

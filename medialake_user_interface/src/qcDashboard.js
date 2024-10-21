import React from 'react';
import { Typography, Grid, Paper } from '@mui/material';

const qcDashboard = () => {
    return (
        <div>
            <Typography variant="h4" gutterBottom>
                Dashboard
            </Typography>
            <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6">Pending Reviews</Typography>
                        <Typography variant="body1">Deduplication: 5</Typography>
                        <Typography variant="body1">Quality Check: 3</Typography>
                    </Paper>
                </Grid>
                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6">Recent Activity</Typography>
                        <Typography variant="body1">Last review: 2 hours ago</Typography>
                        <Typography variant="body1">Total reviews today: 12</Typography>
                    </Paper>
                </Grid>
            </Grid>
        </div>
    );
};

export default qcDashboard;

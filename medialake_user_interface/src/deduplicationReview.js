import React from 'react';
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Button } from '@mui/material';

const DeduplicationComponent = () => {
    const data = [
        { id: 1, title: 'Image 1', type: 'Image', dateAdded: '2024-10-14', priority: 'High' },
        { id: 2, title: 'Video 1', type: 'Video', dateAdded: '2024-10-15', priority: 'Medium' },
        { id: 3, title: 'Image 2', type: 'Image', dateAdded: '2024-10-15', priority: 'Low' },
    ];

    return (
        <TableContainer component={Paper}>
            <Table>
                <TableHead>
                    <TableRow>
                        <TableCell>Title</TableCell>
                        <TableCell>Type</TableCell>
                        <TableCell>Date Added</TableCell>
                        <TableCell>Priority</TableCell>
                        <TableCell>Action</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {data.map((row) => (
                        <TableRow key={row.id}>
                            <TableCell>{row.title}</TableCell>
                            <TableCell>{row.type}</TableCell>
                            <TableCell>{row.dateAdded}</TableCell>
                            <TableCell>{row.priority}</TableCell>
                            <TableCell>
                                <Button variant="contained" size="small">Review</Button>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );
};

export default DeduplicationComponent;

import React from 'react';
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Button } from '@mui/material';

// Add interface for data structure
interface QualityCheckItem {
    id: number;
    title: string;
    type: 'Video' | 'Image';
    dateAdded: string;
    priority: 'High' | 'Medium' | 'Low';
}

// Add React.FC type
const QualityCheckComponent: React.FC = () => {
    const data: QualityCheckItem[] = [
        { id: 1, title: 'Video 2', type: 'Video', dateAdded: '2024-10-14', priority: 'High' },
        { id: 2, title: 'Image 3', type: 'Image', dateAdded: '2024-10-15', priority: 'Low' },
        { id: 3, title: 'Video 3', type: 'Video', dateAdded: '2024-10-15', priority: 'Medium' },
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

export default QualityCheckComponent;

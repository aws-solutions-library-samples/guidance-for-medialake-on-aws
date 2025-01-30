import React from 'react';
import { Box, TextField } from '@mui/material';

interface PipelineNameInputProps {
    value: string;
    onChange: (value: string) => void;
}

const PipelineNameInput: React.FC<PipelineNameInputProps> = ({ value, onChange }) => {
    return (
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
            <TextField
                fullWidth
                variant="outlined"
                size="small"
                label="Pipeline Name"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                sx={{
                    '& .MuiOutlinedInput-root': {
                        borderRadius: '8px',
                    },
                }}
            />
        </Box>
    );
};

export default PipelineNameInput; 
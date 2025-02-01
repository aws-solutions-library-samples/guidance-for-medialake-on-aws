import React from 'react';
import { TextField } from '@mui/material';

interface PipelineNameInputProps {
    value: string;
    onChange: (value: string) => void;
}

const PipelineNameInput: React.FC<PipelineNameInputProps> = ({ value, onChange }) => {
    return (
        <TextField
            fullWidth
            variant="outlined"
            size="small"
            placeholder="Pipeline Name"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            sx={{
                '& .MuiOutlinedInput-root': {
                    borderRadius: '4px',
                    backgroundColor: 'transparent',
                },
                width: '300px'
            }}
        />
    );
};

export default PipelineNameInput; 
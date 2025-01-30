import React from 'react';
import { Box, Stack, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { PipelineNameInput } from './';

export interface PipelineToolbarProps {
    onSave: () => Promise<void>;
    isLoading: boolean;
    pipelineName: string;
    onPipelineNameChange: (value: string) => void;
}

const PipelineToolbar: React.FC<PipelineToolbarProps> = ({
    onSave,
    isLoading,
    pipelineName,
    onPipelineNameChange
}) => {
    const navigate = useNavigate();

    const handleCancel = () => {
        navigate('/pipelines');
    };

    return (
        <Box
            sx={{
                width: '100%',
                height: '64px',
                px: 2,
                py: 1,
                borderBottom: '1px solid',
                borderColor: 'divider',
                bgcolor: 'background.paper',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
            }}
        >
            <PipelineNameInput value={pipelineName} onChange={onPipelineNameChange} />
            <Stack direction="row" spacing={2}>
                <Button
                    variant="outlined"
                    color="inherit"
                    onClick={handleCancel}
                >
                    Cancel
                </Button>
                <Button
                    variant="contained"
                    color="primary"
                    onClick={onSave}
                    disabled={isLoading || !pipelineName.trim()}
                >
                    {isLoading ? 'Saving...' : 'Save'}
                </Button>
            </Stack>
        </Box>
    );
};

export default PipelineToolbar; 

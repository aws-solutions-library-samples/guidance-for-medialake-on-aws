import React from 'react';
import { Stack, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { PipelineNameInput } from './';
import { useSidebar } from '@/contexts/SidebarContext';
import { useRightSidebar } from '@/components/common/RightSidebar/SidebarContext';

export interface PipelineToolbarProps {
    onSave: () => Promise<void>;
    isLoading: boolean;
    pipelineName: string;
    onPipelineNameChange: (value: string) => void;
}

const DRAWER_WIDTH = 260;
const COLLAPSED_DRAWER_WIDTH = 72;
const RIGHT_SIDEBAR_WIDTH = 300;
const RIGHT_SIDEBAR_COLLAPSED_WIDTH = 8;

const PipelineToolbar: React.FC<PipelineToolbarProps> = ({
    onSave,
    isLoading,
    pipelineName,
    onPipelineNameChange,
}) => {
    const navigate = useNavigate();
    const { isCollapsed: isLeftSidebarCollapsed } = useSidebar();
    const { isExpanded: isRightSidebarExpanded } = useRightSidebar();

    const handleCancel = () => {
        navigate('/pipelines');
    };

    const commonStyles = {
        backdropFilter: 'blur(8px)',
        bgcolor: theme => `${theme.palette.background.paper}CC`,
        '&:hover': {
            bgcolor: theme => `${theme.palette.background.paper}EE`,
        }
    };

    return (
        <>
            <Stack
                direction="row"
                spacing={2}
                sx={{
                    position: 'fixed',
                    zIndex: 1100,
                    left: (isLeftSidebarCollapsed ? COLLAPSED_DRAWER_WIDTH : DRAWER_WIDTH) + 16,
                    top: '72px',
                    '& .MuiInputBase-root': {
                        bgcolor: 'transparent',
                        '& input': {
                            ...commonStyles,
                            px: 2,
                            py: 1,
                            borderRadius: '4px',
                        }
                    }
                }}
            >
                <PipelineNameInput
                    value={pipelineName}
                    onChange={onPipelineNameChange}
                />
            </Stack>
            <Stack
                direction="row"
                spacing={2}
                sx={{
                    position: 'fixed',
                    zIndex: 1100,
                    right: (isRightSidebarExpanded ? RIGHT_SIDEBAR_WIDTH : RIGHT_SIDEBAR_COLLAPSED_WIDTH) + 16,
                    top: '72px',
                    '& .MuiButton-root': commonStyles
                }}
            >
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
        </>
    );
};

export default PipelineToolbar;

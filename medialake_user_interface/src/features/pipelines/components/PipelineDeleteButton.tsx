import React from 'react';
import { IconButton, Tooltip } from '@mui/material';
import { Delete as DeleteIcon } from '@mui/icons-material';

interface PipelineDeleteButtonProps {
    id: string;
    name: string;
    isSystem: boolean;
}

export const PipelineDeleteButton: React.FC<PipelineDeleteButtonProps> = ({
    id,
    name,
    isSystem
}) => {
    const handleDelete = async () => {
        // Skip if system pipeline
        if (isSystem) {
            return;
        }

        // Use the browser's native confirm dialog directly
        if (window.confirm(`Are you sure you want to delete pipeline "${name}"? This action cannot be undone.`)) {
            try {
                // Get the auth token and base URL
                const token = localStorage.getItem('medialake-auth-token');
                const awsConfig = localStorage.getItem('medialake-aws-config');
                const baseURL = awsConfig ? JSON.parse(awsConfig)?.API?.REST?.RestApi?.endpoint || '' : '';

                // Call the API directly
                const response = await fetch(`${baseURL}/pipelines/${id}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': token ? `Bearer ${token}` : '',
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                        'Expires': '0'
                    },
                });

                if (response.ok) {
                    // Show success message
                    alert('Pipeline deleted successfully');
                    // Refresh the page
                    window.location.reload();
                } else {
                    // Show error message
                    alert('Failed to delete pipeline');
                }
            } catch (error) {
                console.error("Error deleting pipeline:", error);
                // Show error message
                alert(`Error deleting pipeline: ${error instanceof Error ? error.message : 'Unknown error'}`);
            }
        }
    };

    return (
        <Tooltip title="Delete Pipeline">
            <span>
                <IconButton
                    size="small"
                    onClick={handleDelete}
                    disabled={isSystem}
                >
                    <DeleteIcon fontSize="small" />
                </IconButton>
            </span>
        </Tooltip>
    );
};

import React, { useRef, ChangeEvent } from 'react';
import { Stack, Button, IconButton,Tooltip } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { PipelineNameInput } from './';
import { useSidebar } from '@/contexts/SidebarContext';
import { useRightSidebar } from '@/components/common/RightSidebar/SidebarContext';
import FileUploadIcon from '@mui/icons-material/FileUpload';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import { FaFileVideo } from 'react-icons/fa';
import type { Node, Edge, ReactFlowInstance } from 'reactflow';

export interface PipelineToolbarProps {
  onSave: () => Promise<void>;
  isLoading: boolean;
  pipelineName: string;
  onPipelineNameChange: (value: string) => void;
  reactFlowInstance: ReactFlowInstance | null;
  // New props to update the flow state
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
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
  reactFlowInstance,
  setNodes,
  setEdges,
}) => {
  const navigate = useNavigate();
  const { isCollapsed: isLeftSidebarCollapsed } = useSidebar();
  const { isExpanded: isRightSidebarExpanded } = useRightSidebar();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleCancel = () => {
    navigate('/pipelines');
  };

  const commonStyles = {
    backdropFilter: 'blur(8px)',
    bgcolor: (theme: any) => `${theme.palette.background.paper}CC`,
    '&:hover': {
      bgcolor: (theme: any) => `${theme.palette.background.paper}EE`,
    },
  };

  // Load a flow from a JSON file.
  const handleLoadFlow = (event: ChangeEvent<HTMLInputElement>) => {
    const fileReader = new FileReader();
    const files = event.target.files;
    if (files && files.length > 0) {
      fileReader.readAsText(files[0], 'UTF-8');
      fileReader.onload = (e) => {
        try {
          const flow = JSON.parse(e.target?.result as string);
          if (flow) {
            // Check if the flow uses the nodes/edges structure
            if (flow.nodes && flow.edges) {
              const fixedNodes = flow.nodes.map((node: any) => ({
                ...node,
                data: {
                  ...node.data,
                  // Check if the icon is an object (serialized React element)
                  icon:
                    node.data.icon &&
                    typeof node.data.icon === 'object' &&
                    node.data.icon.props
                      ? <FaFileVideo size={20} />
                      : node.data.icon,
                },
              }));
              setNodes(fixedNodes);
              setEdges(flow.edges);
            }
            // Alternatively, if the flow uses an "elements" array, split it into nodes and edges.
            else if (flow.elements) {
              const nodes = flow.elements.filter(
                (el: any) => !('source' in el && 'target' in el)
              );
              const edges = flow.elements.filter(
                (el: any) => 'source' in el && 'target' in el
              );
              const fixedNodes = nodes.map((node: any) => ({
                ...node,
                data: {
                  ...node.data,
                  icon:
                    node.data.icon &&
                    typeof node.data.icon === 'object' &&
                    node.data.icon.props
                      ? <FaFileVideo size={20} />
                      : node.data.icon,
                },
              }));
              setNodes(fixedNodes);
              setEdges(edges);
            }
            // Update viewport if available
            if (flow.viewport && reactFlowInstance) {
              const { x = 0, y = 0, zoom = 1 } = flow.viewport;
              reactFlowInstance.setViewport({ x, y, zoom });
            }
          }
        } catch (error) {
          console.error('Error parsing flow JSON', error);
        }
      };
    }
  };

  // Export the current flow as a JSON file.
  const onExport = (): void => {
    if (reactFlowInstance) {
      const flow = reactFlowInstance.toObject();
      const flowJson = JSON.stringify(flow, null, 2);
      const blob = new Blob([flowJson], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'flow.json';
      a.click();
      URL.revokeObjectURL(url);
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
          left:
            (isLeftSidebarCollapsed ? COLLAPSED_DRAWER_WIDTH : DRAWER_WIDTH) +
            16,
          top: '72px',
          '& .MuiInputBase-root': {
            bgcolor: 'transparent',
            '& input': {
              ...commonStyles,
              px: 2,
              py: 1,
              borderRadius: '4px',
            },
          },
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
          right:
            (isRightSidebarExpanded
              ? RIGHT_SIDEBAR_WIDTH
              : RIGHT_SIDEBAR_COLLAPSED_WIDTH) + 16,
          top: '72px',
          '& .MuiButton-root': commonStyles,
        }}
      >
        <Tooltip title="Export Pipeline">
        <IconButton onClick={onExport} aria-label="export">
          <FileDownloadIcon />
        </IconButton>
        </Tooltip>
        <Tooltip title="Import Pipeline">
        <IconButton
          onClick={() => fileInputRef.current?.click()}
          aria-label="import"
        >
          <FileUploadIcon />
        </IconButton>
        </Tooltip>
        <input
          type="file"
          accept="application/json"
          ref={fileInputRef}
          style={{ display: 'none' }}
          onChange={handleLoadFlow}
        />
        <Button variant="outlined" color="inherit" onClick={handleCancel}>
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

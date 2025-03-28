import React, { useRef, ChangeEvent } from 'react';
import { Stack, Button, Tooltip, Switch, FormControlLabel } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { PipelineNameInput } from './';
import { useSidebar } from '@/contexts/SidebarContext';
import { useRightSidebar } from '@/components/common/RightSidebar/SidebarContext';
import FileUploadIcon from '@mui/icons-material/FileUpload';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import ButtonGroup from '@mui/material/ButtonGroup';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import Grow from '@mui/material/Grow';
import Paper from '@mui/material/Paper';
import Popper from '@mui/material/Popper';
import MenuItem from '@mui/material/MenuItem';
import MenuList from '@mui/material/MenuList';
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
  active: boolean; // New prop for pipeline active state
  onActiveChange: (active: boolean) => void; // New prop for handling active state changes
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
  active,
  onActiveChange,
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

  // Split button functionality
  const [open, setOpen] = React.useState(false);
  const anchorRef = React.useRef<HTMLDivElement>(null);

  const handleToggle = () => {
    setOpen((prevOpen) => !prevOpen);
  };

  const handleClose = (event: Event) => {
    if (
      anchorRef.current &&
      anchorRef.current.contains(event.target as HTMLElement)
    ) {
      return;
    }

    setOpen(false);
  };

  const handleImport = () => {
    fileInputRef.current?.click();
    setOpen(false);
  };

  const handleExport = () => {
    onExport();
    setOpen(false);
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
        <input
          type="file"
          accept="application/json"
          ref={fileInputRef}
          style={{ display: 'none' }}
          onChange={handleLoadFlow}
        />
        <FormControlLabel
          control={
            <Switch
              checked={active}
              onChange={(e) => onActiveChange(e.target.checked)}
              color="primary"
            />
          }
          label={active ? "Active" : "Inactive"}
          sx={{ mr: 1 }}
        />
        <Button variant="outlined" color="inherit" onClick={handleCancel}>
          Cancel
        </Button>
        
        <React.Fragment>
          <ButtonGroup
            variant="contained"
            ref={anchorRef}
            aria-label="Pipeline actions"
          >
            <Button
              color="primary"
              onClick={onSave}
              disabled={isLoading || !pipelineName.trim()}
            >
              {isLoading ? 'Saving...' : 'Save'}
            </Button>
            <Button
              size="small"
              color="primary"
              aria-controls={open ? 'split-button-menu' : undefined}
              aria-expanded={open ? 'true' : undefined}
              aria-label="select pipeline action"
              aria-haspopup="menu"
              onClick={handleToggle}
            >
              <ArrowDropDownIcon />
            </Button>
          </ButtonGroup>
          <Popper
            sx={{ zIndex: 1200 }}
            open={open}
            anchorEl={anchorRef.current}
            role={undefined}
            transition
            disablePortal
          >
            {({ TransitionProps, placement }) => (
              <Grow
                {...TransitionProps}
                style={{
                  transformOrigin:
                    placement === 'bottom' ? 'center top' : 'center bottom',
                }}
              >
                <Paper>
                  <ClickAwayListener onClickAway={handleClose}>
                    <MenuList id="split-button-menu" autoFocusItem>
                      <MenuItem onClick={handleImport}>
                        <FileUploadIcon sx={{ mr: 1 }} /> Import Pipeline
                      </MenuItem>
                      <MenuItem onClick={handleExport}>
                        <FileDownloadIcon sx={{ mr: 1 }} /> Export Pipeline
                      </MenuItem>
                    </MenuList>
                  </ClickAwayListener>
                </Paper>
              </Grow>
            )}
          </Popper>
        </React.Fragment>
      </Stack>
    </>
  );
};

export default PipelineToolbar;

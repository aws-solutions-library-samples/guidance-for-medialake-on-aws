import React, { useRef, ChangeEvent } from 'react';
import { Stack, Button, Tooltip, FormControlLabel, Box } from '@mui/material';
import { IconSwitch } from '@/components/common';
import ToggleOnIcon from '@mui/icons-material/ToggleOn';
import ToggleOffIcon from '@mui/icons-material/ToggleOff';
import { useNavigate } from 'react-router-dom';
import { PipelineNameInput } from './';
import { useSidebar } from '@/contexts/SidebarContext';
import { useRightSidebar, COLLAPSED_WIDTH } from '@/components/common/RightSidebar/SidebarContext';
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
import { drawerWidth, collapsedDrawerWidth } from '@/constants';

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
  // Add prop for updating formData with imported pipeline
  updateFormData?: (nodes: Node[], edges: Edge[]) => void;
}

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
  updateFormData,
}) => {
  const navigate = useNavigate();
  const { isCollapsed: isLeftSidebarCollapsed } = useSidebar();
  const { isExpanded: isRightSidebarExpanded, width } = useRightSidebar();
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
              
              // Update formData with imported nodes and edges
              if (updateFormData) {
                updateFormData(fixedNodes, flow.edges);
              }
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
              
              // Update formData with imported nodes and edges
              if (updateFormData) {
                updateFormData(fixedNodes, edges);
              }
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

  // Import/Export dropdown functionality
  const [importExportOpen, setImportExportOpen] = React.useState(false);
  const importExportRef = React.useRef<HTMLDivElement>(null);

  const handleImportExportToggle = () => {
    setImportExportOpen((prevOpen) => !prevOpen);
  };

  const handleImportExportClose = (event: Event) => {
    if (
      importExportRef.current &&
      importExportRef.current.contains(event.target as HTMLElement)
    ) {
      return;
    }
    setImportExportOpen(false);
  };

  const handleImport = () => {
    fileInputRef.current?.click();
    setImportExportOpen(false);
  };

  const handleExport = () => {
    onExport();
    setImportExportOpen(false);
  };

  return (
    <>
      {/* Container to calculate available space */}
      <Box
        sx={{
          position: 'fixed',
          zIndex: 1100,
          left: (isLeftSidebarCollapsed ? collapsedDrawerWidth : drawerWidth) + 16,
          right: (isRightSidebarExpanded ? width : COLLAPSED_WIDTH) + 16,
          top: '72px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        {/* Left side - Pipeline Name */}
        <Box
          sx={{
            '& .MuiInputBase-root': {
              bgcolor: 'transparent',
              '& input': {
                ...commonStyles,
                px: 2,
                py: 1,
                borderRadius: '4px',
              },
            },
            maxWidth: {
              // Responsive width based on available space
              xs: '200px',
              sm: '250px',
              md: '300px',
            },
          }}
        >
          <PipelineNameInput
            value={pipelineName}
            onChange={onPipelineNameChange}
          />
        </Box>

        {/* Right side - Controls */}
        <Stack
          direction="row"
          spacing={2}
          sx={{
            '& .MuiButton-root': commonStyles,
          }}
        >
          {/* Hidden file input for import */}
          <input
            type="file"
            accept="application/json"
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={handleLoadFlow}
          />

          {/* Import/Export ButtonGroup */}
          <ButtonGroup
            variant="outlined"
            ref={importExportRef}
            aria-label="Pipeline file operations"
          >
            <Button
              color="inherit"
              onClick={handleImport}
              startIcon={<FileUploadIcon />}
            >
              Import
            </Button>
            <Button
              size="small"
              color="inherit"
              aria-controls={importExportOpen ? 'import-export-menu' : undefined}
              aria-expanded={importExportOpen ? 'true' : undefined}
              aria-label="select import/export action"
              aria-haspopup="menu"
              onClick={handleImportExportToggle}
            >
              <ArrowDropDownIcon />
            </Button>
          </ButtonGroup>

          {/* Import/Export Dropdown */}
          <Popper
            sx={{ zIndex: 1200 }}
            open={importExportOpen}
            anchorEl={importExportRef.current}
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
                  <ClickAwayListener onClickAway={handleImportExportClose}>
                    <MenuList id="import-export-menu" autoFocusItem>
                      <MenuItem onClick={handleExport}>
                        <FileDownloadIcon sx={{ mr: 1 }} /> Export Pipeline
                      </MenuItem>
                    </MenuList>
                  </ClickAwayListener>
                </Paper>
              </Grow>
            )}
          </Popper>

          {/* Active/Inactive Toggle */}
          <FormControlLabel
            control={
              <IconSwitch
                checked={active}
                onChange={(e) => onActiveChange(e.target.checked)}
                color="primary"
                onIcon={<ToggleOnIcon fontSize="large" />}
                offIcon={<ToggleOffIcon fontSize="large" />}
                onColor="#2e7d32"
                offColor="#757575"
                trackOnColor="#b2ebf2"
                trackOffColor="#cfd8dc"
              />
            }
            label={active ? "Active" : "Inactive"}
            sx={{ mx: 2 }}
          />

          {/* Action Buttons */}
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
      </Box>
    </>
  );
};

export default PipelineToolbar;

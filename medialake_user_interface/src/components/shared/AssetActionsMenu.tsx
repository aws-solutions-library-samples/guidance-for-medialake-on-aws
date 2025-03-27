import React from 'react';
import {
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  CircularProgress,
  useTheme,
  alpha
} from '@mui/material';
import {
  Edit as EditIcon,
  Share as ShareIcon,
  Download as DownloadIcon
} from '@mui/icons-material';

interface AssetActionsMenuProps<T> {
  anchorEl: HTMLElement | null;
  selectedAsset: T | null;
  onClose: () => void;
  onAction: (action: string) => void;
  actions?: Array<{
    id: string;
    label: string;
  }>;
  isLoading: {
    rename: boolean;
    share: boolean;
    download: boolean;
    delete: boolean;
  };
}

function AssetActionsMenu<T>({
  anchorEl,
  selectedAsset,
  onClose,
  onAction,
  actions = [
    { id: 'rename', label: 'Rename' },
    { id: 'share', label: 'Share' },
    { id: 'download', label: 'Download' }
  ],
  isLoading
}: AssetActionsMenuProps<T>) {
  const theme = useTheme();

  const getActionIcon = (actionId: string) => {
    switch (actionId) {
      case 'rename':
        return <EditIcon fontSize="small" />;
      case 'share':
        return <ShareIcon fontSize="small" />;
      case 'download':
        return <DownloadIcon fontSize="small" />;
      default:
        return null;
    }
  };

  const isActionLoading = (actionId: string) => {
    switch (actionId) {
      case 'rename':
        return isLoading.rename;
      case 'share':
        return isLoading.share;
      case 'download':
        return isLoading.download;
      default:
        return false;
    }
  };

  return (
    <Menu
      anchorEl={anchorEl}
      open={Boolean(anchorEl)}
      onClose={onClose}
      MenuListProps={{
        'aria-labelledby': selectedAsset ? `asset-menu-button-${selectedAsset}` : undefined
      }}
      anchorOrigin={{
        vertical: 'bottom',
        horizontal: 'right',
      }}
      transformOrigin={{
        vertical: 'top',
        horizontal: 'right',
      }}
      PaperProps={{
        elevation: 0,
        sx: {
          borderRadius: '8px',
          minWidth: 200,
          mt: 1,
          border: theme => `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          backgroundColor: theme => theme.palette.background.paper,
          overflow: 'visible',
          position: 'fixed',
          zIndex: 1400,
        },
      }}
      slotProps={{
        paper: {
          sx: {
            overflow: 'visible',
            position: 'fixed',
          }
        }
      }}
    >
      {actions.map(action => (
        <MenuItem
          key={action.id}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onAction(action.id);
          }}
          disabled={isActionLoading(action.id)}
        >
          <ListItemIcon>
            {isActionLoading(action.id) ? (
              <CircularProgress size={20} />
            ) : (
              getActionIcon(action.id)
            )}
          </ListItemIcon>
          <ListItemText>{action.label}</ListItemText>
        </MenuItem>
      ))}
    </Menu>
  );
}

export default AssetActionsMenu;

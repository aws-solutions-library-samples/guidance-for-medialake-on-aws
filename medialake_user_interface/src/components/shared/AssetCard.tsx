import React, { useState } from 'react';
import {
  Card,
  CardMedia,
  CardContent,
  Typography,
  Box,
  IconButton,
  TextField,
  InputAdornment,
  Tooltip,
  useTheme,
  alpha,
  Chip,
  Stack
} from '@mui/material';
import {
  Delete as DeleteIcon,
  MoreVert as MoreVertIcon,
  Edit as EditIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  Image as ImageIcon,
  VideoFile as VideoFileIcon,
  AudioFile as AudioFileIcon,
  Description as DescriptionIcon
} from '@mui/icons-material';

interface AssetCardProps {
  id: string;
  name: string;
  thumbnailUrl?: string;
  proxyUrl?: string;
  assetType: string;
  fields: { id: string; label: string; visible: boolean }[];
  renderField: (fieldId: string) => React.ReactNode;
  onAssetClick: () => void;
  onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
  onMenuClick: (event: React.MouseEvent<HTMLElement>) => void;
  onEditClick: (event: React.MouseEvent<HTMLElement>) => void;
  isEditing: boolean;
  editedName?: string;
  onEditNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete: (save: boolean) => void;
  cardSize: 'small' | 'medium' | 'large';
  aspectRatio: 'vertical' | 'square' | 'horizontal';
  thumbnailScale: 'fit' | 'fill';
  showMetadata: boolean;
  onImageError?: (event: React.SyntheticEvent<HTMLImageElement, Event>) => void;
  isRenaming?: boolean;
}

const AssetCard: React.FC<AssetCardProps> = ({
  id,
  name,
  thumbnailUrl,
  proxyUrl,
  assetType,
  fields,
  renderField,
  onAssetClick,
  onDeleteClick,
  onMenuClick,
  onEditClick,
  isEditing,
  editedName,
  onEditNameChange,
  onEditNameComplete,
  cardSize,
  aspectRatio,
  thumbnailScale,
  showMetadata,
  onImageError,
  isRenaming = false
}) => {
  const theme = useTheme();
  const [isHovered, setIsHovered] = useState(false);

  // Get aspect ratio based on setting
  const getAspectRatio = () => {
    switch (aspectRatio) {
      case 'vertical':
        return '2/3';
      case 'horizontal':
        return '16/9';
      case 'square':
      default:
        return '1/1';
    }
  };

  // Get thumbnail height based on card size
  const getThumbnailHeight = () => {
    switch (cardSize) {
      case 'small':
        return 120;
      case 'large':
        return 240;
      case 'medium':
      default:
        return 180;
    }
  };

  // Get asset type icon
  const getAssetTypeIcon = () => {
    switch (assetType.toLowerCase()) {
      case 'image':
        return <ImageIcon />;
      case 'video':
        return <VideoFileIcon />;
      case 'audio':
        return <AudioFileIcon />;
      default:
        return <DescriptionIcon />;
    }
  };

  // Handle key down in edit mode
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter') {
      onEditNameComplete(true);
    } else if (event.key === 'Escape') {
      onEditNameComplete(false);
    }
  };

  return (
    <Card
      elevation={0}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '12px',
        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          borderColor: theme.palette.primary.main,
          boxShadow: `0 4px 12px ${alpha(theme.palette.primary.main, 0.1)}`,
          transform: 'translateY(-2px)',
          zIndex: 10, // Add higher z-index when hovered
        },
        position: 'relative',
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Thumbnail */}
      <Box
        onClick={onAssetClick}
        sx={{
          position: 'relative',
          aspectRatio: getAspectRatio(),
          cursor: 'pointer',
          backgroundColor: alpha(theme.palette.common.black, 0.03),
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          overflow: 'hidden',
          borderTopLeftRadius: '12px',
          borderTopRightRadius: '12px',
        }}
      >
        {thumbnailUrl ? (
          <CardMedia
            component="img"
            image={thumbnailUrl}
            alt={name}
            sx={{
              height: '100%',
              width: '100%',
              objectFit: thumbnailScale === 'fill' ? 'cover' : 'contain',
            }}
            onError={(e) => {
              console.error('Image load error:', e);
              if (onImageError) onImageError(e);
              // Set a default placeholder based on asset type
              (e.target as HTMLImageElement).src = `/placeholder-${assetType.toLowerCase()}.png`;
            }}
            data-image-id={id}
          />
        ) : (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '100%',
              width: '100%',
              color: alpha(theme.palette.text.primary, 0.5),
              fontSize: '3rem',
            }}
          >
            {getAssetTypeIcon()}
          </Box>
        )}

        {/* Overlay with actions */}
        {isHovered && (
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              right: 0,
              p: 0.5,
              display: 'flex',
              gap: 0.5,
              backgroundColor: alpha(theme.palette.background.paper, 0.8),
              borderBottomLeftRadius: '12px',
            }}
          >
            <Tooltip title="Edit">
              <IconButton
                size="small"
                onClick={onEditClick}
                sx={{ color: theme.palette.text.secondary }}
              >
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete">
              <IconButton
                size="small"
                onClick={onDeleteClick}
                sx={{ color: theme.palette.error.main }}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="More">
              <IconButton
                size="small"
                onClick={onMenuClick}
                id={`asset-menu-button-${id}`}
                aria-controls={`asset-menu-${id}`}
                aria-haspopup="true"
                sx={{ color: theme.palette.text.secondary }}
              >
                <MoreVertIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        )}

        {/* Asset type badge */}
        <Box
          sx={{
            position: 'absolute',
            bottom: 8,
            left: 8,
            backgroundColor: alpha(theme.palette.background.paper, 0.8),
            borderRadius: '8px',
            px: 1,
            py: 0.5,
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
          }}
        >
          {getAssetTypeIcon()}
          <Typography variant="caption" fontWeight="medium">
            {assetType}
          </Typography>
        </Box>
      </Box>

      {/* Content */}
      <CardContent sx={{ flexGrow: 1, p: 1.5, pt: 1 }}>
        {isEditing ? (
          <TextField
            fullWidth
            variant="outlined"
            size="small"
            value={editedName}
            onChange={onEditNameChange}
            onKeyDown={handleKeyDown}
            autoFocus
            disabled={isRenaming}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    onClick={() => onEditNameComplete(true)}
                    edge="end"
                    disabled={isRenaming}
                  >
                    <CheckIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    size="small"
                    onClick={() => onEditNameComplete(false)}
                    edge="end"
                    disabled={isRenaming}
                  >
                    <CloseIcon fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        ) : (
          <Tooltip title={name}>
            <Typography
              variant="subtitle2"
              noWrap
              sx={{
                mb: 1,
                fontWeight: 500,
                cursor: 'pointer',
              }}
              onClick={onAssetClick}
            >
              {name}
            </Typography>
          </Tooltip>
        )}

        {showMetadata && fields.length > 0 && (
          <Stack spacing={0.5} mt={1}>
            {fields.map(
              (field) =>
                field.visible && (
                  <Box
                    key={field.id}
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ fontWeight: 500 }}
                    >
                      {field.label}:
                    </Typography>
                    <Typography variant="caption" noWrap>
                      {renderField(field.id)}
                    </Typography>
                  </Box>
                )
            )}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
};

export default AssetCard;

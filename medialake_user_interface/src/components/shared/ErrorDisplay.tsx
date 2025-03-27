import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Collapse,
  Alert,
  AlertTitle,
  useTheme
} from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

interface ErrorDisplayProps {
  title: string;
  message: string;
  detailedMessage?: string;
}

const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  title,
  message,
  detailedMessage
}) => {
  const theme = useTheme();
  const [showDetails, setShowDetails] = useState(false);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '30vh',
        textAlign: 'center',
        gap: 2,
        my: 4
      }}
    >
      <Paper
        elevation={0}
        sx={{
          p: 4,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2,
          bgcolor: 'background.paper',
          borderRadius: 2,
          width: '100%',
          maxWidth: 600
        }}
      >
        <ErrorOutlineIcon
          sx={{
            fontSize: 64,
            color: theme.palette.error.main,
            mb: 2
          }}
        />
        <Typography variant="h5" color="error" gutterBottom>
          {title}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {message}
        </Typography>

        {detailedMessage && (
          <>
            <Button
              variant="text"
              color="primary"
              onClick={() => setShowDetails(!showDetails)}
              endIcon={showDetails ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              sx={{ mt: 1 }}
            >
              {showDetails ? 'Hide Details' : 'Show Details'}
            </Button>

            <Collapse in={showDetails} sx={{ width: '100%' }}>
              <Alert severity="error" sx={{ mt: 2, textAlign: 'left' }}>
                <AlertTitle>Error Details</AlertTitle>
                <Typography variant="body2" component="pre" sx={{ 
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontFamily: 'monospace',
                  fontSize: '0.8rem'
                }}>
                  {detailedMessage}
                </Typography>
              </Alert>
            </Collapse>
          </>
        )}
      </Paper>
    </Box>
  );
};

export default ErrorDisplay;

import React, { useState } from 'react';
import { 
  Box, 
  Paper, 
  Typography, 
  Accordion, 
  AccordionSummary, 
  AccordionDetails,
  Chip,
  Button,
  Alert
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useAuth } from '../common/hooks/auth-context';
import { usePermission } from '../permissions/hooks/usePermission';
import { StorageHelper } from '../common/helpers/storage-helper';

/**
 * Debug component to help troubleshoot authentication and permission issues
 * Remove this component in production
 */
export const DebugPermissions: React.FC = () => {
  const { isAuthenticated, isLoading, isInitialized } = useAuth();
  const { ability, loading: permissionLoading } = usePermission();
  const [showDebug, setShowDebug] = useState(false);

  const getTokenInfo = () => {
    try {
      const token = StorageHelper.getToken();
      if (!token) return { hasToken: false };
      
      const tokenParts = token.split('.');
      if (tokenParts.length !== 3) return { hasToken: true, valid: false };
      
      const payload = JSON.parse(atob(tokenParts[1]));
      const exp = payload.exp;
      const now = Math.floor(Date.now() / 1000);
      const isExpired = exp < now;
      
      return {
        hasToken: true,
        valid: true,
        expired: isExpired,
        groups: payload['cognito:groups'] || [],
        customPermissions: payload['custom:permissions'] ? JSON.parse(payload['custom:permissions']) : [],
        username: payload['cognito:username'] || payload.email,
        expiresIn: exp - now
      };
    } catch (error) {
      return { hasToken: true, valid: false, error: error.message };
    }
  };

  const tokenInfo = getTokenInfo();

  if (!showDebug) {
    return (
      <Box sx={{ position: 'fixed', top: 10, right: 10, zIndex: 9999 }}>
        <Button 
          variant="outlined" 
          size="small" 
          onClick={() => setShowDebug(true)}
          sx={{ bgcolor: 'background.paper' }}
        >
          Debug Auth
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ 
      position: 'fixed', 
      top: 10, 
      right: 10, 
      width: 400, 
      maxHeight: '80vh',
      overflow: 'auto',
      zIndex: 9999 
    }}>
      <Paper elevation={8} sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Auth Debug</Typography>
          <Button size="small" onClick={() => setShowDebug(false)}>Close</Button>
        </Box>

        <Alert severity={isAuthenticated ? "success" : "error"} sx={{ mb: 2 }}>
          Status: {isAuthenticated ? "Authenticated" : "Not Authenticated"}
        </Alert>

        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>Auth State</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Chip 
                label={`Loading: ${isLoading}`} 
                color={isLoading ? "warning" : "default"}
                size="small"
              />
              <Chip 
                label={`Initialized: ${isInitialized}`} 
                color={isInitialized ? "success" : "error"}
                size="small"
              />
              <Chip 
                label={`Permission Loading: ${permissionLoading}`} 
                color={permissionLoading ? "warning" : "default"}
                size="small"
              />
            </Box>
          </AccordionDetails>
        </Accordion>

        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>Token Info</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Chip 
                label={`Has Token: ${tokenInfo.hasToken}`} 
                color={tokenInfo.hasToken ? "success" : "error"}
                size="small"
              />
              {tokenInfo.hasToken && (
                <>
                  <Chip 
                    label={`Valid: ${tokenInfo.valid}`} 
                    color={tokenInfo.valid ? "success" : "error"}
                    size="small"
                  />
                  {tokenInfo.valid && (
                    <>
                      <Chip 
                        label={`Expired: ${tokenInfo.expired}`} 
                        color={tokenInfo.expired ? "error" : "success"}
                        size="small"
                      />
                      <Typography variant="caption">
                        Username: {tokenInfo.username}
                      </Typography>
                      <Typography variant="caption">
                        Expires in: {tokenInfo.expiresIn}s
                      </Typography>
                    </>
                  )}
                </>
              )}
            </Box>
          </AccordionDetails>
        </Accordion>

        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>Groups</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {tokenInfo.groups?.length > 0 ? (
                tokenInfo.groups.map((group: string) => (
                  <Chip key={group} label={group} size="small" />
                ))
              ) : (
                <Typography variant="caption">No groups</Typography>
              )}
            </Box>
          </AccordionDetails>
        </Accordion>

        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>Custom Permissions</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              {tokenInfo.customPermissions?.length > 0 ? (
                tokenInfo.customPermissions.map((permission: string) => (
                  <Chip key={permission} label={permission} size="small" />
                ))
              ) : (
                <Typography variant="caption">No custom permissions</Typography>
              )}
            </Box>
          </AccordionDetails>
        </Accordion>

        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>Ability Rules</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box>
              <Typography variant="caption" component="pre" sx={{ fontSize: '10px', overflow: 'auto' }}>
                {JSON.stringify(ability.rules, null, 2)}
              </Typography>
            </Box>
          </AccordionDetails>
        </Accordion>
      </Paper>
    </Box>
  );
}; 
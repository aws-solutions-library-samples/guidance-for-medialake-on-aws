/**
 * Upgrade History View Component
 * Displays paginated list of past upgrades
 */

import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  CircularProgress,
  Alert,
  Button,
  Tooltip,
  IconButton,
} from "@mui/material";
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  NavigateNext as NavigateNextIcon,
  NavigateBefore as NavigateBeforeIcon,
  History as HistoryIcon,
} from "@mui/icons-material";
import { EmptyTableState } from "@/components/common/table";
import { useTranslation } from "react-i18next";
import { getUpgradeHistory, type UpgradeRecord } from "@/api/updatesService";

export const UpgradeHistoryView: React.FC = () => {
  const { t } = useTranslation();

  const [history, setHistory] = useState<UpgradeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | undefined>();
  const [hasNextPage, setHasNextPage] = useState(false);

  const fetchHistory = async (cursor?: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await getUpgradeHistory(10, cursor);
      setHistory(response.data);
      setNextCursor(response.pagination?.next_cursor);
      setHasNextPage(response.pagination?.has_next_page || false);
    } catch (err: any) {
      setError(err.message || "Failed to load upgrade history");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleNextPage = () => {
    if (nextCursor) {
      fetchHistory(nextCursor);
    }
  };

  const formatDuration = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  if (loading && history.length === 0) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        {error}
      </Alert>
    );
  }

  if (history.length === 0) {
    return (
      <Box sx={{ textAlign: "center", py: 4 }}>
        <Typography variant="body2" color="text.secondary">
          {t(
            "settings.systemSettings.upgrade.noHistory",
            "No upgrade history available",
          )}
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <TableContainer component={Paper} elevation={0}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>
                {t(
                  "settings.systemSettings.upgrade.historyTable.status",
                  "Status",
                )}
              </TableCell>
              <TableCell>
                {t("settings.systemSettings.upgrade.historyTable.from", "From")}
              </TableCell>
              <TableCell>
                {t("settings.systemSettings.upgrade.historyTable.to", "To")}
              </TableCell>
              <TableCell>
                {t(
                  "settings.systemSettings.upgrade.historyTable.duration",
                  "Duration",
                )}
              </TableCell>
              <TableCell>
                {t(
                  "settings.systemSettings.upgrade.historyTable.triggeredBy",
                  "Triggered By",
                )}
              </TableCell>
              <TableCell>
                {t("settings.systemSettings.upgrade.historyTable.date", "Date")}
              </TableCell>
              <TableCell align="center">
                {t(
                  "settings.systemSettings.upgrade.historyTable.details",
                  "Details",
                )}
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {history.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} sx={{ p: 0, border: 0 }}>
                  <EmptyTableState
                    message="No upgrade history available"
                    icon={<HistoryIcon sx={{ fontSize: 40 }} />}
                  />
                </TableCell>
              </TableRow>
            ) : (
              history.map((record) => (
                <TableRow key={record.upgrade_id} hover>
                  <TableCell>
                    <Chip
                      icon={
                        record.status === "completed" ? (
                          <CheckCircleIcon />
                        ) : (
                          <ErrorIcon />
                        )
                      }
                      label={record.status}
                      color={
                        record.status === "completed" ? "success" : "error"
                      }
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{ fontFamily: "monospace", fontSize: "0.875rem" }}
                    >
                      {record.from_version}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{ fontFamily: "monospace", fontSize: "0.875rem" }}
                    >
                      {record.to_version}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {formatDuration(record.duration)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" noWrap sx={{ maxWidth: 150 }}>
                      {record.triggered_by}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {new Date(record.end_time).toLocaleString()}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    {record.error_message ? (
                      <Tooltip title={record.error_message} arrow>
                        <IconButton size="small" color="error">
                          <InfoIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    ) : (
                      <Tooltip
                        title={`Pipeline: ${record.pipeline_execution_id}`}
                        arrow
                      >
                        <IconButton size="small">
                          <InfoIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {hasNextPage && (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
          <Button
            onClick={handleNextPage}
            disabled={loading}
            endIcon={
              loading ? <CircularProgress size={16} /> : <NavigateNextIcon />
            }
          >
            {t("common.loadMore", "Load More")}
          </Button>
        </Box>
      )}
    </Box>
  );
};

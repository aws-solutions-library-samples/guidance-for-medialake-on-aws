import React, { useState, useMemo } from "react";
import {
  Box,
  Typography,
  Paper,
  Collapse,
  IconButton,
  Chip,
  Tooltip,
  alpha,
  useTheme,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import SourceIcon from "@mui/icons-material/Source";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import MarkdownRenderer from "../common/MarkdownRenderer";
import TabContentContainer from "../common/TabContentContainer";

interface DescriptiveTabProps {
  assetData: any;
}

interface DescriptiveResult {
  result: string;
  prompt_label: string;
  model_id?: string;
  timestamp?: string | number;
  content_source?: string;
  chunk_index?: number;
  chunk_start_time?: number;
  chunk_end_time?: number;
  chunk_duration?: number;
  chunk_logical_start_time?: number;
  chunk_overlap_before?: number;
  chunk_overlap_after?: number;
  pipeline_execution_id?: string;
  run_timestamp?: string | number;
  chunk_status?: string;
  prompt_type?: string;
  prompt_name?: string;
  prompt_preview?: string;
  pipeline_name?: string;
}

export type DescriptiveEntry = { key: string; data: DescriptiveResult };

export function sortDescriptiveEntries(entries: DescriptiveEntry[]): DescriptiveEntry[] {
  const chunkEntries: DescriptiveEntry[] = [];
  const nonChunkEntries: DescriptiveEntry[] = [];

  for (const entry of entries) {
    if (typeof entry.data.chunk_index === "number") {
      chunkEntries.push(entry);
    } else {
      nonChunkEntries.push(entry);
    }
  }

  const groups = new Map<string, DescriptiveEntry[]>();
  for (const entry of chunkEntries) {
    const groupKey = entry.data.pipeline_execution_id ?? "__unknown__";
    const group = groups.get(groupKey);
    if (group) {
      group.push(entry);
    } else {
      groups.set(groupKey, [entry]);
    }
  }

  const sortedGroups = [...groups.values()]
    .sort((a, b) =>
      String(b[0].data.run_timestamp ?? "").localeCompare(String(a[0].data.run_timestamp ?? ""))
    )
    .map((group) => group.sort((a, b) => (a.data.chunk_index ?? 0) - (b.data.chunk_index ?? 0)));

  return [...sortedGroups.flat(), ...nonChunkEntries];
}

/** Format seconds into MM:SS or HH:MM:SS */
function formatTimecode(seconds: number | undefined): string {
  if (seconds === undefined || seconds === null) return "--:--";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}

/** Extract a clean model display name from a full model_id */
function formatModelName(modelId: string | undefined): string {
  if (!modelId) return "";
  // e.g. "us.anthropic.claude-3-5-sonnet-20241022-v2:0" → "Claude 3.5 Sonnet"
  // e.g. "us.amazon.nova-pro-v1:0" → "Nova Pro"
  // e.g. "us.twelvelabs.pegasus-v1:0" → "Pegasus"
  const parts = modelId.split(".");
  const namePart = parts.length > 2 ? parts.slice(2).join(".") : parts[parts.length - 1];
  // Strip version suffixes
  const clean = namePart.replace(/[-_]v\d.*$/, "").replace(/:.*$/, "");
  return clean
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** Format a timestamp to a readable date. Handles ISO strings, epoch seconds (number or numeric string), and date strings. */
function formatTimestamp(ts: string | number | undefined): string {
  if (ts === undefined || ts === null || ts === "") return "";
  try {
    let d: Date;
    const num = typeof ts === "number" ? ts : Number(ts);
    if (!isNaN(num) && num > 1_000_000_000) {
      // Epoch seconds (or millis if > 1e12)
      d = new Date(num > 1e12 ? num : num * 1000);
    } else {
      d = new Date(ts);
    }
    if (isNaN(d.getTime())) return String(ts);
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(ts);
  }
}

/** Derive a clean label for a prompt, stripping chunk suffixes */
function deriveGroupLabel(entry: DescriptiveEntry): string {
  const label = entry.data.prompt_label || entry.key;
  // Strip chunk suffixes like " — Chunk 3 (21:20–31:55)" or " — 2026-02-20... — Chunk 1 ..."
  const chunkPattern = /\s*[—–-]\s*(Chunk\s+\d+.*|[\d]{4}-[\d]{2}-[\d]{2}.*)/i;
  return label.replace(chunkPattern, "").trim() || label;
}

// ─── Metadata pill ───────────────────────────────────────────────────────────

interface MetaPillProps {
  icon: React.ReactNode;
  label: string;
  tooltip?: string;
}

const MetaPill: React.FC<MetaPillProps> = ({ icon, label, tooltip }) => {
  const theme = useTheme();
  const pill = (
    <Box
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 0.5,
        px: 1,
        py: 0.25,
        borderRadius: "6px",
        bgcolor: alpha(theme.palette.text.secondary, 0.06),
        color: "text.secondary",
        fontSize: "0.7rem",
        lineHeight: 1.4,
        whiteSpace: "nowrap",
        "& .MuiSvgIcon-root": { fontSize: "0.8rem" },
      }}
    >
      {icon}
      {label}
    </Box>
  );
  return tooltip ? <Tooltip title={tooltip}>{pill}</Tooltip> : pill;
};

// ─── Single result card (standalone, non-chunk) ──────────────────────────────

interface StandaloneCardProps {
  entry: DescriptiveEntry;
  defaultExpanded?: boolean;
}

const StandaloneCard: React.FC<StandaloneCardProps> = ({ entry, defaultExpanded = true }) => {
  const theme = useTheme();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const { data } = entry;
  const label = data.prompt_label || entry.key;

  return (
    <Paper
      elevation={0}
      sx={{
        border: "1px solid",
        borderColor: alpha(theme.palette.divider, 0.12),
        borderRadius: "10px",
        overflow: "hidden",
        transition: "border-color 0.2s",
        "&:hover": {
          borderColor: alpha(theme.palette.primary.main, 0.3),
        },
      }}
    >
      {/* Header */}
      <Box
        onClick={() => setExpanded(!expanded)}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          px: 2.5,
          py: 1.5,
          cursor: "pointer",
          userSelect: "none",
          bgcolor: alpha(theme.palette.background.paper, 0.6),
          "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.03) },
        }}
      >
        <Box
          sx={{
            width: 3,
            height: 24,
            borderRadius: 1,
            bgcolor: theme.palette.primary.main,
            flexShrink: 0,
          }}
        />
        <Typography
          sx={{
            flex: 1,
            fontWeight: 600,
            fontSize: "0.875rem",
            color: "text.primary",
          }}
        >
          {label}
        </Typography>

        {/* Meta pills */}
        <Box sx={{ display: "flex", gap: 0.75, alignItems: "center", flexShrink: 0 }}>
          {data.model_id && (
            <MetaPill
              icon={<SmartToyIcon />}
              label={formatModelName(data.model_id)}
              tooltip={data.model_id}
            />
          )}
          {data.timestamp && (
            <MetaPill icon={<AccessTimeIcon />} label={formatTimestamp(data.timestamp)} />
          )}
          {data.content_source && (
            <MetaPill
              icon={<SourceIcon />}
              label={data.content_source.charAt(0).toUpperCase() + data.content_source.slice(1)}
            />
          )}
        </Box>

        <IconButton
          size="small"
          sx={{
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.25s ease",
            color: "text.secondary",
          }}
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Content */}
      <Collapse in={expanded}>
        <Box sx={{ px: 2.5, py: 2, borderTop: `1px solid ${alpha(theme.palette.divider, 0.06)}` }}>
          <MarkdownRenderer content={data.result} />
        </Box>
      </Collapse>
    </Paper>
  );
};

// ─── Chunk card (inside a group) ─────────────────────────────────────────────

interface ChunkCardProps {
  entry: DescriptiveEntry;
  isLast: boolean;
  expanded: boolean;
  onToggle: () => void;
}

const ChunkCard: React.FC<ChunkCardProps> = ({ entry, isLast, expanded, onToggle }) => {
  const theme = useTheme();
  const { data } = entry;
  const isFailed = data.chunk_status === "failed";
  const chunkNum = data.chunk_index ?? "?";

  const timeRange =
    data.chunk_start_time !== undefined && data.chunk_end_time !== undefined
      ? `${formatTimecode(data.chunk_start_time)} → ${formatTimecode(data.chunk_end_time)}`
      : null;

  const durationLabel = data.chunk_duration ? formatTimecode(data.chunk_duration) : null;

  return (
    <Box sx={{ position: "relative", pl: 3.5 }}>
      {/* Timeline connector */}
      <Box
        sx={{
          position: "absolute",
          left: 10,
          top: 0,
          bottom: isLast ? "50%" : 0,
          width: 2,
          bgcolor: alpha(theme.palette.primary.main, 0.15),
        }}
      />
      {/* Timeline dot */}
      <Box
        sx={{
          position: "absolute",
          left: 5,
          top: 16,
          width: 12,
          height: 12,
          borderRadius: "50%",
          bgcolor: isFailed
            ? alpha(theme.palette.error.main, 0.15)
            : alpha(theme.palette.primary.main, 0.12),
          border: "2px solid",
          borderColor: isFailed ? theme.palette.error.main : theme.palette.primary.main,
          zIndex: 1,
        }}
      />

      <Paper
        elevation={0}
        sx={{
          mb: isLast ? 0 : 1.5,
          border: "1px solid",
          borderColor: isFailed
            ? alpha(theme.palette.error.main, 0.25)
            : alpha(theme.palette.divider, 0.1),
          borderRadius: "8px",
          overflow: "hidden",
          transition: "border-color 0.2s, box-shadow 0.2s",
          "&:hover": {
            borderColor: isFailed
              ? alpha(theme.palette.error.main, 0.4)
              : alpha(theme.palette.primary.main, 0.25),
            boxShadow: `0 1px 4px ${alpha(theme.palette.common.black, 0.06)}`,
          },
        }}
      >
        {/* Chunk header */}
        <Box
          onClick={onToggle}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            px: 2,
            py: 1.25,
            cursor: "pointer",
            userSelect: "none",
            "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.02) },
          }}
        >
          {/* Chunk number badge */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 26,
              height: 26,
              borderRadius: "6px",
              bgcolor: isFailed
                ? alpha(theme.palette.error.main, 0.1)
                : alpha(theme.palette.primary.main, 0.08),
              color: isFailed ? "error.main" : "primary.main",
              fontSize: "0.75rem",
              fontWeight: 700,
              flexShrink: 0,
            }}
          >
            {chunkNum}
          </Box>

          {/* Time range */}
          {timeRange && (
            <Typography
              sx={{
                fontSize: "0.8rem",
                fontWeight: 500,
                color: "text.primary",
                fontVariantNumeric: "tabular-nums",
                letterSpacing: "0.02em",
              }}
            >
              {timeRange}
            </Typography>
          )}

          {/* Duration chip */}
          {durationLabel && (
            <Chip
              label={durationLabel}
              size="small"
              sx={{
                height: 20,
                fontSize: "0.65rem",
                fontWeight: 500,
                bgcolor: alpha(theme.palette.text.secondary, 0.06),
                color: "text.secondary",
                "& .MuiChip-label": { px: 0.75 },
              }}
            />
          )}

          {/* Status indicator */}
          <Box sx={{ ml: "auto", display: "flex", alignItems: "center", gap: 0.5 }}>
            {isFailed ? (
              <Chip
                icon={<ErrorOutlineIcon sx={{ fontSize: "0.8rem" }} />}
                label="Failed"
                size="small"
                sx={{
                  height: 20,
                  fontSize: "0.65rem",
                  fontWeight: 600,
                  bgcolor: alpha(theme.palette.error.main, 0.1),
                  color: "error.main",
                  "& .MuiChip-label": { px: 0.5 },
                  "& .MuiChip-icon": { ml: 0.5, color: "error.main" },
                }}
              />
            ) : (
              <CheckCircleOutlineIcon
                sx={{ fontSize: "0.9rem", color: alpha(theme.palette.success.main, 0.6) }}
              />
            )}
          </Box>

          <IconButton
            size="small"
            sx={{
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.25s ease",
              color: "text.secondary",
              p: 0.25,
            }}
            aria-label={expanded ? "Collapse chunk" : "Expand chunk"}
          >
            <ExpandMoreIcon sx={{ fontSize: "1rem" }} />
          </IconButton>
        </Box>

        {/* Chunk content */}
        <Collapse in={expanded}>
          <Box
            sx={{
              px: 2,
              py: 1.5,
              borderTop: `1px solid ${alpha(theme.palette.divider, 0.06)}`,
            }}
          >
            {isFailed ? (
              <Typography variant="body2" color="error.main" sx={{ fontStyle: "italic" }}>
                {data.result || "Processing failed for this segment."}
              </Typography>
            ) : (
              <MarkdownRenderer content={data.result} />
            )}
          </Box>
        </Collapse>
      </Paper>
    </Box>
  );
};

// ─── Chunk group (wraps multiple ChunkCards) ─────────────────────────────────

interface ChunkGroupProps {
  entries: DescriptiveEntry[];
  defaultExpanded?: boolean;
}

const ChunkGroup: React.FC<ChunkGroupProps> = ({ entries, defaultExpanded = true }) => {
  const theme = useTheme();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());

  if (entries.length === 0) return null;

  const allChunksExpanded = entries.length > 0 && expandedChunks.size === entries.length;

  const toggleAllChunks = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (allChunksExpanded) {
      setExpandedChunks(new Set());
    } else {
      setExpandedChunks(new Set(entries.map((entry) => entry.key)));
    }
    // Also ensure the group itself is open when expanding all
    if (!expanded && !allChunksExpanded) {
      setExpanded(true);
    }
  };

  const toggleChunk = (key: string) => {
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const first = entries[0].data;
  const groupLabel = deriveGroupLabel(entries[0]);
  const successCount = entries.filter((e) => e.data.chunk_status !== "failed").length;
  const failedCount = entries.length - successCount;

  return (
    <Paper
      elevation={0}
      sx={{
        border: "1px solid",
        borderColor: alpha(theme.palette.divider, 0.12),
        borderRadius: "10px",
        overflow: "hidden",
        transition: "border-color 0.2s",
        "&:hover": {
          borderColor: alpha(theme.palette.primary.main, 0.3),
        },
      }}
    >
      {/* Group header */}
      <Box
        onClick={() => setExpanded(!expanded)}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          px: 2.5,
          py: 1.5,
          cursor: "pointer",
          userSelect: "none",
          bgcolor: alpha(theme.palette.background.paper, 0.6),
          "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.03) },
        }}
      >
        <Box
          sx={{
            width: 3,
            height: 24,
            borderRadius: 1,
            bgcolor: theme.palette.secondary.main,
            flexShrink: 0,
          }}
        />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography
            sx={{
              fontWeight: 600,
              fontSize: "0.875rem",
              color: "text.primary",
            }}
          >
            {groupLabel}
          </Typography>
        </Box>

        {/* Group meta */}
        <Box sx={{ display: "flex", gap: 0.75, alignItems: "center", flexShrink: 0 }}>
          <Chip
            label={`${entries.length} segment${entries.length !== 1 ? "s" : ""}`}
            size="small"
            sx={{
              height: 22,
              fontSize: "0.7rem",
              fontWeight: 600,
              bgcolor: alpha(theme.palette.primary.main, 0.08),
              color: "primary.main",
              "& .MuiChip-label": { px: 1 },
            }}
          />
          {failedCount > 0 && (
            <Chip
              label={`${failedCount} failed`}
              size="small"
              sx={{
                height: 22,
                fontSize: "0.7rem",
                fontWeight: 600,
                bgcolor: alpha(theme.palette.error.main, 0.08),
                color: "error.main",
                "& .MuiChip-label": { px: 1 },
              }}
            />
          )}
          {first.model_id && (
            <MetaPill
              icon={<SmartToyIcon />}
              label={formatModelName(first.model_id)}
              tooltip={first.model_id}
            />
          )}
          {first.run_timestamp && (
            <MetaPill icon={<AccessTimeIcon />} label={formatTimestamp(first.run_timestamp)} />
          )}

          <Tooltip title={allChunksExpanded ? "Collapse all segments" : "Expand all segments"}>
            <IconButton
              size="small"
              onClick={toggleAllChunks}
              sx={{
                color: "text.secondary",
                p: 0.5,
                borderRadius: "6px",
                "&:hover": {
                  bgcolor: alpha(theme.palette.primary.main, 0.08),
                  color: "primary.main",
                },
              }}
              aria-label={allChunksExpanded ? "Collapse all segments" : "Expand all segments"}
            >
              {allChunksExpanded ? (
                <UnfoldLessIcon sx={{ fontSize: "1.1rem" }} />
              ) : (
                <UnfoldMoreIcon sx={{ fontSize: "1.1rem" }} />
              )}
            </IconButton>
          </Tooltip>
        </Box>

        <IconButton
          size="small"
          sx={{
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.25s ease",
            color: "text.secondary",
          }}
          aria-label={expanded ? "Collapse group" : "Expand group"}
        >
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Chunk timeline */}
      <Collapse in={expanded}>
        <Box
          sx={{
            px: 2.5,
            py: 2,
            borderTop: `1px solid ${alpha(theme.palette.divider, 0.06)}`,
          }}
        >
          {entries.map((entry, i) => (
            <ChunkCard
              key={entry.key}
              entry={entry}
              isLast={i === entries.length - 1}
              expanded={expandedChunks.has(entry.key)}
              onToggle={() => toggleChunk(entry.key)}
            />
          ))}
        </Box>
      </Collapse>
    </Paper>
  );
};

// ─── Main component ──────────────────────────────────────────────────────────

const DescriptiveTab: React.FC<DescriptiveTabProps> = ({ assetData }) => {
  const descriptiveData = assetData?.data?.asset?.Metadata?.Descriptive;

  if (!descriptiveData || Object.keys(descriptiveData).length === 0) {
    return (
      <TabContentContainer>
        <Box sx={{ textAlign: "center", py: 4 }}>
          <Typography color="text.secondary" sx={{ fontSize: "0.875rem" }}>
            No descriptive content available for this asset.
          </Typography>
        </Box>
      </TabContentContainer>
    );
  }

  const rawResults: DescriptiveEntry[] = Object.entries(descriptiveData).map(([key, data]) => ({
    key,
    data: data as DescriptiveResult,
  }));

  // Separate chunks from standalone entries, then group chunks by execution
  const { chunkGroups, standaloneEntries } = useMemo(() => {
    const chunks: DescriptiveEntry[] = [];
    const standalone: DescriptiveEntry[] = [];

    for (const entry of rawResults) {
      if (typeof entry.data.chunk_index === "number") {
        chunks.push(entry);
      } else {
        standalone.push(entry);
      }
    }

    // Group chunks by pipeline_execution_id
    const groupMap = new Map<string, DescriptiveEntry[]>();
    for (const entry of chunks) {
      const gk = entry.data.pipeline_execution_id ?? "__unknown__";
      const group = groupMap.get(gk);
      if (group) {
        group.push(entry);
      } else {
        groupMap.set(gk, [entry]);
      }
    }

    // Sort groups by run_timestamp desc, sort within by chunk_index asc
    const sortedGroups = [...groupMap.values()]
      .sort((a, b) =>
        String(b[0].data.run_timestamp ?? "").localeCompare(String(a[0].data.run_timestamp ?? ""))
      )
      .map((group) => group.sort((a, b) => (a.data.chunk_index ?? 0) - (b.data.chunk_index ?? 0)));

    return { chunkGroups: sortedGroups, standaloneEntries: standalone };
  }, [rawResults]);

  return (
    <TabContentContainer noPaper>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {/* Standalone results first */}
        {standaloneEntries.map((entry, i) => (
          <StandaloneCard key={entry.key} entry={entry} defaultExpanded={i === 0} />
        ))}

        {/* Chunk groups */}
        {chunkGroups.map((group, i) => (
          <ChunkGroup
            key={group[0].data.pipeline_execution_id ?? `group-${i}`}
            entries={group}
            defaultExpanded={i === 0}
          />
        ))}
      </Box>
    </TabContentContainer>
  );
};

export default DescriptiveTab;

import React, {
  useState,
  useCallback,
  useMemo,
  useEffect,
  useRef,
} from "react";
import {
  Box,
  CircularProgress,
  Typography,
  Paper,
  Button,
  Chip,
  useTheme,
  alpha,
  TextField,
  InputAdornment,
  IconButton,
  Tooltip,
  Divider,
  Badge,
  Collapse,
  Menu,
  MenuItem,
  ListItemText,
} from "@mui/material";
import { TranscriptionResponse } from "../../api/hooks/useAssets";
import MarkdownRenderer from "../common/MarkdownRenderer";

// MUI Icons
import SubtitlesOutlinedIcon from "@mui/icons-material/SubtitlesOutlined";
import CodeOutlinedIcon from "@mui/icons-material/CodeOutlined";
import SearchIcon from "@mui/icons-material/Search";
import ClearIcon from "@mui/icons-material/Clear";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PersonIcon from "@mui/icons-material/Person";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import LanguageIcon from "@mui/icons-material/Language";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import FileDownloadIcon from "@mui/icons-material/FileDownload";

// Types
interface TranscriptWordAlternative {
  content: string;
  confidence: number;
}

interface TranscriptWord {
  id: number;
  content: string;
  startTime: number;
  endTime: number;
  confidence: number;
  type: "pronunciation" | "punctuation";
  alternatives?: TranscriptWordAlternative[];
}

interface LanguageIdentification {
  code: string;
  score: number;
}

interface TranscriptSegment {
  id: number;
  text: string;
  startTime: number;
  endTime: number;
  words: TranscriptWord[];
  speaker?: string;
}

interface SearchResult {
  word: TranscriptWord;
  segment: TranscriptSegment;
  timestamp: number;
  matchIndex: number;
}

interface MediaPlayerController {
  currentTime?: number;
  seekTo?: (time: number) => void;
  onTimeUpdate?: (callback: (time: number) => void) => void;
}

interface TranscriptionTabProps {
  assetId: string;
  transcriptionData: TranscriptionResponse | undefined;
  isLoading: boolean;
  assetData: any;
  mediaType: "audio" | "video";
  mediaController?: MediaPlayerController;
}

// Custom hooks
const useTranscriptProcessor = (
  transcriptionData: TranscriptionResponse | undefined,
) => {
  return useMemo(() => {
    if (!transcriptionData?.data?.results)
      return { segments: [], speakers: [], languageData: null };

    const items = transcriptionData.data.results.items || [];
    const audioSegments =
      (transcriptionData.data.results as any).audio_segments || [];
    const languageCode = transcriptionData.data.results.language_code;
    const languageIdentification =
      (transcriptionData.data.results as any).language_identification || [];

    // Process language detection data
    const languageData = {
      primaryLanguage: languageCode,
      detectedLanguages: languageIdentification.map((lang: any) => ({
        code: lang.code,
        score: parseFloat(lang.score),
      })),
    };

    // If audio_segments exist, use them for better organization
    if (audioSegments.length > 0) {
      const segments: TranscriptSegment[] = audioSegments.map(
        (segment: any) => {
          const segmentWords = segment.items
            .map((itemId: number) => items[itemId])
            .filter((item: any) => item && item.type === "pronunciation")
            .map((item: any, index: number) => ({
              id: item.id || index,
              content: item.alternatives?.[0]?.content || "",
              startTime: parseFloat(String(item.start_time || "0")),
              endTime: parseFloat(String(item.end_time || "0")),
              confidence: parseFloat(item.alternatives?.[0]?.confidence || "0"),
              type: item.type as "pronunciation" | "punctuation",
              alternatives:
                item.alternatives?.map((alt: any) => ({
                  content: alt.content,
                  confidence: parseFloat(alt.confidence || "0"),
                })) || [],
            }));

          return {
            id: segment.id,
            text: segment.transcript,
            startTime: parseFloat(segment.start_time),
            endTime: parseFloat(segment.end_time),
            words: segmentWords,
            speaker: segment.speaker || `Speaker ${(segment.id % 2) + 1}`,
          };
        },
      );

      const speakers = Array.from(
        new Set(segments.map((s) => s.speaker).filter(Boolean)),
      );
      return { segments, speakers, languageData };
    }

    // Fallback: create segments from individual items
    const pronunciationItems = items.filter(
      (item) => item.type === "pronunciation",
    );
    const wordsPerSegment = 20; // Group words into segments
    const segments: TranscriptSegment[] = [];

    for (let i = 0; i < pronunciationItems.length; i += wordsPerSegment) {
      const segmentItems = pronunciationItems.slice(i, i + wordsPerSegment);
      const words = segmentItems.map((item, index) => ({
        id: item.id || i + index,
        content: item.alternatives?.[0]?.content || "",
        startTime: parseFloat(String(item.start_time || "0")),
        endTime: parseFloat(String(item.end_time || "0")),
        confidence: parseFloat(item.alternatives?.[0]?.confidence || "0"),
        type: item.type as "pronunciation" | "punctuation",
        alternatives:
          item.alternatives?.map((alt: any) => ({
            content: alt.content,
            confidence: parseFloat(alt.confidence || "0"),
          })) || [],
      }));

      if (words.length > 0) {
        segments.push({
          id: Math.floor(i / wordsPerSegment),
          text: words.map((w) => w.content).join(" "),
          startTime: words[0].startTime,
          endTime: words[words.length - 1].endTime,
          words,
          speaker: `Speaker ${(Math.floor(i / wordsPerSegment) % 2) + 1}`,
        });
      }
    }

    const speakers = Array.from(
      new Set(segments.map((s) => s.speaker).filter(Boolean)),
    );
    return { segments, speakers, languageData };
  }, [transcriptionData]);
};

const useTranscriptSearch = (segments: TranscriptSegment[]) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);

  const search = useCallback(
    (query: string) => {
      if (!query.trim()) {
        setSearchResults([]);
        return;
      }

      const results: SearchResult[] = [];
      const regex = new RegExp(
        query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
        "gi",
      );

      segments.forEach((segment) => {
        segment.words.forEach((word) => {
          if (regex.test(word.content)) {
            results.push({
              word,
              segment,
              timestamp: word.startTime,
              matchIndex: results.length,
            });
          }
        });
      });

      setSearchResults(results);
    },
    [segments],
  );

  useEffect(() => {
    search(searchQuery);
  }, [searchQuery, search]);

  return { searchQuery, setSearchQuery, searchResults, search };
};

const useCurrentWordHighlight = (
  currentTime: number,
  segments: TranscriptSegment[],
) => {
  return useMemo(() => {
    if (!currentTime) return null;

    let closestWord = null;
    let closestDistance = Infinity;

    for (const segment of segments) {
      for (const word of segment.words) {
        // Check if current time is within the word's time range
        if (currentTime >= word.startTime && currentTime <= word.endTime) {
          return { segmentId: segment.id, wordId: word.id };
        }

        // If not exact match, find the closest word for better UX
        // This helps when seeking to a word's start time
        const distanceToStart = Math.abs(currentTime - word.startTime);
        const distanceToMid = Math.abs(
          currentTime - (word.startTime + word.endTime) / 2,
        );
        const minDistance = Math.min(distanceToStart, distanceToMid);

        if (minDistance < closestDistance && minDistance < 0.1) {
          // Within 100ms tolerance
          closestDistance = minDistance;
          closestWord = { segmentId: segment.id, wordId: word.id };
        }
      }
    }

    return closestWord;
  }, [currentTime, segments]);
};

// Components
const LanguageDetectionInfo: React.FC<{
  languageData: {
    primaryLanguage: string;
    detectedLanguages: LanguageIdentification[];
  } | null;
}> = ({ languageData }) => {
  const theme = useTheme();

  if (!languageData || !languageData.detectedLanguages.length) return null;

  const primaryLang = languageData.detectedLanguages[0];
  const hasMultipleLanguages = languageData.detectedLanguages.length > 1;

  return (
    <Paper
      elevation={0}
      sx={{
        mb: 2,
        p: 1.5,
        backgroundColor: alpha(theme.palette.background.paper, 0.5),
        borderRadius: 1,
        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <LanguageIcon
          sx={{ fontSize: 16, color: theme.palette.text.secondary }}
        />
        <Typography variant="caption" sx={{ fontWeight: 600 }}>
          Language Detection:
        </Typography>
        <Chip
          label={`${primaryLang.code} (${Math.round(primaryLang.score * 100)}%)`}
          size="small"
          sx={{
            backgroundColor: alpha(theme.palette.primary.main, 0.1),
            color: theme.palette.primary.main,
            fontSize: "0.7rem",
          }}
        />
        {hasMultipleLanguages && (
          <Tooltip
            title={
              <Box>
                <Typography
                  variant="caption"
                  sx={{ fontWeight: 600, display: "block" }}
                >
                  Other detected languages:
                </Typography>
                {languageData.detectedLanguages
                  .slice(1, 4)
                  .map((lang, index) => (
                    <Typography
                      key={index}
                      variant="caption"
                      sx={{ display: "block" }}
                    >
                      {lang.code}: {Math.round(lang.score * 100)}%
                    </Typography>
                  ))}
              </Box>
            }
          >
            <Chip
              label={`+${languageData.detectedLanguages.length - 1} more`}
              size="small"
              sx={{
                backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                color: theme.palette.secondary.main,
                fontSize: "0.7rem",
              }}
            />
          </Tooltip>
        )}
      </Box>
    </Paper>
  );
};

const TranscriptWord: React.FC<{
  word: TranscriptWord;
  isHighlighted: boolean;
  isSearchMatch: boolean;
  onSeek: (time: number) => void;
}> = ({ word, isHighlighted, isSearchMatch, onSeek }) => {
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [isHovered, setIsHovered] = useState(false);

  // Determine confidence level
  const isLowConfidence = word.confidence < 0.8;
  const isVeryLowConfidence = word.confidence < 0.6;
  const hasAlternatives = word.alternatives && word.alternatives.length > 1;

  const handleAlternativesClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation(); // Prevent word seeking
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleAlternativeSelect = (alternative: TranscriptWordAlternative) => {
    // In a real implementation, this would update the transcript
    // For now, we'll just close the menu
    handleClose();
    onSeek(word.startTime + 0.01);
  };

  return (
    <>
      <span
        onClick={() => onSeek(word.startTime + 0.01)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{
          cursor: "pointer",
          padding: "2px 4px",
          borderRadius: "4px",
          margin: "0 1px",
          backgroundColor: isHighlighted
            ? alpha(theme.palette.primary.main, 0.3)
            : isSearchMatch
              ? alpha(theme.palette.warning.main, 0.2)
              : isVeryLowConfidence
                ? alpha(theme.palette.error.main, 0.1)
                : isLowConfidence
                  ? alpha(theme.palette.warning.main, 0.1)
                  : "transparent",
          color: isHighlighted
            ? theme.palette.primary.contrastText
            : isVeryLowConfidence
              ? theme.palette.error.main
              : isLowConfidence
                ? theme.palette.warning.main
                : "inherit",
          fontWeight: isHighlighted ? 600 : "normal",
          fontStyle: isLowConfidence ? "italic" : "normal",
          textDecoration: isVeryLowConfidence ? "underline dotted" : "none",
          transition: "all 0.2s ease-in-out",
          display: "inline-block",
          position: "relative",
        }}
        title={`${word.startTime.toFixed(1)}s - ${word.endTime.toFixed(1)}s (${Math.round(
          word.confidence * 100,
        )}% confidence)${isLowConfidence ? " - Low confidence" : ""}${
          hasAlternatives ? " - Click icon for alternatives" : ""
        }`}
      >
        {word.content}
        {hasAlternatives && (
          <IconButton
            size="small"
            onClick={handleAlternativesClick}
            sx={{
              ml: 0.3,
              p: 0.2,
              minWidth: "auto",
              width: 16,
              height: 16,
              opacity: isHovered ? 1 : 0.4,
              transition: "opacity 0.2s ease-in-out",
              "&:hover": {
                backgroundColor: alpha(theme.palette.primary.main, 0.1),
              },
            }}
            title="View alternative transcriptions"
          >
            <MoreVertIcon sx={{ fontSize: 12 }} />
          </IconButton>
        )}
      </span>

      {hasAlternatives && (
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleClose}
          PaperProps={{
            sx: { minWidth: 200 },
          }}
        >
          <MenuItem disabled>
            <ListItemText
              primary="Alternative transcriptions:"
              primaryTypographyProps={{ variant: "caption", fontWeight: 600 }}
            />
          </MenuItem>
          <Divider />
          {word.alternatives?.map((alternative, index) => (
            <MenuItem
              key={index}
              onClick={() => handleAlternativeSelect(alternative)}
              selected={alternative.content === word.content}
            >
              <ListItemText
                primary={alternative.content}
                secondary={`${Math.round(alternative.confidence * 100)}% confidence`}
              />
            </MenuItem>
          ))}
        </Menu>
      )}
    </>
  );
};

const TranscriptSegment: React.FC<{
  segment: TranscriptSegment;
  currentHighlight: { segmentId: number; wordId: number } | null;
  searchResults: SearchResult[];
  onSeek: (time: number) => void;
}> = ({ segment, currentHighlight, searchResults, onSeek }) => {
  const theme = useTheme();
  const searchWordIds = new Set(
    searchResults
      .filter((result) => result.segment.id === segment.id)
      .map((result) => result.word.id),
  );

  return (
    <Paper
      elevation={0}
      sx={{
        mb: 2,
        p: 2,
        backgroundColor: alpha(theme.palette.background.paper, 0.7),
        borderRadius: 1,
        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
        "&:hover": {
          backgroundColor: alpha(theme.palette.background.paper, 0.9),
        },
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
        <Chip
          icon={<PersonIcon />}
          label={segment.speaker}
          size="small"
          sx={{
            mr: 2,
            backgroundColor: alpha(theme.palette.secondary.main, 0.1),
            color: theme.palette.secondary.main,
          }}
        />
        <Typography variant="caption" color="text.secondary">
          {segment.startTime.toFixed(1)}s - {segment.endTime.toFixed(1)}s
        </Typography>
        <IconButton
          size="small"
          onClick={() => onSeek(segment.startTime + 0.01)}
          sx={{ ml: 1 }}
        >
          <PlayArrowIcon fontSize="small" />
        </IconButton>
      </Box>

      <Typography variant="body1" sx={{ lineHeight: 1.8 }}>
        {segment.words.map((word) => (
          <TranscriptWord
            key={word.id}
            word={word}
            isHighlighted={
              currentHighlight?.segmentId === segment.id &&
              currentHighlight?.wordId === word.id
            }
            isSearchMatch={searchWordIds.has(word.id)}
            onSeek={onSeek}
          />
        ))}
      </Typography>
    </Paper>
  );
};

const SearchBar: React.FC<{
  searchQuery: string;
  onSearchChange: (query: string) => void;
  searchResults: SearchResult[];
  onJumpToResult: (result: SearchResult) => void;
}> = ({ searchQuery, onSearchChange, searchResults, onJumpToResult }) => {
  const [showResults, setShowResults] = useState(false);

  return (
    <Box sx={{ mb: 3 }}>
      <TextField
        fullWidth
        variant="outlined"
        placeholder="Search transcript..."
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon />
            </InputAdornment>
          ),
          endAdornment: searchQuery && (
            <InputAdornment position="end">
              <Badge badgeContent={searchResults.length} color="primary">
                <IconButton
                  size="small"
                  onClick={() => setShowResults(!showResults)}
                >
                  {showResults ? (
                    <KeyboardArrowUpIcon />
                  ) : (
                    <KeyboardArrowDownIcon />
                  )}
                </IconButton>
              </Badge>
              <IconButton size="small" onClick={() => onSearchChange("")}>
                <ClearIcon />
              </IconButton>
            </InputAdornment>
          ),
        }}
      />

      <Collapse in={showResults && searchResults.length > 0}>
        <Paper sx={{ mt: 1, maxHeight: 200, overflow: "auto" }}>
          {searchResults.map((result, index) => (
            <Box
              key={index}
              sx={{
                p: 1,
                borderBottom:
                  index < searchResults.length - 1 ? "1px solid" : "none",
                borderColor: "divider",
                cursor: "pointer",
                "&:hover": { backgroundColor: "action.hover" },
              }}
              onClick={() => onJumpToResult(result)}
            >
              <Typography variant="body2">
                <strong>{result.word.content}</strong> -{" "}
                {result.segment.speaker} at {result.timestamp.toFixed(1)}s
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {result.segment.text.substring(0, 100)}...
              </Typography>
            </Box>
          ))}
        </Paper>
      </Collapse>
    </Box>
  );
};

const TranscriptionTab: React.FC<TranscriptionTabProps> = ({
  assetId,
  transcriptionData,
  isLoading,
  assetData,
  mediaType,
  mediaController,
}) => {
  const theme = useTheme();
  const [currentTime, setCurrentTime] = useState(0);
  const [accordionExpanded, setAccordionExpanded] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);

  // Process transcript data
  const { segments, speakers, languageData } =
    useTranscriptProcessor(transcriptionData);

  // Search functionality
  const { searchQuery, setSearchQuery, searchResults } =
    useTranscriptSearch(segments);

  // Current word highlighting
  const currentHighlight = useCurrentWordHighlight(currentTime, segments);

  // Media controller integration
  useEffect(() => {
    if (mediaController?.onTimeUpdate) {
      const unsubscribe = mediaController.onTimeUpdate(setCurrentTime);
      return unsubscribe;
    }
  }, [mediaController]);

  // Seek functionality
  const handleSeek = useCallback(
    (time: number) => {
      if (mediaController?.seekTo) {
        mediaController.seekTo(time);
      }
    },
    [mediaController],
  );

  // Jump to search result
  const handleJumpToResult = useCallback(
    (result: SearchResult) => {
      handleSeek(result.timestamp);

      // Scroll to the segment
      const segmentElement = document.getElementById(
        `segment-${result.segment.id}`,
      );
      if (segmentElement) {
        segmentElement.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    },
    [handleSeek],
  );

  // Handle loading state
  if (isLoading) {
    return (
      <Box
        sx={{
          p: 2,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "300px",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Handle missing or invalid data
  if (
    !transcriptionData ||
    !transcriptionData.data ||
    !transcriptionData.data.results
  ) {
    return (
      <Box sx={{ p: 2, textAlign: "center" }}>
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
          {mediaType === "audio" ? "Audio" : "Video"} Transcription
        </Typography>
        <Paper
          elevation={0}
          sx={{
            mb: 3,
            p: 4,
            backgroundColor: alpha(theme.palette.background.paper, 0.7),
            borderRadius: 1,
            border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          }}
        >
          <Typography variant="body1" color="text.secondary">
            No transcription data available for this {mediaType} file.
          </Typography>
        </Paper>
      </Box>
    );
  }

  // Check if transcripts array exists and has items
  const hasTranscripts =
    transcriptionData.data.results.transcripts &&
    transcriptionData.data.results.transcripts.length > 0;

  // Export transcript functionality
  const handleExportTranscript = useCallback(() => {
    if (!transcriptionData?.data?.results) return;

    let exportText = "";

    if (segments.length > 0) {
      // Export with timestamps and speakers
      exportText = segments
        .map((segment) => {
          const timeStamp = `[${segment.startTime.toFixed(1)}s - ${segment.endTime.toFixed(1)}s]`;
          const speaker = segment.speaker ? `${segment.speaker}: ` : "";
          return `${timeStamp} ${speaker}${segment.text}`;
        })
        .join("\n\n");
    } else if (hasTranscripts) {
      // Fallback to simple transcript
      exportText = transcriptionData.data.results.transcripts[0].transcript;
    }

    if (exportText) {
      // Create and download file
      const blob = new Blob([exportText], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `transcript-${assetId}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  }, [transcriptionData, segments, hasTranscripts, assetId]);

  // Extract summary from asset data
  const summary = assetData?.data?.asset?.Summary100Result;

  return (
    <Box sx={{ p: 2 }} ref={transcriptRef}>
      {/* Collapsible Header */}
      {/* Custom Collapsible Header */}
      <Paper
        elevation={0}
        sx={{
          mb: 2,
          border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
        }}
      >
        <Box
          sx={{
            backgroundColor: alpha(theme.palette.background.paper, 0.7),
            "&:hover": {
              backgroundColor: alpha(theme.palette.background.paper, 0.9),
            },
            display: "flex",
            alignItems: "center",
            padding: "8px 16px",
            minHeight: "48px",
          }}
        >
          {/* Custom Header Content */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              width: "100%",
            }}
          >
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              {mediaType === "audio" ? "Audio" : "Video"} Transcription
            </Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              {/* Quick Search */}
              {segments.length > 0 && (
                <TextField
                  size="small"
                  placeholder="Quick search..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon sx={{ fontSize: 16 }} />
                      </InputAdornment>
                    ),
                    sx: { fontSize: "0.875rem" },
                  }}
                  sx={{ width: 200 }}
                />
              )}

              {/* Language Detection Chip */}
              {languageData && languageData.detectedLanguages.length > 0 && (
                <Chip
                  icon={<LanguageIcon />}
                  label={`${languageData.detectedLanguages[0].code} (${Math.round(
                    languageData.detectedLanguages[0].score * 100,
                  )}%)`}
                  size="small"
                  sx={{
                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                    color: theme.palette.primary.main,
                    fontSize: "0.7rem",
                  }}
                />
              )}

              {/* Export Button */}
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  handleExportTranscript();
                }}
                title="Export transcript"
                sx={{
                  backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                  "&:hover": {
                    backgroundColor: alpha(theme.palette.secondary.main, 0.2),
                  },
                }}
              >
                <FileDownloadIcon sx={{ fontSize: 16 }} />
              </IconButton>

              {/* Custom Expand Button */}
              <IconButton
                size="small"
                onClick={() => setAccordionExpanded(!accordionExpanded)}
                title={
                  accordionExpanded ? "Collapse details" : "Expand details"
                }
                sx={{
                  "&:hover": {
                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                  },
                }}
              >
                <ExpandMoreIcon
                  sx={{
                    transform: accordionExpanded
                      ? "rotate(180deg)"
                      : "rotate(0deg)",
                    transition: "transform 0.2s ease-in-out",
                  }}
                />
              </IconButton>
            </Box>
          </Box>
        </Box>

        {/* Collapsible Details */}
        <Collapse in={accordionExpanded}>
          <Box sx={{ p: 2, pt: 0 }}>
            {/* Summary Section */}
            {summary && (
              <Paper
                elevation={0}
                sx={{
                  mb: 2,
                  p: 2,
                  backgroundColor: alpha(theme.palette.background.paper, 0.5),
                  borderRadius: 1,
                  border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                }}
              >
                <Typography
                  variant="body2"
                  sx={{
                    mb: 2,
                    fontStyle: "italic",
                    color: theme.palette.text.secondary,
                  }}
                >
                  Summary:
                </Typography>
                <MarkdownRenderer content={summary} />
              </Paper>
            )}

            {/* Advanced Search */}
            {segments.length > 0 && searchResults.length > 0 && (
              <Paper
                elevation={0}
                sx={{
                  mb: 2,
                  p: 1.5,
                  backgroundColor: alpha(theme.palette.background.paper, 0.5),
                  borderRadius: 1,
                  border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{ mb: 1, display: "block", fontWeight: 600 }}
                >
                  Search Results ({searchResults.length}):
                </Typography>
                <Box sx={{ maxHeight: 250, overflowY: "auto" }}>
                  {searchResults.map((result, index) => (
                    <Box
                      key={index}
                      onClick={() => handleJumpToResult(result)}
                      sx={{
                        p: 1,
                        cursor: "pointer",
                        borderRadius: 1,
                        "&:hover": {
                          backgroundColor: alpha(
                            theme.palette.primary.main,
                            0.1,
                          ),
                        },
                      }}
                    >
                      <Typography variant="caption" color="text.secondary">
                        {result.segment.speaker} • {result.timestamp.toFixed(1)}
                        s
                      </Typography>
                      <Typography variant="body2" sx={{ fontSize: "0.8rem" }}>
                        ...{result.word.content}...
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Paper>
            )}

            {/* Language Detection Details */}
            {languageData && languageData.detectedLanguages.length > 1 && (
              <Paper
                elevation={0}
                sx={{
                  mb: 2,
                  p: 1.5,
                  backgroundColor: alpha(theme.palette.background.paper, 0.5),
                  borderRadius: 1,
                  border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{ mb: 1, display: "block", fontWeight: 600 }}
                >
                  Language Detection Details:
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                  {languageData.detectedLanguages
                    .filter((lang) => lang.score >= 0.7) // Only show languages with 70%+ confidence
                    .slice(0, 5)
                    .map((lang, index) => (
                      <Chip
                        key={index}
                        label={`${lang.code}: ${Math.round(lang.score * 100)}%`}
                        size="small"
                        variant={index === 0 ? "filled" : "outlined"}
                        sx={{ fontSize: "0.7rem" }}
                      />
                    ))}
                </Box>
              </Paper>
            )}

            {/* Confidence Legend */}
            {segments.length > 0 && (
              <Paper
                elevation={0}
                sx={{
                  mb: 2,
                  p: 1.5,
                  backgroundColor: alpha(theme.palette.background.paper, 0.5),
                  borderRadius: 1,
                  border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{ mb: 1, display: "block", fontWeight: 600 }}
                >
                  Confidence Indicators:
                </Typography>
                <Box
                  sx={{
                    display: "flex",
                    gap: 2,
                    flexWrap: "wrap",
                    alignItems: "center",
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                    <span
                      style={{
                        padding: "2px 6px",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        backgroundColor: "transparent",
                      }}
                    >
                      Normal
                    </span>
                    <Typography variant="caption" color="text.secondary">
                      ≥80% confidence
                    </Typography>
                  </Box>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                    <span
                      style={{
                        padding: "2px 6px",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        fontStyle: "italic",
                        backgroundColor: alpha(theme.palette.warning.main, 0.1),
                        color: theme.palette.warning.main,
                      }}
                    >
                      Low
                    </span>
                    <Typography variant="caption" color="text.secondary">
                      60-79% confidence
                    </Typography>
                  </Box>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                    <span
                      style={{
                        padding: "2px 6px",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        fontStyle: "italic",
                        textDecoration: "underline dotted",
                        backgroundColor: alpha(theme.palette.error.main, 0.1),
                        color: theme.palette.error.main,
                      }}
                    >
                      Very Low
                    </span>
                    <Typography variant="caption" color="text.secondary">
                      &lt;60% confidence
                    </Typography>
                  </Box>
                  {/* <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                        <span style={{
                                            padding: '2px 6px',
                                            borderRadius: '4px',
                                            fontSize: '0.75rem',
                                            backgroundColor: 'transparent'
                                        }}>
                                            Word
                                        </span>
                                        <IconButton
                                            size="small"
                                            sx={{
                                                ml: 0.3,
                                                p: 0.2,
                                                minWidth: 'auto',
                                                width: 16,
                                                height: 16,
                                                opacity: 0.6
                                            }}
                                            disabled
                                        >
                                            <MoreVertIcon sx={{ fontSize: 12 }} />
                                        </IconButton>
                                    </Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Click icon for alternatives
                                    </Typography>
                                </Box> */}
                </Box>
              </Paper>
            )}

            {/* Speakers Info */}
            {speakers.length > 0 && (
              <Paper
                elevation={0}
                sx={{
                  mb: 0,
                  p: 1.5,
                  backgroundColor: alpha(theme.palette.background.paper, 0.5),
                  borderRadius: 1,
                  border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{ mb: 1, display: "block", fontWeight: 600 }}
                >
                  Speakers:
                </Typography>
                <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                  {speakers.map((speaker) => (
                    <Chip
                      key={speaker}
                      icon={<PersonIcon />}
                      label={speaker}
                      size="small"
                      variant="outlined"
                      sx={{ fontSize: "0.7rem" }}
                    />
                  ))}
                </Box>
              </Paper>
            )}
          </Box>
        </Collapse>
      </Paper>

      {/*  Transcript */}
      {segments.length > 0 ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>
            Transcript
            {currentTime > 0 && (
              <Chip
                label={`${currentTime.toFixed(1)}s`}
                size="small"
                sx={{ ml: 2 }}
                color="primary"
              />
            )}
          </Typography>

          {segments.map((segment) => (
            <div key={segment.id} id={`segment-${segment.id}`}>
              <TranscriptSegment
                segment={segment}
                currentHighlight={currentHighlight}
                searchResults={searchResults}
                onSeek={handleSeek}
              />
            </div>
          ))}
        </Box>
      ) : (
        /* Fallback to original display */
        <Paper
          elevation={0}
          sx={{
            mb: 3,
            p: 2,
            backgroundColor: alpha(theme.palette.background.paper, 0.7),
            borderRadius: 1,
            border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          }}
        >
          <Typography
            variant="body2"
            sx={{
              mb: 2,
              fontStyle: "italic",
              color: theme.palette.text.secondary,
            }}
          >
            Full Transcript:
          </Typography>
          <Typography variant="body1" paragraph>
            {hasTranscripts
              ? transcriptionData.data.results.transcripts[0].transcript
              : "Full transcript not available"}
          </Typography>
        </Paper>
      )}
    </Box>
  );
};

export default TranscriptionTab;

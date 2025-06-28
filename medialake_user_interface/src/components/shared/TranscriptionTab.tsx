import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
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
    Collapse
} from '@mui/material';
import { TranscriptionResponse } from '../../api/hooks/useAssets';
import MarkdownRenderer from '../common/MarkdownRenderer';

// MUI Icons
import SubtitlesOutlinedIcon from '@mui/icons-material/SubtitlesOutlined';
import CodeOutlinedIcon from '@mui/icons-material/CodeOutlined';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PersonIcon from '@mui/icons-material/Person';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';

// Types
interface TranscriptWord {
    id: number;
    content: string;
    startTime: number;
    endTime: number;
    confidence: number;
    type: 'pronunciation' | 'punctuation';
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
    mediaType: 'audio' | 'video';
    mediaController?: MediaPlayerController;
}

// Custom hooks
const useTranscriptProcessor = (transcriptionData: TranscriptionResponse | undefined) => {
    return useMemo(() => {
        if (!transcriptionData?.data?.results) return { segments: [], speakers: [] };

        const items = transcriptionData.data.results.items || [];
        const audioSegments = (transcriptionData.data.results as any).audio_segments || [];

        // If audio_segments exist, use them for better organization
        if (audioSegments.length > 0) {
            const segments: TranscriptSegment[] = audioSegments.map((segment: any) => {
                const segmentWords = segment.items
                    .map((itemId: number) => items[itemId])
                    .filter((item: any) => item && item.type === 'pronunciation')
                    .map((item: any, index: number) => ({
                        id: item.id || index,
                        content: item.alternatives?.[0]?.content || '',
                        startTime: parseFloat(String(item.start_time || '0')),
                        endTime: parseFloat(String(item.end_time || '0')),
                        confidence: parseFloat(item.alternatives?.[0]?.confidence || '0'),
                        type: item.type as 'pronunciation' | 'punctuation'
                    }));

                return {
                    id: segment.id,
                    text: segment.transcript,
                    startTime: parseFloat(segment.start_time),
                    endTime: parseFloat(segment.end_time),
                    words: segmentWords,
                    speaker: segment.speaker || `Speaker ${(segment.id % 2) + 1}`
                };
            });

            const speakers = Array.from(new Set(segments.map(s => s.speaker).filter(Boolean)));
            return { segments, speakers };
        }

        // Fallback: create segments from individual items
        const pronunciationItems = items.filter(item => item.type === 'pronunciation');
        const wordsPerSegment = 20; // Group words into segments
        const segments: TranscriptSegment[] = [];

        for (let i = 0; i < pronunciationItems.length; i += wordsPerSegment) {
            const segmentItems = pronunciationItems.slice(i, i + wordsPerSegment);
            const words = segmentItems.map((item, index) => ({
                id: item.id || i + index,
                content: item.alternatives?.[0]?.content || '',
                startTime: parseFloat(String(item.start_time || '0')),
                endTime: parseFloat(String(item.end_time || '0')),
                confidence: parseFloat(item.alternatives?.[0]?.confidence || '0'),
                type: item.type as 'pronunciation' | 'punctuation'
            }));

            if (words.length > 0) {
                segments.push({
                    id: Math.floor(i / wordsPerSegment),
                    text: words.map(w => w.content).join(' '),
                    startTime: words[0].startTime,
                    endTime: words[words.length - 1].endTime,
                    words,
                    speaker: `Speaker ${(Math.floor(i / wordsPerSegment) % 2) + 1}`
                });
            }
        }

        const speakers = Array.from(new Set(segments.map(s => s.speaker).filter(Boolean)));
        return { segments, speakers };
    }, [transcriptionData]);
};

const useTranscriptSearch = (segments: TranscriptSegment[]) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);

    const search = useCallback((query: string) => {
        if (!query.trim()) {
            setSearchResults([]);
            return;
        }

        const results: SearchResult[] = [];
        const regex = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');

        segments.forEach(segment => {
            segment.words.forEach(word => {
                if (regex.test(word.content)) {
                    results.push({
                        word,
                        segment,
                        timestamp: word.startTime,
                        matchIndex: results.length
                    });
                }
            });
        });

        setSearchResults(results);
    }, [segments]);

    useEffect(() => {
        search(searchQuery);
    }, [searchQuery, search]);

    return { searchQuery, setSearchQuery, searchResults, search };
};

const useCurrentWordHighlight = (currentTime: number, segments: TranscriptSegment[]) => {
    return useMemo(() => {
        if (!currentTime) return null;

        for (const segment of segments) {
            for (const word of segment.words) {
                if (currentTime >= word.startTime && currentTime <= word.endTime) {
                    return { segmentId: segment.id, wordId: word.id };
                }
            }
        }
        return null;
    }, [currentTime, segments]);
};

// Components
const TranscriptWord: React.FC<{
    word: TranscriptWord;
    isHighlighted: boolean;
    isSearchMatch: boolean;
    onSeek: (time: number) => void;
}> = ({ word, isHighlighted, isSearchMatch, onSeek }) => {
    const theme = useTheme();

    return (
        <span
            onClick={() => onSeek(word.startTime)}
            style={{
                cursor: 'pointer',
                padding: '2px 4px',
                borderRadius: '4px',
                margin: '0 1px',
                backgroundColor: isHighlighted 
                    ? alpha(theme.palette.primary.main, 0.3)
                    : isSearchMatch 
                    ? alpha(theme.palette.warning.main, 0.2)
                    : 'transparent',
                color: isHighlighted ? theme.palette.primary.contrastText : 'inherit',
                fontWeight: isHighlighted ? 600 : 'normal',
                transition: 'all 0.2s ease-in-out',
                display: 'inline-block'
            }}
            title={`${word.startTime.toFixed(1)}s - ${word.endTime.toFixed(1)}s (${Math.round(word.confidence * 100)}%)`}
        >
            {word.content}
        </span>
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
            .filter(result => result.segment.id === segment.id)
            .map(result => result.word.id)
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
                '&:hover': {
                    backgroundColor: alpha(theme.palette.background.paper, 0.9)
                }
            }}
        >
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Chip
                    icon={<PersonIcon />}
                    label={segment.speaker}
                    size="small"
                    sx={{
                        mr: 2,
                        backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                        color: theme.palette.secondary.main
                    }}
                />
                <Typography variant="caption" color="text.secondary">
                    {segment.startTime.toFixed(1)}s - {segment.endTime.toFixed(1)}s
                </Typography>
                <IconButton
                    size="small"
                    onClick={() => onSeek(segment.startTime)}
                    sx={{ ml: 1 }}
                >
                    <PlayArrowIcon fontSize="small" />
                </IconButton>
            </Box>
            
            <Typography variant="body1" sx={{ lineHeight: 1.8 }}>
                {segment.words.map(word => (
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
                                    {showResults ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
                                </IconButton>
                            </Badge>
                            <IconButton
                                size="small"
                                onClick={() => onSearchChange('')}
                            >
                                <ClearIcon />
                            </IconButton>
                        </InputAdornment>
                    )
                }}
            />
            
            <Collapse in={showResults && searchResults.length > 0}>
                <Paper sx={{ mt: 1, maxHeight: 200, overflow: 'auto' }}>
                    {searchResults.map((result, index) => (
                        <Box
                            key={index}
                            sx={{
                                p: 1,
                                borderBottom: index < searchResults.length - 1 ? '1px solid' : 'none',
                                borderColor: 'divider',
                                cursor: 'pointer',
                                '&:hover': { backgroundColor: 'action.hover' }
                            }}
                            onClick={() => onJumpToResult(result)}
                        >
                            <Typography variant="body2">
                                <strong>{result.word.content}</strong> - {result.segment.speaker} at {result.timestamp.toFixed(1)}s
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
    mediaController 
}) => {
    const theme = useTheme();
    const [currentTime, setCurrentTime] = useState(0);
    const transcriptRef = useRef<HTMLDivElement>(null);
    
    // Process transcript data
    const { segments, speakers } = useTranscriptProcessor(transcriptionData);
    
    // Search functionality
    const { searchQuery, setSearchQuery, searchResults } = useTranscriptSearch(segments);
    
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
    const handleSeek = useCallback((time: number) => {
        if (mediaController?.seekTo) {
            mediaController.seekTo(time);
        }
    }, [mediaController]);
    
    // Jump to search result
    const handleJumpToResult = useCallback((result: SearchResult) => {
        handleSeek(result.timestamp);
        
        // Scroll to the segment
        const segmentElement = document.getElementById(`segment-${result.segment.id}`);
        if (segmentElement) {
            segmentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }, [handleSeek]);
    
    
    // Handle loading state
    if (isLoading) {
        return (
            <Box sx={{ p: 2, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
                <CircularProgress />
            </Box>
        );
    }
    
    // Handle missing or invalid data
    if (!transcriptionData || !transcriptionData.data || !transcriptionData.data.results) {
        return (
            <Box sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
                    {mediaType === 'audio' ? 'Audio' : 'Video'} Transcription
                </Typography>
                <Paper elevation={0} sx={{
                    mb: 3,
                    p: 4,
                    backgroundColor: alpha(theme.palette.background.paper, 0.7),
                    borderRadius: 1,
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`
                }}>
                    <Typography variant="body1" color="text.secondary">
                        No transcription data available for this {mediaType} file.
                    </Typography>
                </Paper>
            </Box>
        );
    }
    
    // Check if transcripts array exists and has items
    const hasTranscripts = transcriptionData.data.results.transcripts &&
                          transcriptionData.data.results.transcripts.length > 0;
    
    // Export transcript functionality
    const handleExportTranscript = useCallback(() => {
        if (!transcriptionData?.data?.results) return;
        
        let exportText = '';
        
        if (segments.length > 0) {
            // Export with timestamps and speakers
            exportText = segments.map(segment => {
                const timeStamp = `[${segment.startTime.toFixed(1)}s - ${segment.endTime.toFixed(1)}s]`;
                const speaker = segment.speaker ? `${segment.speaker}: ` : '';
                return `${timeStamp} ${speaker}${segment.text}`;
            }).join('\n\n');
        } else if (hasTranscripts) {
            // Fallback to simple transcript
            exportText = transcriptionData.data.results.transcripts[0].transcript;
        }
        
        if (exportText) {
            // Create and download file
            const blob = new Blob([exportText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
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
            <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
                {mediaType === 'audio' ? 'Audio' : 'Video'} Transcription
            </Typography>
            
            {/* Summary Section */}
            {summary && (
                <Paper elevation={0} sx={{
                    mb: 3,
                    p: 2,
                    backgroundColor: alpha(theme.palette.background.paper, 0.7),
                    borderRadius: 1,
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`
                }}>
                    <Typography variant="body2" sx={{ mb: 2, fontStyle: 'italic', color: theme.palette.text.secondary }}>
                        Summary:
                    </Typography>
                    <MarkdownRenderer content={summary} />
                </Paper>
            )}
            
            {/* Search Bar */}
            {segments.length > 0 && (
                <SearchBar
                    searchQuery={searchQuery}
                    onSearchChange={setSearchQuery}
                    searchResults={searchResults}
                    onJumpToResult={handleJumpToResult}
                />
            )}
            
            {/* Speakers Info */}
            {speakers.length > 0 && (
                <Box sx={{ mb: 3 }}>
                    <Typography variant="body2" sx={{ mb: 1, color: theme.palette.text.secondary }}>
                        Speakers:
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        {speakers.map(speaker => (
                            <Chip
                                key={speaker}
                                icon={<PersonIcon />}
                                label={speaker}
                                size="small"
                                variant="outlined"
                            />
                        ))}
                    </Box>
                </Box>
            )}
            
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
                    
                    {segments.map(segment => (
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
                <Paper elevation={0} sx={{
                    mb: 3,
                    p: 2,
                    backgroundColor: alpha(theme.palette.background.paper, 0.7),
                    borderRadius: 1,
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`
                }}>
                    <Typography variant="body2" sx={{ mb: 2, fontStyle: 'italic', color: theme.palette.text.secondary }}>
                        Full Transcript:
                    </Typography>
                    <Typography variant="body1" paragraph>
                        {hasTranscripts
                            ? transcriptionData.data.results.transcripts[0].transcript
                            : "Full transcript not available"}
                    </Typography>
                </Paper>
            )}
            
            <Divider sx={{ my: 3 }} />
            
            <Box sx={{ display: 'flex', justifyContent: 'center' }}>
                <Button
                    variant="outlined"
                    startIcon={<SubtitlesOutlinedIcon />}
                    disabled={!hasTranscripts}
                    onClick={handleExportTranscript}
                >
                    Export Transcript
                </Button>
            </Box>
        </Box>
    );
};

export default TranscriptionTab;
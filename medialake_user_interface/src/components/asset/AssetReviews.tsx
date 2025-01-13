import React, { useState } from 'react';
import {
    Box,
    TextField,
    Button,
    Stack,
    Avatar,
    Chip,
    Typography
} from '@mui/material';

interface Comment {
    user: string;
    avatar: string;
    content: string;
    timestamp: string;
}

interface AssetReviewsProps {
    comments: Comment[];
    onAddComment: (comment: string) => void;
}

const AssetReviews: React.FC<AssetReviewsProps> = ({ comments, onAddComment }) => {
    const [newComment, setNewComment] = useState('');

    const handleSubmit = () => {
        if (newComment.trim()) {
            onAddComment(newComment);
            setNewComment('');
        }
    };

    return (
        <Box sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{
                flexGrow: 1,
                overflowY: 'auto',
                mb: 2,
                '&::-webkit-scrollbar': {
                    width: '0.4em'
                },
                '&::-webkit-scrollbar-track': {
                    boxShadow: 'inset 0 0 6px rgba(0,0,0,0.00)',
                    webkitBoxShadow: 'inset 0 0 6px rgba(0,0,0,0.00)'
                },
                '&::-webkit-scrollbar-thumb': {
                    backgroundColor: 'rgba(0,0,0,.1)',
                    outline: '1px solid slategrey'
                }
            }}>
                <Stack spacing={2}>
                    {comments.map((comment, index) => (
                        <Box
                            key={index}
                            sx={{
                                display: 'flex',
                                justifyContent: index % 2 === 0 ? 'flex-start' : 'flex-end',
                                width: '100%',
                            }}
                        >
                            <Box
                                sx={{
                                    display: 'flex',
                                    flexDirection: index % 2 === 0 ? 'row' : 'row-reverse',
                                    alignItems: 'center',
                                    maxWidth: '80%',
                                }}
                            >
                                <Avatar
                                    src={comment.avatar}
                                    sx={{
                                        width: 32,
                                        height: 32,
                                        marginRight: index % 2 === 0 ? 1 : 0,
                                        marginLeft: index % 2 === 0 ? 0 : 1,
                                    }}
                                />
                                <Chip
                                    label={comment.content}
                                    variant="outlined"
                                    color={index % 2 === 0 ? "primary" : "success"}
                                    sx={{
                                        height: 'auto',
                                        '& .MuiChip-label': {
                                            display: 'block',
                                            whiteSpace: 'normal',
                                            padding: '8px 12px',
                                        },
                                    }}
                                />
                            </Box>
                        </Box>
                    ))}
                </Stack>
            </Box>
            <Box sx={{ mt: 'auto' }}>
                <Box sx={{ display: 'flex', alignItems: 'flex-end' }}>
                    <TextField
                        multiline
                        fullWidth
                        rows={2}
                        maxRows={4}
                        placeholder="Add a comment"
                        value={newComment}
                        onChange={(e) => setNewComment(e.target.value)}
                        sx={{
                            '& .MuiInputBase-root': {
                                maxHeight: 'calc(4em + 32px)',
                                overflowY: 'auto'
                            }
                        }}
                    />
                    <Button
                        variant="contained"
                        onClick={handleSubmit}
                        disabled={!newComment.trim()}
                        sx={{ ml: 1, height: '56px' }}
                    >
                        Post
                    </Button>
                </Box>
            </Box>
        </Box>
    );
};

export default AssetReviews;

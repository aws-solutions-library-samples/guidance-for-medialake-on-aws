import React, { useState } from "react";
import {
  Typography,
  Paper,
  Button,
  TextField,
  List,
  ListItem,
  Divider,
  Box,
  Card,
  CardContent,
  CardActions,
  Avatar,
  IconButton,
} from "@mui/material";
import { ThumbUp, ThumbDown, Comment, Close } from "@mui/icons-material";
import { PLACEHOLDER_IMAGE } from "../utils/placeholderSvg";

interface Comment {
  id: string;
  text: string;
  timestamp: Date;
  author: string;
}

interface VideoReviewData {
  id: string;
  title: string;
  description: string;
  thumbnailUrl: string;
  status: "pending" | "approved" | "denied";
  comments: Comment[];
}

interface VideoReviewInterfaceProps {
  onClose: () => void;
}

const VideoReviewInterface: React.FC<VideoReviewInterfaceProps> = ({
  onClose,
}) => {
  const [currentReview, setCurrentReview] = useState<VideoReviewData>({
    id: "1",
    title: "Sample Video",
    description: "This is a sample video for review",
    thumbnailUrl: PLACEHOLDER_IMAGE,
    status: "pending",
    comments: [],
  });
  const [newComment, setNewComment] = useState("");

  const handleApprove = () => {
    setCurrentReview((prev) => ({ ...prev, status: "approved" }));
    // Here you would typically make an API call to update the status
  };

  const handleDeny = () => {
    setCurrentReview((prev) => ({ ...prev, status: "denied" }));
    // Here you would typically make an API call to update the status
  };

  const handleAddComment = () => {
    if (!newComment.trim()) return;

    const comment: Comment = {
      id: Date.now().toString(),
      text: newComment,
      timestamp: new Date(),
      author: "Current User", // This would typically come from auth context
    };

    setCurrentReview((prev) => ({
      ...prev,
      comments: [...prev.comments, comment],
    }));
    setNewComment("");
    // Here you would typically make an API call to save the comment
  };

  return (
    <Box sx={{ maxWidth: 1200, margin: "0 auto", p: 2 }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
        }}
      >
        <Typography variant="h5">Video Review</Typography>
        <IconButton onClick={onClose}>
          <Close />
        </IconButton>
      </Box>

      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {currentReview.title}
          </Typography>
          <Box
            component="img"
            src={currentReview.thumbnailUrl}
            alt={currentReview.title}
            sx={{ width: "100%", maxHeight: 400, objectFit: "contain", mb: 2 }}
          />
          <Typography variant="body1" color="text.secondary">
            {currentReview.description}
          </Typography>
          <Box sx={{ mt: 2, display: "flex", gap: 2 }}>
            <Typography variant="subtitle2">
              Status:{" "}
              <span
                style={{
                  color:
                    currentReview.status === "approved"
                      ? "green"
                      : currentReview.status === "denied"
                        ? "red"
                        : "orange",
                }}
              >
                {currentReview.status.toUpperCase()}
              </span>
            </Typography>
          </Box>
        </CardContent>
        <CardActions sx={{ justifyContent: "space-between", p: 2 }}>
          <Button
            variant="contained"
            color="success"
            startIcon={<ThumbUp />}
            onClick={handleApprove}
            disabled={currentReview.status !== "pending"}
          >
            Approve
          </Button>
          <Button
            variant="contained"
            color="error"
            startIcon={<ThumbDown />}
            onClick={handleDeny}
            disabled={currentReview.status !== "pending"}
          >
            Deny
          </Button>
        </CardActions>
      </Card>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Comments
        </Typography>
        <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
          <TextField
            fullWidth
            multiline
            rows={2}
            variant="outlined"
            placeholder="Add a comment..."
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
          />
          <Button
            variant="contained"
            startIcon={<Comment />}
            onClick={handleAddComment}
            sx={{ minWidth: 120 }}
          >
            Comment
          </Button>
        </Box>
        <List>
          {currentReview.comments.map((comment, index) => (
            <React.Fragment key={comment.id}>
              {index > 0 && <Divider />}
              <ListItem alignItems="flex-start">
                <Box sx={{ display: "flex", gap: 2, width: "100%" }}>
                  <Avatar>{comment.author[0]}</Avatar>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="subtitle2">
                      {comment.author}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {comment.timestamp.toLocaleString()}
                    </Typography>
                    <Typography variant="body1" sx={{ mt: 1 }}>
                      {comment.text}
                    </Typography>
                  </Box>
                </Box>
              </ListItem>
            </React.Fragment>
          ))}
        </List>
      </Paper>
    </Box>
  );
};

export default VideoReviewInterface;

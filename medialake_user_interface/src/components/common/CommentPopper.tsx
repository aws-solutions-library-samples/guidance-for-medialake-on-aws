import React from "react";
import { Popper } from "@mui/material";
import { styled, css } from "@mui/material/styles";
import { Box, Typography, Avatar } from "@mui/material";

interface CommentPopperProps {
  id: string;
  open: boolean;
  anchorEl: null | HTMLElement;
  comment: {
    user: string;
    avatar: string;
    timestamp: string;
    content: string;
  };
  onClose: () => void;
}

const CommentPopper: React.FC<CommentPopperProps> = ({ id, open, anchorEl, comment }) => {
  return (
    <Popper id={id} open={open} anchorEl={anchorEl}>
      <StyledPopperDiv>
        <Box display="flex" alignItems="center" mb={1}>
          <Avatar src={comment.avatar} sx={{ width: 24, height: 24, mr: 1 }} />
          <Typography variant="subtitle2">{comment.user}</Typography>
        </Box>
        <Typography variant="body2">{comment.content}</Typography>
        <Typography variant="caption" color="text.secondary" mt={1}>
          {comment.timestamp}
        </Typography>
      </StyledPopperDiv>
    </Popper>
  );
};

const StyledPopperDiv = styled("div")(
  ({ theme }) => css`
    background-color: ${theme.palette.background.paper};
    border-radius: 8px;
    border: 1px solid ${theme.palette.divider};
    box-shadow: ${theme.palette.mode === "dark"
      ? `0px 4px 8px rgb(0 0 0 / 0.7)`
      : `0px 4px 8px rgb(0 0 0 / 0.1)`};
    padding: 0.75rem;
    color: ${theme.palette.text.primary};
    font-size: 0.875rem;
    font-family: inherit;
    font-weight: 500;
    opacity: 1;
    margin: 0.25rem 0;
  `
);

export default CommentPopper;

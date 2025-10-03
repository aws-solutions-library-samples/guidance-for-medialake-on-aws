import React from "react";
import { Typography, Box, useTheme } from "@mui/material";

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
}) => {
  const theme = useTheme();

  const parseMarkdown = (text: string) => {
    const lines = text.split("\n");
    const elements: React.ReactNode[] = [];
    const currentIndex = 0;

    lines.forEach((line, index) => {
      const trimmedLine = line.trim();

      // Skip empty lines
      if (!trimmedLine) {
        elements.push(<Box key={`empty-${index}`} sx={{ height: "0.5rem" }} />);
        return;
      }

      // Headers
      if (trimmedLine.startsWith("###")) {
        elements.push(
          <Typography
            key={`h3-${index}`}
            variant="h6"
            sx={{
              fontWeight: 600,
              mb: 1,
              mt: index > 0 ? 2 : 0,
              color: theme.palette.primary.main,
            }}
          >
            {trimmedLine.replace(/^###\s*/, "")}
          </Typography>,
        );
      } else if (trimmedLine.startsWith("##")) {
        elements.push(
          <Typography
            key={`h2-${index}`}
            variant="h5"
            sx={{
              fontWeight: 600,
              mb: 1,
              mt: index > 0 ? 2 : 0,
              color: theme.palette.primary.main,
            }}
          >
            {trimmedLine.replace(/^##\s*/, "")}
          </Typography>,
        );
      } else if (trimmedLine.startsWith("#")) {
        elements.push(
          <Typography
            key={`h1-${index}`}
            variant="h4"
            sx={{
              fontWeight: 600,
              mb: 1,
              mt: index > 0 ? 2 : 0,
              color: theme.palette.primary.main,
            }}
          >
            {trimmedLine.replace(/^#\s*/, "")}
          </Typography>,
        );
      }
      // Bold text with **
      else if (trimmedLine.includes("**")) {
        const parts = trimmedLine.split(/(\*\*[^*]+\*\*)/g);
        const formattedParts = parts.map((part, partIndex) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return (
              <strong key={`bold-${index}-${partIndex}`}>
                {part.replace(/\*\*/g, "")}
              </strong>
            );
          }
          return part;
        });

        elements.push(
          <Typography
            key={`text-${index}`}
            variant="body1"
            paragraph
            sx={{ mb: 1 }}
          >
            {formattedParts}
          </Typography>,
        );
      }
      // List items
      else if (trimmedLine.startsWith("- ") || trimmedLine.startsWith("* ")) {
        elements.push(
          <Box key={`list-${index}`} sx={{ display: "flex", mb: 0.5 }}>
            <Typography
              variant="body1"
              sx={{ mr: 1, color: theme.palette.primary.main }}
            >
              •
            </Typography>
            <Typography variant="body1" sx={{ flex: 1 }}>
              {trimmedLine.replace(/^[-*]\s*/, "")}
            </Typography>
          </Box>,
        );
      }
      // Regular paragraphs
      else {
        elements.push(
          <Typography
            key={`text-${index}`}
            variant="body1"
            paragraph
            sx={{ mb: 1 }}
          >
            {trimmedLine}
          </Typography>,
        );
      }
    });

    return elements;
  };

  return <Box>{parseMarkdown(content)}</Box>;
};

export default MarkdownRenderer;

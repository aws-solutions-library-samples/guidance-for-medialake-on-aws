import React, { useMemo } from "react";
import { Box, Typography } from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import DOMPurify from "dompurify";

/**
 * Public-page portal header.
 *
 * Two rendering paths:
 *   1. **Rich-text path** (preferred): when `titleHtml` or
 *      `descriptionHtml` is a non-empty string, the HTML is passed
 *      through `DOMPurify.sanitize` and injected via
 *      `dangerouslySetInnerHTML` inside a `<Box>` that zeroes paragraph
 *      margins so the Tiptap output sits flush with the surrounding
 *      layout (Requirements 12.5, 12.7, 12.8, 12.9).
 *   2. **Plain-text fallback**: if the HTML field is absent/empty, we
 *      render `name` / `description` via MUI `Typography`, matching the
 *      pre-visual-editor rendering. No Markdown path exists — existing
 *      portals are not migrated.
 *
 * Logo size defaults to 48px and can be overridden via `logoSize`
 * (Requirement 18.1 — the admin configures `appearance.branding.logoSize`
 * and the public page honors it).
 */
const DEFAULT_LOGO_SIZE = 48;

interface Props {
  name: string;
  description?: string;
  logoUrl?: string;
  /**
   * Sanitized HTML for the portal title. When present and non-empty,
   * this replaces the plain-text `name` rendering. Passed through
   * DOMPurify before injection — do not sanitize at the call site as
   * well.
   */
  titleHtml?: string;
  /**
   * Sanitized HTML for the portal description. Same contract as
   * `titleHtml`.
   */
  descriptionHtml?: string;
  /**
   * Logo width/height in pixels. Defaults to {@link DEFAULT_LOGO_SIZE}
   * when omitted. Applied to both the `<img>` and the fallback cloud
   * icon so the header's visual rhythm is consistent.
   */
  logoSize?: number;
  /**
   * Horizontal alignment of the logo and header content.
   * `"left"` (default) renders the logo inline with the text.
   * `"center"` stacks the logo above the text, both centered.
   */
  logoAlignment?: "left" | "center";
  /**
   * When false, the logo (uploaded image or fallback icon) is not rendered
   * at all. Defaults to true to preserve the prior always-show behavior.
   */
  showLogo?: boolean;
}

const PortalHeader: React.FC<Props> = ({
  name,
  description,
  logoUrl,
  titleHtml,
  descriptionHtml,
  logoSize,
  logoAlignment,
  showLogo = true,
}) => {
  const resolvedLogoSize = logoSize ?? DEFAULT_LOGO_SIZE;
  const isCentered = logoAlignment === "center";

  // Sanitize once per incoming HTML; memoized so unrelated re-renders
  // don't re-run DOMPurify.
  const sanitizedTitle = useMemo(
    () => (titleHtml && titleHtml.trim() ? DOMPurify.sanitize(titleHtml) : ""),
    [titleHtml]
  );
  const sanitizedDescription = useMemo(
    () => (descriptionHtml && descriptionHtml.trim() ? DOMPurify.sanitize(descriptionHtml) : ""),
    [descriptionHtml]
  );

  const hasTitleHtml = sanitizedTitle.length > 0;
  const hasDescriptionHtml = sanitizedDescription.length > 0;

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: isCentered ? "column" : "row",
        alignItems: isCentered ? "center" : "center",
        textAlign: isCentered ? "center" : "left",
        gap: isCentered ? 1.5 : 2.5,
        p: "28px 32px 20px",
        borderBottom: "1px solid",
        borderColor: "divider",
      }}
    >
      {showLogo &&
        (logoUrl ? (
          <Box
            component="img"
            src={logoUrl}
            alt=""
            sx={{
              width: resolvedLogoSize,
              height: resolvedLogoSize,
              objectFit: "contain",
              borderRadius: 1,
              flexShrink: 0,
            }}
          />
        ) : (
          <CloudUploadIcon
            sx={{
              fontSize: resolvedLogoSize,
              color: "primary.main",
              flexShrink: 0,
            }}
          />
        ))}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {hasTitleHtml ? (
          <Box
            sx={{
              "& p": { m: 0 },
              "& h1, & h2, & h3": { m: 0 },
              wordBreak: "break-word",
            }}
            dangerouslySetInnerHTML={{ __html: sanitizedTitle }}
          />
        ) : (
          <Typography variant="h5" component="h1" sx={{ fontWeight: 600, wordBreak: "break-word" }}>
            {name}
          </Typography>
        )}
        {hasDescriptionHtml ? (
          <Box
            sx={{
              "& p": { m: 0 },
              mt: 0.5,
              color: "text.secondary",
              wordBreak: "break-word",
            }}
            dangerouslySetInnerHTML={{ __html: sanitizedDescription }}
          />
        ) : description ? (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mt: 0.5, wordBreak: "break-word" }}
          >
            {description}
          </Typography>
        ) : null}
      </Box>
    </Box>
  );
};

export default PortalHeader;

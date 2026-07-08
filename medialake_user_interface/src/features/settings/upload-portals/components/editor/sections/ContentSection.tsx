import React, { useCallback, useState } from "react";
import { Stack, TextField, Typography } from "@mui/material";
import { ToggleButton, ToggleButtonGroup } from "@mui/material";

import { usePortalEditorStore } from "../../../stores/usePortalEditorStore";
import RichTextEditor from "../RichTextEditor.lazy";

/**
 * Maximum length for the submit-button label. Mirrors the 1-50 range from
 * Requirement 8.7 and the Zod schema in `appearance.schema.ts`.
 */
const SUBMIT_BUTTON_MAX_LENGTH = 50;

/** Maximum length for the success message. */
const SUCCESS_MESSAGE_MAX_LENGTH = 500;

/** Maximum length for the drop zone text. */
const DROP_ZONE_TEXT_MAX_LENGTH = 200;

/**
 * Slugify a free-form portal slug input.
 *
 * Lowercases, trims, collapses every run of non-alphanumeric characters into
 * a single `-`, then strips leading/trailing dashes. Kept inline because the
 * rest of the codebase has no shared slugify helper yet and the behavior
 * here is tiny and purpose-built for portal URLs.
 *
 *   "My Cool Portal!" -> "my-cool-portal"
 *   "  foo__bar  "    -> "foo-bar"
 *   "---"             -> ""
 */
const slugify = (input: string): string =>
  input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

/**
 * Build the portal URL preview string displayed under the slug field.
 *
 * In the browser this resolves to `${window.location.origin}/p/${slug}`.
 * During SSR or tests where `window` is not a DOM window, we fall back to a
 * relative path so the component never throws during render.
 */
const buildPortalUrl = (slug: string): string => {
  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin}/p/${slug}`;
  }
  return `/p/${slug}`;
};

/**
 * ContentSection
 *
 * Edits the visible portal content: title, description, slug, submit-button
 * text, and footer. Rendered inside the sidebar's "Content" accordion.
 *
 * Controls (top-to-bottom):
 *   1. Title {@link RichTextEditor} bound to `appearance.content.titleHtml`
 *      with `singleLine={true}` so Enter does not insert a line break
 *      (Requirement 8.3).
 *   2. Description {@link RichTextEditor} bound to
 *      `appearance.content.descriptionHtml` (multi-line, Requirement 8.4).
 *   3. Slug `TextField` auto-slugifying on every change, with the resolved
 *      public portal URL (`<origin>/p/<slug>`) displayed underneath
 *      (Requirement 8.6).
 *   4. Upload-button `TextField` bound to
 *      `appearance.content.submitButtonText`, with a live char-count helper
 *      and a blur-time guard that reverts empty input back to the previous
 *      value so the field can never be saved as a blank string
 *      (Requirement 8.7). This labels the uploader's OWN upload-trigger
 *      button ("Upload assets" by default) — it does NOT control the
 *      page-level Submit/Complete action, which is a fixed string so the
 *      two buttons stay visually distinct.
 *   5. Footer {@link RichTextEditor} bound to
 *      `appearance.content.footerHtml` (Requirement 8.5).
 *
 * Store subscriptions are all fine-grained so editing one field does not
 * re-render the siblings.
 */
const ContentSection: React.FC = () => {
  const titleHtml = usePortalEditorStore((s) => s.appearance.content.titleHtml);
  const descriptionHtml = usePortalEditorStore((s) => s.appearance.content.descriptionHtml);
  const footerHtml = usePortalEditorStore((s) => s.appearance.content.footerHtml);
  const submitButtonText = usePortalEditorStore((s) => s.appearance.content.submitButtonText);
  const successMessage = usePortalEditorStore((s) => s.appearance.content.successMessage);
  const dropZoneText = usePortalEditorStore((s) => s.appearance.content.dropZoneText);
  const buttonStyle = usePortalEditorStore((s) => s.appearance.content.buttonStyle);
  const buttonRounding = usePortalEditorStore((s) => s.appearance.content.buttonRounding);
  const slug = usePortalEditorStore((s) => s.portalData?.slug ?? "");
  const name = usePortalEditorStore((s) => (s.portalData?.name as string) ?? "");

  // Field-level validation errors for this section
  const sectionErrors = usePortalEditorStore((s) => s.validationErrors.content);
  const slugError = sectionErrors?.find((e) => e.field === "slug")?.message;
  const nameError = sectionErrors?.find((e) => e.field === "name")?.message;

  const updateContent = usePortalEditorStore((s) => s.updateContent);
  const updateSlug = usePortalEditorStore((s) => s.updateSlug);
  const updatePortalData = usePortalEditorStore((s) => s.updatePortalData);

  // Local mirror for the submit-button input so we can allow the user to
  // temporarily clear the field while typing. Only the blur-time handler
  // commits (or reverts) the value back into the store.
  const [submitDraft, setSubmitDraft] = useState(submitButtonText);

  // Keep the local draft in sync when the store value changes externally
  // (e.g. appearance reset, draft rehydration). A plain `useEffect` would
  // work here but a guarded setter avoids re-entrant updates during typing.
  React.useEffect(() => {
    setSubmitDraft((prev) => (prev === submitButtonText ? prev : submitButtonText));
  }, [submitButtonText]);

  const handleTitleChange = useCallback(
    (html: string) => {
      updateContent({ titleHtml: html });
    },
    [updateContent]
  );

  const handleDescriptionChange = useCallback(
    (html: string) => {
      updateContent({ descriptionHtml: html });
    },
    [updateContent]
  );

  const handleFooterChange = useCallback(
    (html: string) => {
      updateContent({ footerHtml: html });
    },
    [updateContent]
  );

  const handleSlugChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      // Slugify on every keystroke so the stored value is always a valid
      // URL segment. The field will visually collapse uppercase/spaces
      // as the user types, which matches the behavior of the legacy
      // PortalForm step-1 dialog.
      updateSlug(slugify(event.target.value));
    },
    [updateSlug]
  );

  const handleNameChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      updatePortalData({ name: event.target.value });
    },
    [updatePortalData]
  );

  const handleSubmitDraftChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const next = event.target.value;
      setSubmitDraft(next);
      // Propagate non-empty drafts to the store immediately so the live
      // preview tracks typing. The empty-revert safety net only runs on blur.
      if (next.length > 0) {
        updateContent({ submitButtonText: next });
      }
    },
    [updateContent]
  );

  const handleSubmitBlur = useCallback(() => {
    // Requirement 8.7: min length 1 validated on blur. If the user cleared
    // the field, snap it back to the previous committed value instead of
    // persisting an invalid empty string.
    if (submitDraft.length === 0) {
      setSubmitDraft(submitButtonText);
      return;
    }
    // No-op when the draft already matches the store; otherwise commit. This
    // covers the edge case where the user typed, deleted down to 1 char,
    // then blurred.
    if (submitDraft !== submitButtonText) {
      updateContent({ submitButtonText: submitDraft });
    }
  }, [submitDraft, submitButtonText, updateContent]);

  const handleSuccessMessageChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      updateContent({ successMessage: event.target.value });
    },
    [updateContent]
  );

  const handleDropZoneTextChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      updateContent({ dropZoneText: event.target.value });
    },
    [updateContent]
  );

  const handleButtonStyleChange = useCallback(
    (_event: React.MouseEvent<HTMLElement>, value: "contained" | "outlined" | "text" | null) => {
      if (value === null) return;
      updateContent({ buttonStyle: value });
    },
    [updateContent]
  );

  const handleButtonRoundingChange = useCallback(
    (_event: React.MouseEvent<HTMLElement>, value: "square" | "rounded" | "pill" | null) => {
      if (value === null) return;
      updateContent({ buttonRounding: value });
    },
    [updateContent]
  );

  const portalUrl = buildPortalUrl(slug);

  return (
    <Stack spacing={2}>
      {/* Portal name */}
      <TextField
        label="Portal name"
        value={name}
        onChange={handleNameChange}
        size="small"
        fullWidth
        required
        error={!!nameError}
        helperText={nameError}
        inputProps={{ "aria-label": "Portal name" }}
      />

      {/* Title — single-line rich text so the title never wraps onto a
          second line. Enter is swallowed by the Tiptap editor itself via
          the `singleLine` prop (Requirement 8.11). */}
      <div>
        <Typography variant="caption" color="text.secondary" component="div">
          Title
        </Typography>
        <RichTextEditor
          value={titleHtml}
          onChange={handleTitleChange}
          singleLine
          ariaLabel="Title editor" // i18n-ignore
        />
      </div>

      {/* Description — full multi-line rich text, including headings and
          lists when the user uses the bubble menu. */}
      <div>
        <Typography variant="caption" color="text.secondary" component="div">
          Description
        </Typography>
        <RichTextEditor
          value={descriptionHtml}
          onChange={handleDescriptionChange}
          ariaLabel="Description editor" // i18n-ignore
          minHeight={144}
        />
      </div>

      {/* Slug + portal URL preview */}
      <div>
        <TextField
          label="Slug"
          value={slug}
          onChange={handleSlugChange}
          size="small"
          fullWidth
          required
          error={!!slugError}
          helperText={slugError ?? portalUrl}
          inputProps={{ "aria-label": "Portal slug" }}
        />
      </div>

      {/* Upload-button text — labels the uploader's own upload-trigger
          button, distinct from the page-level Submit/Complete action. */}
      <TextField
        label="Upload button text"
        value={submitDraft}
        onChange={handleSubmitDraftChange}
        onBlur={handleSubmitBlur}
        size="small"
        fullWidth
        inputProps={{ maxLength: SUBMIT_BUTTON_MAX_LENGTH }}
        helperText={`${submitDraft.length}/${SUBMIT_BUTTON_MAX_LENGTH}`}
      />

      {/* Footer — free-form rich text. */}
      <div>
        <Typography variant="caption" color="text.secondary" component="div">
          Footer
        </Typography>
        <RichTextEditor
          value={footerHtml}
          onChange={handleFooterChange}
          ariaLabel="Footer editor" // i18n-ignore
          minHeight={96}
        />
      </div>

      {/* Success message */}
      <TextField
        label="Success message"
        value={successMessage}
        onChange={handleSuccessMessageChange}
        size="small"
        fullWidth
        multiline
        minRows={2}
        inputProps={{ maxLength: SUCCESS_MESSAGE_MAX_LENGTH }}
        helperText={`Shown after upload completes. ${successMessage.length}/${SUCCESS_MESSAGE_MAX_LENGTH}`}
      />

      {/* Drop zone text */}
      <TextField
        label="Drop zone text"
        value={dropZoneText}
        onChange={handleDropZoneTextChange}
        size="small"
        fullWidth
        inputProps={{ maxLength: DROP_ZONE_TEXT_MAX_LENGTH }}
        helperText={`${dropZoneText.length}/${DROP_ZONE_TEXT_MAX_LENGTH}`}
      />

      {/* Button style */}
      <div>
        <Typography variant="caption" color="text.secondary" component="div">
          Button style
        </Typography>
        <ToggleButtonGroup
          value={buttonStyle}
          exclusive
          onChange={handleButtonStyleChange}
          size="small"
          aria-label="Button style"
          sx={{ mt: 0.5 }}
        >
          <ToggleButton value="contained" aria-label="Filled">
            Filled
          </ToggleButton>
          <ToggleButton value="outlined" aria-label="Outlined">
            Outlined
          </ToggleButton>
          <ToggleButton value="text" aria-label="Text">
            Text
          </ToggleButton>
        </ToggleButtonGroup>
      </div>

      {/* Button rounding */}
      <div>
        <Typography variant="caption" color="text.secondary" component="div">
          Button rounding
        </Typography>
        <ToggleButtonGroup
          value={buttonRounding}
          exclusive
          onChange={handleButtonRoundingChange}
          size="small"
          aria-label="Button rounding"
          sx={{ mt: 0.5 }}
        >
          <ToggleButton value="square" aria-label="Square">
            Square
          </ToggleButton>
          <ToggleButton value="rounded" aria-label="Rounded">
            Rounded
          </ToggleButton>
          <ToggleButton value="pill" aria-label="Pill">
            Pill
          </ToggleButton>
        </ToggleButtonGroup>
      </div>
    </Stack>
  );
};

export { ContentSection };
export default React.memo(ContentSection);

/**
 * Shared `File` → base64 helper used by the portal editor's upload paths.
 *
 * The backend logo/banner endpoints accept a `{ data, contentType }` body
 * where `data` is the base64 payload without the `data:<mime>;base64,`
 * prefix. `BrandingSection` (immediate uploads in edit mode) and the
 * Save/Publish handlers in `PortalEditorPage` (deferred uploads in create
 * mode) both need exactly this conversion, so it lives here instead of
 * being duplicated across components.
 *
 * Resolves with `{ base64, contentType }`:
 *   - `base64`: the payload stripped of its data-URL prefix.
 *   - `contentType`: `file.type`, falling back to
 *     `application/octet-stream` when the browser has no MIME hint.
 *
 * Rejects when the reader errors or returns a non-string result so callers
 * can surface a single error path.
 */
export const readFileAsBase64 = (file: File): Promise<{ base64: string; contentType: string }> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("FileReader returned a non-string result"));
        return;
      }
      // data URLs are `data:<mime>;base64,<payload>`; strip up to and
      // including the first comma so we match the shape expected by
      // `useUploadPortalLogo` / `useUploadPortalBanner`.
      const [, payload = ""] = result.split(",", 2);
      resolve({
        base64: payload,
        contentType: file.type || "application/octet-stream",
      });
    };
    reader.onerror = () => reject(reader.error ?? new Error("FileReader error"));
    reader.readAsDataURL(file);
  });

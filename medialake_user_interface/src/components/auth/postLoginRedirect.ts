/**
 * Where to send the user after they sign in.
 *
 * ProtectedRoute / PermissionGuard redirect to /sign-in with
 * `state: { from: location }`. Returning there after login preserves deep
 * links. The value comes from history state, so it is validated: only a
 * same-origin, app-relative path (one leading "/", not "//" or "/\") that is
 * not the sign-in page itself is accepted. Anything else falls back to "/".
 */
export const DEFAULT_POST_LOGIN_PATH = "/";

const SIGN_IN_PATH = "/sign-in";

interface FromLocation {
  pathname?: unknown;
  search?: unknown;
  hash?: unknown;
}

const asString = (value: unknown): string => (typeof value === "string" ? value : "");

export function getPostLoginPath(state: unknown): string {
  const from = (state as { from?: FromLocation } | null | undefined)?.from;
  if (!from || typeof from !== "object" || typeof from.pathname !== "string") {
    return DEFAULT_POST_LOGIN_PATH;
  }

  const { pathname } = from;
  // Exactly one leading slash: "//host" and "/\host" are protocol-relative
  // URLs that browsers resolve to another origin.
  if (!pathname.startsWith("/") || pathname[1] === "/" || pathname[1] === "\\") {
    return DEFAULT_POST_LOGIN_PATH;
  }
  if (pathname === SIGN_IN_PATH || pathname.startsWith(`${SIGN_IN_PATH}/`)) {
    return DEFAULT_POST_LOGIN_PATH;
  }

  const path = pathname + asString(from.search) + asString(from.hash);

  // Belt and braces: the URL parser strips tabs/newlines, so resolve the
  // path and require that it stays on this origin.
  try {
    const origin = window.location.origin;
    if (new URL(path, origin).origin !== origin) {
      return DEFAULT_POST_LOGIN_PATH;
    }
  } catch {
    return DEFAULT_POST_LOGIN_PATH;
  }

  return path;
}

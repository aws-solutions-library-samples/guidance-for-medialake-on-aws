import React, { useEffect, useState } from "react";
import { Box, Button, Card, TextField, Alert, CircularProgress, Typography } from "@mui/material";
import { StorageHelper } from "@/common/helpers/storage-helper";
import { usePortalApi } from "../hooks/usePortalApi";
import type { PortalAuthCredentials } from "../types/portal.types";

/**
 * sessionStorage key used to stash the CSRF-protecting OAuth `state`
 * between the initial redirect to Cognito and the callback handler that
 * parses the hash fragment. Exported so the callback handler can import
 * the same key instead of a stringly-typed duplicate.
 */
export const PORTAL_OAUTH_STATE_KEY = "portal.oauth.state";

/**
 * Generate a cryptographically-random string suitable for use as an OAuth
 * `state` value. Requires `crypto.getRandomValues` — throws if unavailable.
 */
function generateOAuthState(): string {
  if (typeof crypto === "undefined" || typeof crypto.getRandomValues !== "function") {
    throw new Error("Secure random unavailable: crypto.getRandomValues required");
  }
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  // Hex-encode — URL-safe and predictable length.
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

interface Props {
  slug: string;
  urlToken?: string | null;
  onSessionEstablished: (jwt: string) => void;
  onPortalUnavailable: (reason: "inactive" | "expired") => void;
}

type GateStep = "loading" | "email" | "passphrase" | "cognito-redirect";

const PortalAccessGate: React.FC<Props> = ({
  slug,
  urlToken,
  onSessionEstablished,
  onPortalUnavailable,
}) => {
  const [step, setStep] = useState<GateStep>("loading");
  const [email, setEmail] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [capturedToken, setCapturedToken] = useState<string | null>(null);
  const [capturedEmail, setCapturedEmail] = useState<string | null>(null);

  const { authenticate } = usePortalApi(slug, null);

  // Probe-based mode discovery on mount
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const result = await authenticate({});
        if (!cancelled && result.sessionToken) {
          // Redirect public portals from /upload/ to /p/
          if (result.accessMode === "public" && window.location.pathname.startsWith("/upload/")) {
            const slug = window.location.pathname.replace(/^\/upload\//, "");
            window.location.replace(`/p/${slug}${window.location.search}`);
            return;
          }
          onSessionEstablished(result.sessionToken);
        }
      } catch (err: any) {
        if (cancelled) return;
        const msg = err?.response?.data?.message || err?.response?.data?.error?.message || "";

        if (err?.response?.status === 403) {
          onPortalUnavailable("inactive");
        } else if (/not available|inactive/i.test(msg)) {
          onPortalUnavailable(/expired/i.test(msg) ? "expired" : "inactive");
        } else if (/expired/i.test(msg) && /portal/i.test(msg)) {
          onPortalUnavailable("expired");
        } else if (/authorization header required/i.test(msg)) {
          // Check if returning from Cognito redirect
          const hash = window.location.hash;
          if (hash.includes("id_token=")) {
            const params = new URLSearchParams(hash.substring(1));
            const idToken = params.get("id_token");
            if (idToken) {
              window.history.replaceState(
                null,
                "",
                window.location.pathname + window.location.search
              );
              try {
                const r = await authenticate({}, { Authorization: `Bearer ${idToken}` });
                if (!cancelled) onSessionEstablished(r.sessionToken);
              } catch {
                if (!cancelled) setStep("cognito-redirect");
              }
              return;
            }
          }
          setStep("cognito-redirect");
        } else if (
          /token and email are required/i.test(msg) ||
          /passphrase is required/i.test(msg)
        ) {
          setStep(urlToken ? "email" : "passphrase");
        } else {
          setStep("passphrase");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !urlToken) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await authenticate({ token: urlToken, email: email.trim() });
      onSessionEstablished(result.sessionToken);
    } catch (err: any) {
      const msg =
        err?.response?.data?.message ||
        err?.response?.data?.error?.message ||
        "Authentication failed. Please try again.";

      if (/passphrase is required/i.test(msg)) {
        setCapturedToken(urlToken);
        setCapturedEmail(email.trim());
        setError(null);
        setStep("passphrase");
      } else if (/expired/i.test(msg)) {
        setError("Link expired. Contact the portal administrator for a new link.");
      } else {
        setError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handlePassphraseSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!passphrase.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const creds: PortalAuthCredentials =
        capturedToken && capturedEmail
          ? { token: capturedToken, email: capturedEmail, passphrase: passphrase.trim() }
          : { passphrase: passphrase.trim() };
      const result = await authenticate(creds);
      onSessionEstablished(result.sessionToken);
    } catch (err: any) {
      const msg =
        err?.response?.data?.message ||
        err?.response?.data?.error?.message ||
        "Authentication failed. Please try again.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCognitoRedirect = () => {
    const cognitoConfig = StorageHelper.getAwsConfig()?.Auth?.Cognito;
    if (!cognitoConfig) {
      setError("Cognito configuration not found.");
      return;
    }
    const { userPoolClientId, loginWith } = cognitoConfig;
    const domain = loginWith?.oauth?.domain;
    const redirectUri = window.location.origin + window.location.pathname + window.location.search;

    // Generate a CSRF-protecting `state` value. The callback handler is
    // responsible for pulling the same key out of sessionStorage and
    // comparing it to the `state` returned by Cognito — a mismatch
    // indicates the response didn't originate from our redirect.
    const state = generateOAuthState();
    try {
      sessionStorage.setItem(PORTAL_OAUTH_STATE_KEY, state);
    } catch {
      // sessionStorage may be unavailable (private browsing, SSR). We
      // still send the parameter; the callback handler will treat a
      // missing stored value as a failed CSRF check.
    }

    const url = `https://${domain}/oauth2/authorize?response_type=token&client_id=${userPoolClientId}&redirect_uri=${encodeURIComponent(
      redirectUri
    )}&scope=openid+email+profile&state=${encodeURIComponent(state)}`;
    window.location.href = url;
  };

  if (step === "loading") {
    return (
      <Box sx={{ p: 4, textAlign: "center" }}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  return (
    <Card sx={{ p: 4 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Access Portal
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {step === "email" && (
        <Box
          component="form"
          onSubmit={handleEmailSubmit}
          sx={{ display: "flex", flexDirection: "column", gap: 2 }}
        >
          <Typography variant="body2" color="text.secondary">
            Enter your email to continue.
          </Typography>
          <TextField
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            fullWidth
            autoFocus
          />
          <Button type="submit" variant="contained" disabled={submitting || !email.trim()}>
            {submitting ? <CircularProgress size={20} /> : "Continue"}
          </Button>
        </Box>
      )}

      {step === "passphrase" && (
        <Box
          component="form"
          onSubmit={handlePassphraseSubmit}
          sx={{ display: "flex", flexDirection: "column", gap: 2 }}
        >
          <Typography variant="body2" color="text.secondary">
            Enter the passphrase to access this portal.
          </Typography>
          <TextField
            label="Passphrase"
            type="password"
            value={passphrase}
            onChange={(e) => setPassphrase(e.target.value)}
            required
            fullWidth
            autoFocus
          />
          <Button type="submit" variant="contained" disabled={submitting || !passphrase.trim()}>
            {submitting ? <CircularProgress size={20} /> : "Submit"}
          </Button>
        </Box>
      )}

      {step === "cognito-redirect" && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, alignItems: "center" }}>
          <Typography variant="body2" color="text.secondary">
            Sign in with your organization account to continue.
          </Typography>
          <Button variant="contained" onClick={handleCognitoRedirect} disabled={submitting}>
            Sign In
          </Button>
        </Box>
      )}
    </Card>
  );
};

export default PortalAccessGate;

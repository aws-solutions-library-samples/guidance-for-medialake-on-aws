import React, { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Box, Button, CircularProgress, Typography } from "@mui/material";
import {
  WafCaptchaNotConfiguredError,
  loadWafCaptchaSdk,
  resolveWafCaptchaConfig,
} from "../api/wafCaptchaSdk";

interface CaptchaGateProps {
  captchaEnabled: boolean;
  onCaptchaComplete: () => void;
  children: React.ReactNode;
}

const LOAD_FAILED_MESSAGE =
  "The CAPTCHA verification could not be loaded. Please check your network connection and try again.";
const CONFIG_MISSING_MESSAGE =
  "CAPTCHA configuration is missing. Please contact the portal administrator.";

const CaptchaGate: React.FC<CaptchaGateProps> = ({
  captchaEnabled,
  onCaptchaComplete,
  children,
}) => {
  const [captchaSolved, setCaptchaSolved] = useState(!captchaEnabled);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  /** Reset solved state when captchaEnabled changes from false → true */
  useEffect(() => {
    setCaptchaSolved(!captchaEnabled);
  }, [captchaEnabled]);

  const renderCaptcha = useCallback(async () => {
    if (!containerRef.current) return;

    setError(null);
    setLoading(true);

    // The SDK URL and API key come from aws-exports.json (Portal.*); the SDK
    // is injected only now, when a CAPTCHA-enabled portal needs it. Missing
    // configuration fails closed: the children are never rendered.
    const { sdkUrl, apiKey } = await resolveWafCaptchaConfig();
    if (!apiKey) {
      setLoading(false);
      setError(CONFIG_MISSING_MESSAGE);
      return;
    }

    try {
      await loadWafCaptchaSdk(sdkUrl);
    } catch (err) {
      setLoading(false);
      setError(
        err instanceof WafCaptchaNotConfiguredError ? CONFIG_MISSING_MESSAGE : LOAD_FAILED_MESSAGE
      );
      return;
    }

    const container = containerRef.current;
    if (!container) return; // unmounted while loading

    if (typeof AwsWafCaptcha === "undefined") {
      setLoading(false);
      setError(LOAD_FAILED_MESSAGE);
      return;
    }

    // Clear previous widget content before re-rendering
    container.innerHTML = "";

    try {
      AwsWafCaptcha.renderCaptcha(container, {
        apiKey,
        onSuccess: () => {
          setCaptchaSolved(true);
          onCaptchaComplete();
        },
        onError: (err: Error) => {
          console.error("CAPTCHA error:", err);
          setError("Verification failed. Please try again.");
          setLoading(false);
        },
        dynamicWidth: true,
        skipTitle: true,
      });
      setLoading(false);
    } catch (err) {
      console.error("CAPTCHA render error:", err);
      setLoading(false);
      setError(LOAD_FAILED_MESSAGE);
    }
  }, [onCaptchaComplete]);

  /** Render the CAPTCHA widget when enabled and not yet solved */
  useEffect(() => {
    if (!captchaEnabled || captchaSolved) return;
    renderCaptcha();
  }, [captchaEnabled, captchaSolved, renderCaptcha]);

  if (captchaSolved) {
    return <>{children}</>;
  }

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 2,
        py: 4,
        px: 2,
      }}
    >
      <Typography variant="body1" color="text.secondary">
        Please complete the verification below
      </Typography>

      {loading && <CircularProgress size={32} />}

      {error && (
        <Alert
          severity="error"
          sx={{ width: "100%", maxWidth: 400 }}
          action={
            <Button color="inherit" size="small" onClick={renderCaptcha}>
              Retry
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      <Box ref={containerRef} sx={{ minHeight: 200, width: "100%" }} />
    </Box>
  );
};

export default CaptchaGate;

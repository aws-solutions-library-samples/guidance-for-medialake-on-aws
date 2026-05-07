import React, { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Box, Button, CircularProgress, Typography } from "@mui/material";

interface CaptchaGateProps {
  captchaEnabled: boolean;
  onCaptchaComplete: () => void;
  children: React.ReactNode;
}

/**
 * WAF CAPTCHA API key — injected at build time.
 * Safe to embed client-side; it only authorises CAPTCHA widget rendering.
 */
const WAF_CAPTCHA_API_KEY = import.meta.env.VITE_WAF_CAPTCHA_API_KEY as string | undefined;

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

  const renderCaptcha = useCallback(() => {
    if (!containerRef.current) return;

    setError(null);
    setLoading(true);

    if (typeof AwsWafCaptcha === "undefined") {
      setLoading(false);
      setError(
        "The CAPTCHA verification could not be loaded. Please check your network connection and try again."
      );
      return;
    }

    if (!WAF_CAPTCHA_API_KEY) {
      setLoading(false);
      setError("CAPTCHA configuration is missing. Please contact the portal administrator.");
      return;
    }

    // Clear previous widget content before re-rendering
    containerRef.current.innerHTML = "";

    try {
      AwsWafCaptcha.renderCaptcha(containerRef.current, {
        apiKey: WAF_CAPTCHA_API_KEY,
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
      setError(
        "The CAPTCHA verification could not be loaded. Please check your network connection and try again."
      );
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

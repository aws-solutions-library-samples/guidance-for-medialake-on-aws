import React from "react";
import { Box, Typography, Slider } from "@mui/material";
import { useTranslation } from "react-i18next";
import { CONFIDENCE_COLORS, getThresholdsForModel } from "@/components/common/utils";

interface ConfidenceSliderProps {
  value: number;
  modelVersion?: string;
  onChange: (value: number) => void;
  onChangeCommitted: (value: number) => void;
}

function ConfidenceSlider({
  value,
  modelVersion,
  onChange,
  onChangeCommitted,
}: ConfidenceSliderProps) {
  const [sliderValue, setSliderValue] = React.useState(value);
  const [isSliderActive, setIsSliderActive] = React.useState(false);

  React.useEffect(() => {
    if (!isSliderActive) {
      setSliderValue(value);
    }
  }, [value, isSliderActive]);

  const thresholds = getThresholdsForModel(modelVersion);
  const { t } = useTranslation();

  const confidenceMarks = [
    {
      value: thresholds.MIN,
      label: (
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              bgcolor: CONFIDENCE_COLORS.LOW,
            }}
          />
          <span>{t("common.viewControls.confidence.low")}</span>
        </Box>
      ),
    },
    {
      value: thresholds.MEDIUM,
      label: (
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              bgcolor: CONFIDENCE_COLORS.MEDIUM,
            }}
          />
          <span>{t("common.viewControls.confidence.med")}</span>
        </Box>
      ),
    },
    {
      value: thresholds.HIGH,
      label: (
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              bgcolor: CONFIDENCE_COLORS.HIGH,
            }}
          />
          <span>{t("common.viewControls.confidence.high")}</span>
        </Box>
      ),
    },
  ];

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        minWidth: 320,
        flexShrink: 0,
      }}
    >
      <Typography
        variant="body2"
        sx={{
          fontSize: "0.875rem",
          color: "text.secondary",
          whiteSpace: "nowrap",
          pr: 0.5,
          mt: -3.0,
        }}
      >
        {t("common.viewControls.confidence.label")}
      </Typography>
      <Slider
        value={sliderValue}
        onChange={(_, val) => {
          setSliderValue(val as number);
          setIsSliderActive(true);
          onChange(val as number);
        }}
        onChangeCommitted={(_, val) => {
          setIsSliderActive(false);
          onChangeCommitted(val as number);
        }}
        min={thresholds.MIN}
        max={thresholds.MAX}
        step={0.001}
        marks={confidenceMarks}
        size="small"
        sx={{
          width: 200,
          mb: 3,
          "& .MuiSlider-thumb": { width: 16, height: 16 },
          "& .MuiSlider-track": { height: 3 },
          "& .MuiSlider-rail": { height: 3 },
          "& .MuiSlider-mark": { display: "none" },
          "& .MuiSlider-markLabel": {
            fontSize: "0.7rem",
            color: "text.secondary",
            top: 28,
          },
          "& .MuiSlider-markLabel[data-index='0']": {
            left: "0% !important",
            transform: "translateX(0)",
          },
          "& .MuiSlider-markLabel[data-index='1']": {
            left: "50% !important",
            transform: "translateX(-50%)",
          },
          "& .MuiSlider-markLabel[data-index='2']": {
            left: "100% !important",
            transform: "translateX(-100%)",
          },
        }}
      />
      <Typography
        variant="body2"
        sx={{
          minWidth: 50,
          fontSize: "0.875rem",
          color: "text.secondary",
          textAlign: "center",
          fontWeight: 500,
          mt: -3.0,
        }}
      >
        {sliderValue.toFixed(3).substring(1)}
      </Typography>
    </Box>
  );
}

export default ConfidenceSlider;

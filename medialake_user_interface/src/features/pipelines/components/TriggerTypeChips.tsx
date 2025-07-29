import React from "react";
import { Stack, Chip, Tooltip, Typography, Box } from "@mui/material";
import {
  Event as EventIcon,
  Api as ApiIcon,
  TouchApp as ManualIcon,
  Image as ImageIcon,
  Videocam as VideoIcon,
  AudioFile as AudioIcon,
  Code as CodeIcon,
} from "@mui/icons-material";
import { Pipeline } from "../types/pipelines.types";

interface EventRule {
  ruleName?: string;
  eventBusName?: string;
  ruleArn?: string;
  description?: string;
  fileTypes?: string[];
  eventType?: string;
}

interface EventRuleInfo {
  triggerTypes: string[];
  eventRules: EventRule[];
}

interface TriggerTypeChipsProps {
  triggerTypes: string[];
  eventRuleInfo?: EventRuleInfo;
  pipeline?: Pipeline;
}

/**
 * Component to display multiple trigger types as chips in a horizontal stack
 */
export const TriggerTypeChips: React.FC<TriggerTypeChipsProps> = ({
  triggerTypes,
  eventRuleInfo,
  pipeline,
}) => {
  // If eventRuleInfo is not provided but pipeline is, extract the info from the pipeline
  const derivedEventRuleInfo = React.useMemo(() => {
    if (eventRuleInfo) return eventRuleInfo;
    if (!pipeline) return undefined;

    return extractEventRuleInfoFromPipeline(pipeline);
  }, [eventRuleInfo, pipeline]);

  return (
    <Stack direction="row" spacing={0.5} flexWrap="wrap">
      {triggerTypes.map((type, index) => {
        const icon = getTriggerIcon(type);
        const tooltipContent = getTooltipContent(type, derivedEventRuleInfo);

        return (
          <Tooltip key={index} title={tooltipContent} arrow placement="top">
            <Chip
              icon={icon}
              label={type}
              size="small"
              color={getChipColor(type)}
            />
          </Tooltip>
        );
      })}
    </Stack>
  );
};

/**
 * Extract event rule information from a pipeline object
 */
const extractEventRuleInfoFromPipeline = (
  pipeline: Pipeline,
): EventRuleInfo => {
  const eventRuleInfo: EventRuleInfo = {
    triggerTypes: ["Event Triggered"],
    eventRules: [],
  };

  // Check for Event Triggered (EventBridge rules)
  if (pipeline.dependentResources) {
    for (const [resourceType, resourceValue] of pipeline.dependentResources) {
      if (resourceType === "eventbridge_rule") {
        // Extract rule name and eventbus name if available
        const rule: EventRule = {};

        if (typeof resourceValue === "object" && resourceValue !== null) {
          rule.ruleName = resourceValue.rule_name || "";
          rule.eventBusName = resourceValue.eventbus_name || "";
        } else {
          // If it's just a string ARN, extract the rule name from the ARN
          rule.ruleArn = resourceValue as string;
          if (
            typeof resourceValue === "string" &&
            resourceValue.includes("/")
          ) {
            rule.ruleName = resourceValue.split("/").pop() || "";
          }
        }

        // Try to extract human-friendly information from the rule name
        if (rule.ruleName) {
          const ruleName = rule.ruleName;

          // Check for default pipeline patterns
          if (
            ruleName.includes("default-image-pipeline") ||
            pipeline.name.includes("Image Pipeline")
          ) {
            rule.description =
              "Triggers on image files (TIF, JPG, JPEG, PNG, WEBP, GIF, SVG)";
            rule.fileTypes = [
              "TIF",
              "JPG",
              "JPEG",
              "PNG",
              "WEBP",
              "GIF",
              "SVG",
            ];
            rule.eventType = "AssetCreated";
          } else if (
            ruleName.includes("default-video-pipeline") ||
            pipeline.name.includes("Video Pipeline")
          ) {
            rule.description =
              "Triggers on video files (MP4, MOV, AVI, MKV, WEBM)";
            rule.fileTypes = ["MP4", "MOV", "AVI", "MKV", "WEBM"];
            rule.eventType = "AssetCreated";
          } else if (
            ruleName.includes("default-audio-pipeline") ||
            pipeline.name.includes("Audio Pipeline")
          ) {
            rule.description =
              "Triggers on audio files (WAV, AIFF, AIF, MP3, PCM, M4A)";
            rule.fileTypes = ["WAV", "AIFF", "AIF", "MP3", "PCM", "M4A"];
            rule.eventType = "AssetCreated";
          } else if (ruleName.includes("pipeline_execution_completed")) {
            rule.description =
              "Triggers when another pipeline completes execution";
            rule.eventType = "Pipeline Execution Completed";
          } else {
            rule.description = `Custom event rule: ${ruleName}`;
          }
        }

        eventRuleInfo.eventRules.push(rule);
      }
    }
  }

  return eventRuleInfo;
};

/**
 * Get the appropriate icon for a trigger type
 */
const getTriggerIcon = (type: string) => {
  switch (type) {
    case "Event Triggered":
      return <EventIcon fontSize="small" />;
    case "API Triggered":
      return <ApiIcon fontSize="small" />;
    case "Manually Triggered":
      return <ManualIcon fontSize="small" />;
    default:
      return <EventIcon fontSize="small" />;
  }
};

/**
 * Get the tooltip content for a trigger type
 */
const getTooltipContent = (type: string, eventRuleInfo?: EventRuleInfo) => {
  if (
    !eventRuleInfo ||
    !eventRuleInfo.eventRules ||
    eventRuleInfo.eventRules.length === 0
  ) {
    return type;
  }

  return (
    <Box sx={{ p: 1, maxWidth: 300 }}>
      <Typography variant="subtitle2" gutterBottom>
        {type}
      </Typography>
      {eventRuleInfo.eventRules.map((rule, index) => (
        <Box key={index} sx={{ mt: 1 }}>
          {rule.description && (
            <Typography variant="body2" color="text.secondary">
              {rule.description}
            </Typography>
          )}
          {rule.fileTypes && rule.fileTypes.length > 0 && (
            <Box sx={{ mt: 0.5, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
              {rule.fileTypes.map((fileType, i) => {
                const icon = getFileTypeIcon(fileType);
                return (
                  <Chip
                    key={i}
                    icon={icon}
                    label={fileType}
                    size="small"
                    variant="outlined"
                    sx={{ height: 20, "& .MuiChip-label": { px: 0.5 } }}
                  />
                );
              })}
            </Box>
          )}
          {rule.eventType && (
            <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
              Event: {rule.eventType}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  );
};

/**
 * Get the appropriate icon for a file type
 */
const getFileTypeIcon = (fileType: string) => {
  const videoFormats = ["MP4", "MOV", "AVI", "MKV", "WEBM"];
  const imageFormats = ["TIF", "JPG", "JPEG", "PNG", "WEBP", "GIF", "SVG"];
  const audioFormats = ["WAV", "AIFF", "AIF", "MP3", "PCM", "M4A"];

  if (videoFormats.includes(fileType)) {
    return <VideoIcon fontSize="small" />;
  } else if (imageFormats.includes(fileType)) {
    return <ImageIcon fontSize="small" />;
  } else if (audioFormats.includes(fileType)) {
    return <AudioIcon fontSize="small" />;
  } else {
    return <CodeIcon fontSize="small" />;
  }
};

/**
 * Get the appropriate color for a trigger type chip
 */
const getChipColor = (
  type: string,
): "primary" | "secondary" | "success" | "info" => {
  switch (type) {
    case "Event Triggered":
      return "primary";
    case "API Triggered":
      return "secondary";
    case "Manually Triggered":
      return "success";
    default:
      return "info";
  }
};

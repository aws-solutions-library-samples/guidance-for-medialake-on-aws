import React from "react";
import { Stack, Chip, Tooltip, Typography, Box } from "@mui/material";
import { Event as EventIcon, Api as ApiIcon, TouchApp as ManualIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();

  // If eventRuleInfo is not provided but pipeline is, extract the info from the pipeline
  const derivedEventRuleInfo = React.useMemo(() => {
    if (eventRuleInfo) {
      // Process the API-provided eventRuleInfo to fix descriptions
      return processEventRuleInfo(eventRuleInfo, pipeline);
    }
    if (!pipeline) {
      return undefined;
    }

    return extractEventRuleInfoFromPipeline(pipeline);
  }, [eventRuleInfo, pipeline]);

  return (
    <Stack direction="row" spacing={0.5} flexWrap="wrap">
      {triggerTypes.map((type, index) => {
        const icon = getTriggerIcon(type);
        const tooltipContent = getTooltipContent(type, derivedEventRuleInfo);

        // Translate the trigger type label
        const translatedLabel =
          type === "Event Triggered"
            ? t("integrations.triggerTypes.eventTriggered")
            : type === "API Triggered"
              ? t("integrations.triggerTypes.apiTriggered")
              : type === "Manually Triggered"
                ? t("integrations.triggerTypes.manuallyTriggered")
                : type;

        return (
          <Tooltip key={index} title={tooltipContent} arrow placement="top">
            <Chip icon={icon} label={translatedLabel} size="small" color={getChipColor(type)} />
          </Tooltip>
        );
      })}
    </Stack>
  );
};

/**
 * Process API-provided eventRuleInfo to fix descriptions
 */
const processEventRuleInfo = (eventRuleInfo: EventRuleInfo, pipeline?: Pipeline): EventRuleInfo => {
  const processed: EventRuleInfo = {
    ...eventRuleInfo,
    eventRules: eventRuleInfo.eventRules.map((rule) => {
      const ruleName = rule.ruleName || "";
      const ruleNameLower = ruleName.toLowerCase();
      const pipelineName = pipeline?.name || "";

      // Apply case-insensitive pattern matching to fix descriptions
      let newDescription = rule.description;
      let eventType = rule.eventType;

      if (
        ruleNameLower.includes("default-image-pipeline") ||
        pipelineName.includes("Image Pipeline")
      ) {
        newDescription = "Triggers on image files";
        eventType = "AssetCreated";
      } else if (
        ruleNameLower.includes("default-video-pipeline") ||
        pipelineName.includes("Video Pipeline")
      ) {
        newDescription = "Triggers on video files";
        eventType = "AssetCreated";
      } else if (
        ruleNameLower.includes("default-audio-pipeline") ||
        pipelineName.includes("Audio Pipeline")
      ) {
        newDescription = "Triggers on audio files";
        eventType = "AssetCreated";
      } else if (
        ruleNameLower.includes("pipeline_execution_completed") ||
        ruleNameLower.includes("pipeline_execut")
      ) {
        newDescription = "Triggers when another pipeline completes execution";
        eventType = "Pipeline Execution Completed";
      } else if (rule.description?.startsWith("Custom event rule:")) {
        // Remove the "Custom event rule:" prefix for unrecognized rules
        newDescription = undefined;
      }

      return {
        ...rule,
        description: newDescription,
        eventType: eventType || rule.eventType,
      };
    }),
  };

  return processed;
};

/**
 * Extract event rule information from a pipeline object
 */
const extractEventRuleInfoFromPipeline = (pipeline: Pipeline): EventRuleInfo => {
  const eventRuleInfo: EventRuleInfo = {
    triggerTypes: ["Event Triggered"],
    eventRules: [],
  };

  // Check for Event Triggered (EventBridge rules)
  if (pipeline.dependentResources) {
    for (const [resourceType, resourceValue] of pipeline.dependentResources) {
      if (resourceType === "eventbridge_rule") {
        const rule: EventRule = {};

        if (typeof resourceValue === "object" && resourceValue !== null) {
          rule.ruleName = resourceValue.rule_name || "";
          rule.eventBusName = resourceValue.eventbus_name || "";
        } else {
          // If it's just a string ARN, extract the rule name from the ARN
          rule.ruleArn = resourceValue as string;
          if (typeof resourceValue === "string" && resourceValue.includes("/")) {
            rule.ruleName = resourceValue.split("/").pop() || "";
          }
        }

        // Try to extract human-friendly information from the rule name
        if (rule.ruleName) {
          const ruleName = rule.ruleName;
          const ruleNameLower = ruleName.toLowerCase();

          // Check for default pipeline patterns (case-insensitive)
          if (
            ruleNameLower.includes("default-image-pipeline") ||
            pipeline.name.includes("Image Pipeline")
          ) {
            rule.description = "Triggers on image files";
            rule.eventType = "AssetCreated";
          } else if (
            ruleNameLower.includes("default-video-pipeline") ||
            pipeline.name.includes("Video Pipeline")
          ) {
            rule.description = "Triggers on video files";
            rule.eventType = "AssetCreated";
          } else if (
            ruleNameLower.includes("default-audio-pipeline") ||
            pipeline.name.includes("Audio Pipeline")
          ) {
            rule.description = "Triggers on audio files";
            rule.eventType = "AssetCreated";
          } else if (ruleNameLower.includes("pipeline_execution_completed")) {
            rule.description = "Triggers when another pipeline completes execution";
            rule.eventType = "Pipeline Execution Completed";
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
  // Normalize the type for comparison (case-insensitive and trim)
  const normalizedType = type.toLowerCase().trim();

  if (normalizedType.includes("event")) {
    return <EventIcon fontSize="small" />;
  } else if (normalizedType.includes("api")) {
    return <ApiIcon fontSize="small" />;
  } else if (normalizedType.includes("manual")) {
    return <ManualIcon fontSize="small" />;
  } else {
    return <EventIcon fontSize="small" />;
  }
};

/**
 * Get the tooltip content for a trigger type
 */
const getTooltipContent = (type: string, eventRuleInfo?: EventRuleInfo) => {
  if (!eventRuleInfo || !eventRuleInfo.eventRules || eventRuleInfo.eventRules.length === 0) {
    return type;
  }

  return (
    <Box sx={{ p: 1, maxWidth: 300 }}>
      <Typography variant="subtitle2" gutterBottom sx={{ color: "common.white" }}>
        {type}
      </Typography>
      {eventRuleInfo.eventRules.map((rule, index) => (
        <Box key={index} sx={{ mt: 1 }}>
          {rule.description && (
            <Typography variant="body2" sx={{ color: "rgba(255, 255, 255, 0.9)" }}>
              {rule.description}
            </Typography>
          )}
          {rule.fileTypes && rule.fileTypes.length > 0 && (
            <Box sx={{ mt: 0.5, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
              {rule.fileTypes.map((fileType, i) => (
                <Chip
                  key={i}
                  label={fileType}
                  size="small"
                  variant="outlined"
                  sx={{
                    height: 20,
                    "& .MuiChip-label": { px: 0.5, color: "common.white" },
                    borderColor: "rgba(255, 255, 255, 0.5)",
                  }}
                />
              ))}
            </Box>
          )}
          {rule.eventType && (
            <Typography
              variant="caption"
              display="block"
              sx={{ mt: 0.5, color: "rgba(255, 255, 255, 0.7)" }}
            >
              Event: {rule.eventType}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  );
};

/**
 * Get the appropriate color for a trigger type chip
 */
const getChipColor = (type: string): "primary" | "secondary" | "success" | "info" => {
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

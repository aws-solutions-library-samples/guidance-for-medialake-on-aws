import { FormDefinition } from "@/forms/types";

export const createIntegrationFormDefinition = (): FormDefinition => ({
  id: "integration-form",
  name: "Integration Form",
  translationPrefix: "integrations.form",
  fields: [
    {
      name: "nodeId",
      type: "text",
      label: "Integration",
      tooltip: "Select an integration provider",
      required: true,
      validation: {
        type: "string",
        rules: [
          {
            type: "min",
            value: 1,
            message: "Integration selection is required",
          },
        ],
      },
    },
    {
      name: "description",
      type: "text",
      label: "Description",
      tooltip: "Provide a description for this integration (optional)",
      required: false,
      multiline: true,
      rows: 3,
      validation: {
        type: "string",
        rules: [],
      },
    },
    {
      name: "auth.type",
      type: "select",
      label: "Authentication Type",
      tooltip: "Select the authentication method",
      required: true,
      options: [
        { label: "AWS IAM", value: "awsIam" },
        { label: "API Key", value: "apiKey" },
      ],
      defaultValue: "apiKey",
    },
    {
      name: "auth.credentials.apiKey",
      type: "password",
      label: "API Key",
      tooltip: "Enter your API key",
      required: true,
      validation: {
        type: "string",
        rules: [
          {
            type: "min",
            value: 1,
            message: "API Key is required",
          },
        ],
      },
      showWhen: {
        field: "auth.type",
        value: "apiKey",
      },
    },
  ],
});

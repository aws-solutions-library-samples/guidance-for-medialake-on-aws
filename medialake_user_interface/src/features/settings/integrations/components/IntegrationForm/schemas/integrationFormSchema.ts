import { z } from "zod";
import { createZodSchema } from "@/forms/utils/createZodSchema";
import { createIntegrationFormDefinition } from "@/features/settings/integrations/schemas/integrationFormDefinition";

// Create schema without environments
export const integrationFormSchema = createZodSchema(
  createIntegrationFormDefinition().fields,
);

export type IntegrationFormData = z.infer<typeof integrationFormSchema>;

export const createIntegrationFormDefaults = (): IntegrationFormData => ({
  nodeId: "",
  description: "",
  auth: {
    type: "apiKey",
    credentials: {},
  },
});

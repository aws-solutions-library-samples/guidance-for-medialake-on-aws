import { z } from "zod";

const integrationFormSchema = z.object({
  nodeId: z.string().min(1, "Node selection is required"),
  environmentId: z.string().min(1, "Environment selection is required"),
  description: z.string().min(1, "Description is required"),
  auth: z.object({
    type: z.enum(["awsIam", "apiKey"]),
    credentials: z.record(z.string()),
  }),
}) as z.ZodType<{
  nodeId: string;
  environmentId: string;
  description: string;
  auth: {
    type: "awsIam" | "apiKey";
    credentials: Record<string, string>;
  };
}>;

export type IntegrationFormData = z.infer<typeof integrationFormSchema>;

export { integrationFormSchema };

export const createIntegrationFormDefaults: IntegrationFormData = {
  nodeId: "",
  environmentId: "",
  description: "",
  auth: {
    type: "apiKey",
    credentials: {},
  },
};

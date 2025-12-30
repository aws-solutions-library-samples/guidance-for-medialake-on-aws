import { z } from "zod";

export const EnvironmentStatusValues = {
  Active: "active",
  Disabled: "disabled",
} as const;

export type EnvironmentStatus =
  (typeof EnvironmentStatusValues)[keyof typeof EnvironmentStatusValues];

export const environmentFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  region: z.string().min(1, "Region is required"),
  status: z.enum([EnvironmentStatusValues.Active, EnvironmentStatusValues.Disabled]),
  tags: z
    .object({
      "cost-center": z.string().min(1, "Cost center is required"),
      team: z.string().min(1, "Team is required"),
    })
    .and(z.record(z.string())),
});

export type EnvironmentFormData = z.infer<typeof environmentFormSchema>;

export const defaultEnvironmentFormData: EnvironmentFormData = {
  name: "",
  region: "us-west-2", // Default region
  status: EnvironmentStatusValues.Active,
  tags: {
    "cost-center": "",
    team: "default", // Default team
  },
};

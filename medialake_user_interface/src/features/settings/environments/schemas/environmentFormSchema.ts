import { z } from "zod";

export const EnvironmentStatus = {
  Active: "active",
  Disabled: "disabled",
} as const;

export type EnvironmentStatus =
  (typeof EnvironmentStatus)[keyof typeof EnvironmentStatus];

export const environmentFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  region: z.string().min(1, "Region is required"),
  status: z.enum([EnvironmentStatus.Active, EnvironmentStatus.Disabled]),
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
  status: EnvironmentStatus.Active,
  tags: {
    "cost-center": "",
    team: "default", // Default team
  },
};

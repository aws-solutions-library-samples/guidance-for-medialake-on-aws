import { z } from "zod";

export const userFormSchema = z.object({
  given_name: z.string().trim().min(1, "First name is required"),
  family_name: z.string().trim().min(1, "Last name is required"),
  email: z.string().trim().email("Invalid email format"),
  groups: z.string().default("editors"),
});

export type UserFormData = z.infer<typeof userFormSchema>;

export const createUserFormDefaults: UserFormData = {
  given_name: "",
  family_name: "",
  email: "",
  groups: "editors",
};

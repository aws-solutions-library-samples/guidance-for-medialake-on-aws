import { z } from 'zod';

const userFormSchema = z.object({
    given_name: z.string().min(1, 'First name is required'),
    family_name: z.string().min(1, 'Last name is required'),
    email: z.string().email('Invalid email format'),
    email_verified: z.boolean().default(false),
    roles: z.array(z.string()).min(1, 'At least one role is required'),
    enabled: z.boolean().default(true),
}) as z.ZodType<{
    given_name: string;
    family_name: string;
    email: string;
    email_verified: boolean;
    roles: string[];
    enabled: boolean;
}>;

export type UserFormData = z.infer<typeof userFormSchema>;

export { userFormSchema };

export const createUserFormDefaults: UserFormData = {
    given_name: '',
    family_name: '',
    email: '',
    email_verified: false,
    roles: [],
    enabled: true,
};

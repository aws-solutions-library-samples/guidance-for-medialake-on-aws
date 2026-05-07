export function formatCamelCase(input: string): string {
  // Step 1: Add space before any uppercase letter that follows a lowercase letter
  const spaced = input.replace(/([a-z])([A-Z])/g, "$1 $2");

  // Step 2: Capitalize the first letter of the entire string
  const capitalized = spaced.charAt(0).toUpperCase() + spaced.slice(1);

  return capitalized;
}

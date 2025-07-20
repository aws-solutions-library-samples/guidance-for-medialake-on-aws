// src/permissions/hooks/usePermission.ts
import { useCallback } from "react";
import { usePermissionContext } from "../context/permission-context";
import { globalPermissionCache } from "../utils/global-permission-cache";
import { Actions, Subjects } from "../types/ability.types";

/**
 * Hook for checking permissions in components
 *
 * @returns Object with can and cannot functions, loading state, and error
 */
export function usePermission() {
  const { ability, loading, error } = usePermissionContext();

  /**
   * Check if the user can perform an action on a subject
   *
   * @param action The action to check
   * @param subject The subject to check
   * @param field Optional field to check
   * @returns True if the user can perform the action, false otherwise
   */
  const can = useCallback(
    (action: Actions, subject: Subjects | any, field?: string) => {
      // Generate a cache key based on the parameters
      const subjectKey =
        typeof subject === "string" ? subject : JSON.stringify(subject);
      const cacheKey = `${action}:${subjectKey}:${field || ""}`;

      // Check global cache first for performance
      const cachedResult = globalPermissionCache.getPermissionCheck(cacheKey);
      if (cachedResult !== null) {
        return cachedResult;
      }

      // Perform the check and cache the result
      let result = false;
      try {
        result = ability.can(action, subject, field);

        // Cache the result in global cache
        globalPermissionCache.setPermissionCheck(cacheKey, result);
      } catch (error) {
        console.error("Error during permission check:", error);
        result = false;
        // Cache the failed result to avoid repeated errors
        globalPermissionCache.setPermissionCheck(cacheKey, result);
      }

      return result;
    },
    [ability, loading],
  );

  /**
   * Check if the user cannot perform an action on a subject
   *
   * @param action The action to check
   * @param subject The subject to check
   * @param field Optional field to check
   * @returns True if the user cannot perform the action, false otherwise
   */
  const cannot = useCallback(
    (action: Actions, subject: Subjects | any, field?: string) => {
      return !can(action, subject, field);
    },
    [can],
  );

  return { ability, can, cannot, loading, error };
}

/**
 * Hook for checking permissions on a specific subject
 *
 * @param subject The subject to check permissions on
 * @returns Object with can and cannot functions, loading state, and error
 */
export function useSubjectPermission(subject: any) {
  const { can, cannot, loading, error } = usePermission();

  /**
   * Check if the user can perform an action on the subject
   *
   * @param action The action to check
   * @param field Optional field to check
   * @returns True if the user can perform the action, false otherwise
   */
  const canOnSubject = useCallback(
    (action: Actions, field?: string) => {
      return can(action, subject, field);
    },
    [can, subject],
  );

  /**
   * Check if the user cannot perform an action on the subject
   *
   * @param action The action to check
   * @param field Optional field to check
   * @returns True if the user cannot perform the action, false otherwise
   */
  const cannotOnSubject = useCallback(
    (action: Actions, field?: string) => {
      return cannot(action, subject, field);
    },
    [cannot, subject],
  );

  return { can: canOnSubject, cannot: cannotOnSubject, loading, error };
}

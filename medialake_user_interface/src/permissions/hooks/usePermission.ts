// src/permissions/hooks/usePermission.ts
import { useCallback } from 'react';
import { usePermissionContext } from '../context/permission-context';
import { permissionCache } from '../utils/permission-cache';
import { Actions, Subjects } from '../types/ability.types';

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
  const can = useCallback((action: Actions, subject: Subjects | any, field?: string) => {
    // Generate a cache key based on the parameters
    const subjectKey = typeof subject === 'string' ? subject : JSON.stringify(subject);
    const cacheKey = `${action}:${subjectKey}:${field || ''}`;
    
    console.log('=== PERMISSION CHECK ===');
    console.log('usePermission.can called with:', { action, subject, field });
    console.log('Cache key:', cacheKey);
    console.log('Current ability:', ability);
    console.log('Ability rules count:', ability?.rules?.length || 0);
    console.log('Loading state:', loading);
    
    // Log some ability rules for debugging
    if (ability?.rules?.length > 0) {
      console.log('First few ability rules:', ability.rules.slice(0, 5));
    }
    
    // Check cache first for performance
    if (permissionCache.has(cacheKey)) {
      const cachedResult = permissionCache.get(cacheKey);
      console.log('Using cached result:', cachedResult);
      console.log('========================');
      return cachedResult;
    }
    
    // Perform the check and cache the result
    let result = false;
    try {
      result = ability.can(action, subject, field);
      console.log('Fresh permission check result:', result);
      
      // If the check failed, let's see why
      if (!result) {
        console.log('Permission DENIED. Debugging...');
        console.log('Checking if ability has any rules:', ability.rules.length);
        
        // Let's try some alternative checks to see what might work
        const alternativeChecks = [
          { action: 'view', subject: subject },
          { action: 'manage', subject: subject },
          { action: action, subject: 'all' },
          { action: 'manage', subject: 'all' }
        ];
        
        alternativeChecks.forEach(check => {
          try {
            const altResult = ability.can(check.action as Actions, check.subject as Subjects);
            console.log(`Alternative check ${check.action} on ${check.subject}:`, altResult);
          } catch (e) {
            console.log(`Alternative check ${check.action} on ${check.subject} failed:`, e);
          }
        });
        
        // Log all rules that might be relevant
        const relevantRules = ability.rules.filter(rule => 
          rule.subject === subject || 
          rule.subject === 'all' || 
          rule.action === action ||
          rule.action === 'manage'
        );
        console.log('Potentially relevant rules:', relevantRules);
      }
    } catch (error) {
      console.error('Error during permission check:', error);
      result = false;
    }
    
    console.log('Final permission result:', result);
    console.log('========================');
    
    permissionCache.set(cacheKey, result);
    return result;
  }, [ability, loading]);
  
  /**
   * Check if the user cannot perform an action on a subject
   * 
   * @param action The action to check
   * @param subject The subject to check
   * @param field Optional field to check
   * @returns True if the user cannot perform the action, false otherwise
   */
  const cannot = useCallback((action: Actions, subject: Subjects | any, field?: string) => {
    return !can(action, subject, field);
  }, [can]);
  
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
  const canOnSubject = useCallback((action: Actions, field?: string) => {
    return can(action, subject, field);
  }, [can, subject]);
  
  /**
   * Check if the user cannot perform an action on the subject
   * 
   * @param action The action to check
   * @param field Optional field to check
   * @returns True if the user cannot perform the action, false otherwise
   */
  const cannotOnSubject = useCallback((action: Actions, field?: string) => {
    return cannot(action, subject, field);
  }, [cannot, subject]);
  
  return { can: canOnSubject, cannot: cannotOnSubject, loading, error };
}
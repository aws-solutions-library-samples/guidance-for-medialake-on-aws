// src/permissions/types/ability.types.ts
import {
  Ability,
  AbilityBuilder,
  AbilityClass,
  MongoQuery,
  RawRuleOf,
} from "@casl/ability";

// Define the possible actions
export type Actions =
  | "view"
  | "edit"
  | "delete"
  | "create"
  | "upload"
  | "download"
  | "share"
  | "manage"
  | "run"
  | "add"
  | "disable";

// Define the possible subjects
export type Subjects =
  | "asset"
  | "pipeline"
  | "connector"
  | "user"
  | "group"
  | "settings"
  | "permission-set"
  | "integration"
  | "region"
  | "system-settings"
  | "all";

// Define the conditions type for subject-based authorization
export type Conditions = MongoQuery;

// Define the AppAbility type
export type AppAbility = Ability<[Actions, Subjects]>;

// Define the AppAbilityRule type
export type AppAbilityRule = RawRuleOf<AppAbility>;

// Define the AppAbilityBuilder type
export type AppAbilityBuilder = AbilityBuilder<AppAbility>;

// Define the createAppAbility function
export const createAppAbility = () => new Ability<[Actions, Subjects]>();

// Define the subject type for use in components and hooks
export type SubjectType = {
  type: Subjects;
  id?: string;
  [key: string]: any;
};

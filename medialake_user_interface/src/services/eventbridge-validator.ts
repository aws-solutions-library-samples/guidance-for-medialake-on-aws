export interface ValidationError {
  path: string;
  message: string;
  severity: "error" | "warning";
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
}

export class EventBridgePatternValidator {
  private static readonly MAX_PATTERN_SIZE = 2048;
  private static readonly MAX_NUMERIC_VALUE = 5.0e9;
  private static readonly MIN_NUMERIC_VALUE = -5.0e9;

  private static readonly VALID_ROOT_FIELDS = [
    "source",
    "detail-type",
    "detail",
    "account",
    "region",
    "time",
    "id",
    "resources",
  ];

  private static readonly VALID_OPERATORS = [
    "prefix",
    "suffix",
    "anything-but",
    "numeric",
    "exists",
    "cidr",
    "equals-ignore-case",
    "wildcard",
  ];

  static validate(pattern: Record<string, any>): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationError[] = [];

    if (!pattern || typeof pattern !== "object") {
      errors.push({
        path: "$",
        message: "Pattern must be a valid JSON object",
        severity: "error",
      });
      return { valid: false, errors, warnings };
    }

    const patternJson = JSON.stringify(pattern);
    if (patternJson.length > this.MAX_PATTERN_SIZE) {
      errors.push({
        path: "$",
        message: `Pattern size (${patternJson.length} bytes) exceeds ${this.MAX_PATTERN_SIZE} byte limit`,
        severity: "error",
      });
    }

    for (const field of Object.keys(pattern)) {
      if (!this.VALID_ROOT_FIELDS.includes(field)) {
        errors.push({
          path: field,
          message: `Invalid root field: ${field}. Valid fields are: ${this.VALID_ROOT_FIELDS.join(
            ", "
          )}`,
          severity: "error",
        });
      }
    }

    this.validateNode(pattern, "$", errors, warnings);

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }

  private static validateNode(
    node: any,
    path: string,
    errors: ValidationError[],
    warnings: ValidationError[]
  ): void {
    if (Array.isArray(node)) {
      node.forEach((item, index) => {
        this.validateArrayItem(item, `${path}[${index}]`, errors, warnings);
      });
    } else if (typeof node === "object" && node !== null) {
      for (const [key, value] of Object.entries(node)) {
        if (key === "$or") {
          this.validateOrOperator(value, `${path}.${key}`, errors, warnings);
        } else {
          this.validateNode(value, `${path}.${key}`, errors, warnings);
        }
      }
    }
  }

  private static validateArrayItem(
    item: any,
    path: string,
    errors: ValidationError[],
    warnings: ValidationError[]
  ): void {
    if (typeof item === "object" && item !== null && !Array.isArray(item)) {
      for (const [operator, value] of Object.entries(item)) {
        if (!this.VALID_OPERATORS.includes(operator)) {
          errors.push({
            path,
            message: `Unknown operator: ${operator}`,
            severity: "error",
          });
          continue;
        }

        switch (operator) {
          case "numeric":
            this.validateNumericOperator(value, path, errors);
            break;
          case "cidr":
            this.validateCidrOperator(value, path, errors);
            break;
          case "exists":
            this.validateExistsOperator(value, path, errors);
            break;
          case "wildcard":
            this.validateWildcardOperator(value, path, errors, warnings);
            break;
        }
      }
    }
  }

  private static validateNumericOperator(
    value: any,
    path: string,
    errors: ValidationError[]
  ): void {
    if (!Array.isArray(value)) {
      errors.push({
        path,
        message: "Numeric operator must be an array",
        severity: "error",
      });
      return;
    }

    const validOps = ["=", "!=", "<", "<=", ">", ">="];
    let i = 0;
    while (i < value.length) {
      const op = value[i];
      if (typeof op !== "string" || !validOps.includes(op)) {
        errors.push({
          path: `${path}[${i}]`,
          message: `Invalid numeric operator: ${op}. Valid operators: ${validOps.join(", ")}`,
          severity: "error",
        });
        break;
      }

      i++;
      if (i >= value.length) {
        errors.push({
          path,
          message: `Numeric operator ${op} missing value`,
          severity: "error",
        });
        break;
      }

      const num = value[i];
      if (typeof num !== "number") {
        errors.push({
          path: `${path}[${i}]`,
          message: `Numeric value must be a number, got: ${typeof num}`,
          severity: "error",
        });
        break;
      }

      if (num < this.MIN_NUMERIC_VALUE || num > this.MAX_NUMERIC_VALUE) {
        errors.push({
          path: `${path}[${i}]`,
          message: `Numeric value ${num} out of range [${this.MIN_NUMERIC_VALUE}, ${this.MAX_NUMERIC_VALUE}]`,
          severity: "error",
        });
      }

      i++;
    }
  }

  private static validateCidrOperator(value: any, path: string, errors: ValidationError[]): void {
    if (typeof value !== "string") {
      errors.push({
        path,
        message: "CIDR value must be a string",
        severity: "error",
      });
      return;
    }

    const cidrPattern =
      /^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$|^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}\/\d{1,3}$/;
    if (!cidrPattern.test(value)) {
      errors.push({
        path,
        message: `Invalid CIDR format: ${value}`,
        severity: "error",
      });
    }
  }

  private static validateExistsOperator(value: any, path: string, errors: ValidationError[]): void {
    if (typeof value !== "boolean") {
      errors.push({
        path,
        message: "Exists value must be true or false",
        severity: "error",
      });
    }
  }

  private static validateWildcardOperator(
    value: any,
    path: string,
    errors: ValidationError[],
    warnings: ValidationError[]
  ): void {
    if (typeof value !== "string" && !Array.isArray(value)) {
      errors.push({
        path,
        message: "Wildcard value must be a string or array of strings",
        severity: "error",
      });
      return;
    }

    if (Array.isArray(value)) {
      value.forEach((v, index) => {
        if (typeof v !== "string") {
          errors.push({
            path: `${path}[${index}]`,
            message: "Wildcard array values must be strings",
            severity: "error",
          });
        } else {
          this.validateWildcardPattern(v, `${path}[${index}]`, errors, warnings);
        }
      });
    } else {
      this.validateWildcardPattern(value, path, errors, warnings);
    }
  }

  private static validateWildcardPattern(
    pattern: string,
    path: string,
    errors: ValidationError[],
    warnings: ValidationError[]
  ): void {
    if (pattern.includes("**")) {
      errors.push({
        path,
        message: "Consecutive wildcard characters are not supported",
        severity: "error",
      });
    }

    const wildcardCount = (pattern.match(/\*/g) || []).length;
    if (wildcardCount > 3) {
      warnings.push({
        path,
        message: `Pattern contains ${wildcardCount} wildcards which may increase complexity`,
        severity: "warning",
      });
    }
  }

  private static validateOrOperator(
    value: any,
    path: string,
    errors: ValidationError[],
    warnings: ValidationError[]
  ): void {
    if (!Array.isArray(value)) {
      errors.push({
        path,
        message: "$or value must be an array",
        severity: "error",
      });
      return;
    }

    if (value.length === 0) {
      errors.push({
        path,
        message: "$or array cannot be empty",
        severity: "error",
      });
      return;
    }

    let totalCombinations = 1;
    const countOrArrays = (obj: any): number => {
      let count = 0;
      if (Array.isArray(obj)) {
        return obj.length;
      }
      if (typeof obj === "object" && obj !== null) {
        for (const value of Object.values(obj)) {
          if (Array.isArray(value) && value.length > 0) {
            count = Math.max(count, value.length);
          } else {
            count = Math.max(count, countOrArrays(value));
          }
        }
      }
      return Math.max(1, count);
    };

    value.forEach((condition, index) => {
      const combinations = countOrArrays(condition);
      totalCombinations *= combinations;
      this.validateNode(condition, `${path}[${index}]`, errors, warnings);
    });

    if (totalCombinations > 1000) {
      errors.push({
        path,
        message: `$or combinations (${totalCombinations}) exceed limit of 1000`,
        severity: "error",
      });
    } else if (totalCombinations > 500) {
      warnings.push({
        path,
        message: `$or combinations (${totalCombinations}) are high, consider simplifying`,
        severity: "warning",
      });
    }
  }
}

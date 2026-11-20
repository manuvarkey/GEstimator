import type { TemplateRow } from "./programSettings";
export interface AnalysisCondition { field: string; operator: string; value: string; value2?: string }
export interface AnalysisConditionGroup { mode: string; conditions: (AnalysisCondition | AnalysisConditionGroup)[] }
export interface AnalysisRule { match: AnalysisConditionGroup & { kind: string; occurrence: string; case_sensitive: boolean }; action: string; field: string; value: string; find: string; rows: TemplateRow[] }
export const analysisFields = [{ value: "description", label: "Description" }, { value: "code", label: "Code" }, { value: "value", label: "Quantity / factor" }, { value: "remarks", label: "Entry remarks" }];
const textOperators = [{ value: "contains", label: "Contains" }, { value: "not_contains", label: "Does not contain" }, { value: "equals", label: "Equals" }, { value: "not_equals", label: "Does not equal" }, { value: "starts_with", label: "Starts with" }, { value: "ends_with", label: "Ends with" }, { value: "glob", label: "Wildcard (*, ?)" }];
const numberOperators = [{ value: "numeric_eq", label: "Equals" }, { value: "numeric_ne", label: "Does not equal" }, { value: "gt", label: "Greater than" }, { value: "gte", label: "At least" }, { value: "lt", label: "Less than" }, { value: "lte", label: "At most" }, { value: "between", label: "Between (inclusive)" }];
export function analysisOperators(field: string) { return [...(field === "value" ? numberOperators : textOperators), { value: "is_empty", label: "Is empty" }, { value: "not_empty", label: "Is not empty" }]; }
export function isConditionGroup(value: AnalysisCondition | AnalysisConditionGroup): value is AnalysisConditionGroup { return "conditions" in value; }
export function conditionCount(group: AnalysisConditionGroup): number { return group.conditions.reduce((count, item) => count + 1 + (isConditionGroup(item) ? conditionCount(item) : 0), 0); }

package com.trustvision.dataset.validation;

import java.util.List;
import java.util.Map;

/** Structured outcome of the pre-analysis ZIP structure validation. */
public record ValidationReport(
        boolean valid,
        String declaredFormat,
        String detectedFormat,
        List<ValidationIssue> errors,
        List<ValidationIssue> warnings,
        Map<String, Object> stats
) {

    public record ValidationIssue(
            String type,
            String message,
            List<String> files,
            String suggestedFix
    ) {
    }
}

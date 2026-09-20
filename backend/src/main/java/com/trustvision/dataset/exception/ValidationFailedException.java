package com.trustvision.dataset.exception;

import com.trustvision.dataset.validation.ValidationReport;

/** Thrown when dataset upload validation fails — mapped to HTTP 422 with the full report. */
public class ValidationFailedException extends RuntimeException {

    private final transient ValidationReport report;

    public ValidationFailedException(ValidationReport report) {
        super("dataset validation failed with " + report.errors().size() + " error(s)");
        this.report = report;
    }

    public ValidationReport getReport() {
        return report;
    }
}

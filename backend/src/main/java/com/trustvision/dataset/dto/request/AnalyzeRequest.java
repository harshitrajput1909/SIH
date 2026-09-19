package com.trustvision.dataset.dto.request;

import jakarta.validation.constraints.NotNull;

import java.util.Map;
import java.util.UUID;

/**
 * Request to run the assurance pipeline for a stored dataset through the
 * AI engine. Options are passed through to the engine (e.g. folds, epochs,
 * near_dup_hamming) — see the engine README for the full list.
 */
public record AnalyzeRequest(
        @NotNull(message = "datasetId is required")
        UUID datasetId,
        Map<String, Object> options,
        Boolean force
) {
}

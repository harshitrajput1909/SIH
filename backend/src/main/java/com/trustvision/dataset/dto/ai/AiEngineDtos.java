package com.trustvision.dataset.dto.ai;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.PropertyNamingStrategies.SnakeCaseStrategy;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

import java.util.List;
import java.util.Map;

/**
 * DTOs mirroring the FastAPI Dataset Assurance Engine response
 * (snake_case JSON — see ai-engine/app/schemas.py).
 */
public final class AiEngineDtos {

    private AiEngineDtos() {
    }

    @JsonNaming(SnakeCaseStrategy.class)
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiJobAccepted(String jobId, String status, String pollUrl) {
    }

    @JsonNaming(SnakeCaseStrategy.class)
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiJobStatus(
            String jobId,
            String status,
            Double progress,
            String stage,
            String error,
            AiAssuranceResult result
    ) {
    }

    @JsonNaming(SnakeCaseStrategy.class)
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiAssuranceResult(
            String engineVersion,
            AiDatasetSummary dataset,
            List<AiCapability> capabilities,
            List<AiContributorRisk> contributorRiskScores,
            List<AiComponentScore> componentScores,
            Double trustScore,
            String riskLevel,
            Double confidence,
            List<String> limitations,
            String startedAt,
            String completedAt,
            Double durationSeconds
    ) {
    }

    @JsonNaming(SnakeCaseStrategy.class)
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiDatasetSummary(
            String name,
            String sourcePath,
            String format,
            Integer imagesTotal,
            Integer imagesAnalysed,
            Integer imagesCorrupted,
            Integer missingLabels,
            Integer classCount,
            List<String> classNames,
            Integer contributorCount,
            List<String> contributors
    ) {
    }

    @JsonNaming(SnakeCaseStrategy.class)
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiCapability(
            String capability,
            Boolean ran,
            String skipReason,
            List<AiFinding> findings
    ) {
    }

    @JsonNaming(SnakeCaseStrategy.class)
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiFinding(
            String findingId,
            String detector,
            String title,
            String description,
            String severity,
            Double confidence,
            Integer sampleCount,
            List<String> contributors,
            List<AiEvidence> evidence,
            Map<String, Object> detail
    ) {
    }

    @JsonNaming(SnakeCaseStrategy.class)
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiEvidence(
            String kind,
            List<String> imagePaths,
            String contributor,
            Map<String, Object> detail
    ) {
    }

    @JsonNaming(SnakeCaseStrategy.class)
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiContributorRisk(
            String contributor,
            Integer samples,
            Map<String, Double> rates,
            Double riskScore,
            String riskLevel,
            Double confidence,
            Boolean flagged
    ) {
    }

    @JsonNaming(SnakeCaseStrategy.class)
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AiComponentScore(String name, Double score, Double weight) {
    }
}

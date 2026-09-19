package com.trustvision.dataset.dto.response;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record DatasetAnalysisResponse(
        UUID id,
        UUID datasetId,
        String status,
        String engineJobId,
        Integer duplicatesCount,
        Integer floodCount,
        Integer labelFlipCount,
        Integer systematicMislabelCount,
        Integer triggerCount,
        Integer oodCount,
        BigDecimal trustScore,
        String riskLevel,
        List<ComponentScoreDto> componentScores,
        List<String> limitations,
        String resultSha256,
        String error,
        Instant startedAt,
        Instant completedAt,
        List<ContributorRiskResponse> contributorRisks,
        List<EvidenceResponse> evidence
) {
}

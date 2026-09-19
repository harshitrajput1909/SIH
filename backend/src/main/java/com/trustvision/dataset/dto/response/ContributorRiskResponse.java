package com.trustvision.dataset.dto.response;

import com.trustvision.dataset.domain.ContributorRisk;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record ContributorRiskResponse(
        UUID id,
        UUID analysisId,
        String contributor,
        int samplesContributed,
        BigDecimal riskScore,
        String riskLevel,
        boolean flagged,
        Instant assessedAt
) {

    public static ContributorRiskResponse from(ContributorRisk risk) {
        return new ContributorRiskResponse(
                risk.getId(),
                risk.getAnalysis() != null ? risk.getAnalysis().getId() : null,
                risk.getContributor() != null ? risk.getContributor().getName() : null,
                risk.getSamplesContributed(),
                risk.getRiskScore(),
                risk.getRiskLevel().name(),
                risk.isFlagged(),
                risk.getAssessedAt()
        );
    }
}

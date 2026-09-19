package com.trustvision.dataset.dto.response;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record ReportResponse(
        UUID id,
        String reportType,
        String format,
        String title,
        String subjectType,
        UUID subjectId,
        UUID datasetAnalysisId,
        BigDecimal trustScore,
        String riskLevel,
        String sha256,
        String artefactRef,
        Instant generatedAt,
        Object payload
) {
}

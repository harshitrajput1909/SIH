package com.trustvision.dataset.dto.response;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record EvidenceResponse(
        UUID id,
        UUID analysisId,
        String findingId,
        String detector,
        String title,
        String description,
        String severity,
        BigDecimal confidence,
        int sampleCount,
        List<String> contributors,
        List<String> imagePaths,
        Map<String, Object> detail,
        Instant createdAt
) {
}

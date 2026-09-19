package com.trustvision.dataset.dto.response;

import java.util.UUID;

public record DatasetDetailResponse(DatasetResponse dataset, DatasetAnalysisResponse latestAnalysis) {
}

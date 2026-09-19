package com.trustvision.dataset.dto.response;

import com.trustvision.dataset.domain.Dataset;

import java.time.Instant;
import java.util.UUID;

public record DatasetResponse(
        UUID id,
        String name,
        String codename,
        int version,
        String format,
        String classification,
        String state,
        String sha256,
        long sizeBytes,
        Integer imageCount,
        Integer classCount,
        String notes,
        Instant uploadedAt,
        UUID ownerId
) {

    public static DatasetResponse from(Dataset dataset) {
        return new DatasetResponse(
                dataset.getId(),
                dataset.getName(),
                dataset.getCodename(),
                dataset.getVersion(),
                dataset.getFormat().name(),
                dataset.getClassification().name(),
                dataset.getState().name(),
                dataset.getSha256(),
                dataset.getSizeBytes(),
                dataset.getImageCount(),
                dataset.getClassCount(),
                dataset.getNotes(),
                dataset.getUploadedAt(),
                dataset.getOwner() != null ? dataset.getOwner().getId() : null
        );
    }
}

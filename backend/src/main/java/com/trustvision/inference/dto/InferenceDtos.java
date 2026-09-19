package com.trustvision.inference.dto;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** DTOs for the inference verification flow (mirrors provenance-engine records). */
public final class InferenceDtos {

    private InferenceDtos() {
    }

    public record ProvenanceRecordDto(
            String recordId,
            String recordType,
            Instant timestamp,
            Map<String, Object> artifacts,
            String nonce,
            String prevHash,
            String verificationHash,
            Map<String, Object> signature
    ) {
    }

    public record VerificationResultDto(
            String recordId,
            Boolean valid,
            Map<String, Boolean> checks,
            Map<String, Object> details,
            String verifiedAt
    ) {
    }

    public record InferenceVerifyResponse(
            UUID requestId,
            String recordId,
            String verdict,
            ProvenanceRecordDto record,
            VerificationResultDto verification
    ) {
    }

    public record InferenceDetailResponse(
            UUID id,
            String imageSha256,
            String modelSha256,
            String configSha256,
            String outputSha256,
            String nonce,
            String recordId,
            Instant requestedAt,
            ProvenanceRecordDto provenance,
            List<VerificationResultDto> verifications
    ) {
    }

    public record EvidenceItemDto(
            String kind,
            String name,
            String algorithm,
            String value,
            Boolean passed,
            Map<String, Object> detail
    ) {
    }
}

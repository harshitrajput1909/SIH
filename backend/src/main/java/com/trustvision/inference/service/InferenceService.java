package com.trustvision.inference.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trustvision.dataset.config.AppProperties;
import com.trustvision.dataset.domain.User;
import com.trustvision.dataset.exception.AiEngineException;
import com.trustvision.dataset.exception.ResourceNotFoundException;
import com.trustvision.dataset.repository.UserRepository;
import com.trustvision.dataset.service.StorageService;
import com.trustvision.inference.domain.InferenceRequest;
import com.trustvision.inference.domain.InferenceVerification;
import com.trustvision.inference.domain.ProvenanceRecord;
import com.trustvision.inference.dto.InferenceDtos.EvidenceItemDto;
import com.trustvision.inference.dto.InferenceDtos.InferenceDetailResponse;
import com.trustvision.inference.dto.InferenceDtos.InferenceVerifyResponse;
import com.trustvision.inference.dto.InferenceDtos.ProvenanceRecordDto;
import com.trustvision.inference.dto.InferenceDtos.VerificationResultDto;
import com.trustvision.inference.exception.InvalidInferenceException;
import com.trustvision.inference.exception.VerificationRejectedException;
import com.trustvision.inference.repository.InferenceRequestRepository;
import com.trustvision.inference.repository.InferenceVerificationRepository;
import com.trustvision.inference.repository.ProvenanceRecordRepository;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Inference verification orchestration: store artifacts (hashing in-stream),
 * create the provenance record via the provenance engine, verify it, and
 * persist hashes / nonce / signature / verification results.
 */
@Service
public class InferenceService {

    private final InferenceRequestRepository requestRepository;
    private final InferenceVerificationRepository verificationRepository;
    private final ProvenanceRecordRepository provenanceRecordRepository;
    private final UserRepository userRepository;
    private final InferenceArtifactStore artifactStore;
    private final ProvenanceEngineClient provenanceEngineClient;
    private final ObjectMapper objectMapper;
    private final AppProperties properties;

    public InferenceService(
            InferenceRequestRepository requestRepository,
            InferenceVerificationRepository verificationRepository,
            ProvenanceRecordRepository provenanceRecordRepository,
            UserRepository userRepository,
            InferenceArtifactStore artifactStore,
            ProvenanceEngineClient provenanceEngineClient,
            ObjectMapper objectMapper,
            AppProperties properties
    ) {
        this.requestRepository = requestRepository;
        this.verificationRepository = verificationRepository;
        this.provenanceRecordRepository = provenanceRecordRepository;
        this.userRepository = userRepository;
        this.artifactStore = artifactStore;
        this.provenanceEngineClient = provenanceEngineClient;
        this.objectMapper = objectMapper;
        this.properties = properties;
    }

    public InferenceVerifyResponse verify(MultipartFile image, MultipartFile model,
                                          MultipartFile output, String configJson, String nonce) {
        validate(image, model);
        Map<String, Object> config = parseConfig(configJson);
        User actor = systemUser();

        InferenceRequest request = new InferenceRequest();
        request.setRequestedBy(actor);
        InferenceRequest saved = requestRepository.save(request);

        try {
            var imageFile = artifactStore.store(saved.getId(), "input_image", image);
            var modelFile = artifactStore.store(saved.getId(), "model", model);
            var outputFile = (output != null && !output.isEmpty())
                    ? artifactStore.store(saved.getId(), "output", output)
                    : null;

            Map<String, Object> record = provenanceEngineClient.createRecord(
                    Path.of(imageFile.absolutePath()),
                    Path.of(modelFile.absolutePath()),
                    outputFile != null ? Path.of(outputFile.absolutePath()) : null,
                    config,
                    nonce
            );

            applyRecord(saved, record, imageFile, modelFile, outputFile);
            requestRepository.save(saved);

            Map<String, Object> verification = provenanceEngineClient.verify(record.get("record_id").toString());
            InferenceVerification stored = persistVerification(saved, verification, actor);

            ProvenanceRecordDto recordDto = provenanceRecordRepository
                    .findByRecordId(saved.getRecordId())
                    .map(this::toRecordDto)
                    .orElseGet(() -> toRecordDto(record));

            return new InferenceVerifyResponse(
                    saved.getId(),
                    saved.getRecordId(),
                    stored.isValid() ? "VERIFIED" : "REJECTED",
                    recordDto,
                    toVerificationDto(stored)
            );
        } catch (IOException | AiEngineException | VerificationRejectedException e) {
            requestRepository.delete(saved);   // nothing entered the chain — drop the placeholder
            if (e instanceof VerificationRejectedException rejected) {
                throw rejected;
            }
            if (e instanceof AiEngineException engineError) {
                throw engineError;
            }
            throw new InvalidInferenceException("could not store verification artifacts: " + e.getMessage());
        }
    }

    public InferenceDetailResponse get(UUID id) {
        InferenceRequest request = requestRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("inference request", id));
        ProvenanceRecordDto record = provenanceRecordRepository
                .findTopByRequestIdOrderByCreatedAtDesc(id)
                .map(this::toRecordDto)
                .orElse(null);
        List<VerificationResultDto> verifications = verificationRepository
                .findByRequestIdOrderByVerifiedAtDesc(id).stream()
                .map(this::toVerificationDto)
                .toList();
        return new InferenceDetailResponse(
                request.getId(),
                request.getImageSha256(),
                request.getModelSha256(),
                request.getConfigSha256(),
                request.getOutputSha256(),
                request.getNonce(),
                request.getRecordId(),
                request.getRequestedAt(),
                record,
                verifications
        );
    }

    public ProvenanceRecordDto provenance(UUID requestId) {
        if (!requestRepository.existsById(requestId)) {
            throw new ResourceNotFoundException("inference request", requestId);
        }
        return provenanceRecordRepository.findTopByRequestIdOrderByCreatedAtDesc(requestId)
                .map(this::toRecordDto)
                .orElseThrow(() -> new ResourceNotFoundException("provenance record", requestId));
    }

    public List<EvidenceItemDto> evidence(UUID requestId) {
        InferenceRequest request = requestRepository.findById(requestId)
                .orElseThrow(() -> new ResourceNotFoundException("inference request", requestId));
        ProvenanceRecordDto record = provenanceRecordRepository
                .findTopByRequestIdOrderByCreatedAtDesc(requestId)
                .map(this::toRecordDto)
                .orElseThrow(() -> new ResourceNotFoundException("provenance record", requestId));
        VerificationResultDto verification = verificationRepository
                .findByRequestIdOrderByVerifiedAtDesc(requestId).stream()
                .findFirst()
                .map(this::toVerificationDto)
                .orElse(null);

        List<EvidenceItemDto> items = new ArrayList<>();
        if (record.artifacts() != null) {
            record.artifacts().forEach((artifactName, commitment) -> {
                if (commitment instanceof Map<?, ?> committed && committed.get("sha256") != null) {
                    Map<String, Object> detail = new java.util.HashMap<>();
                    Object filename = committed.get("filename");
                    detail.put("filename", filename == null ? "" : String.valueOf(filename));
                    items.add(new EvidenceItemDto(
                            "hash_commitment", artifactName, "SHA-256",
                            String.valueOf(committed.get("sha256")), null, detail));
                }
            });
        }
        items.add(new EvidenceItemDto("nonce", "verification nonce", null, record.nonce(), null, Map.of()));
        items.add(new EvidenceItemDto("timestamp", "record timestamp", null,
                record.timestamp() == null ? null : record.timestamp().toString(), null, Map.of()));
        if (record.signature() != null) {
            items.add(new EvidenceItemDto("signature", "digital signature", "Ed25519",
                    String.valueOf(record.signature().get("value")), null,
                    Map.of("key_id", String.valueOf(record.signature().get("key_id")))));
        }
        items.add(new EvidenceItemDto("chain", "verification hash", "SHA-256",
                record.verificationHash(), null, Map.of("prev_hash", String.valueOf(record.prevHash()))));

        if (verification != null && verification.checks() != null) {
            verification.checks().forEach((name, passed) -> items.add(new EvidenceItemDto(
                    "integrity_check", name, null, Boolean.TRUE.equals(passed) ? "PASSED" : "FAILED",
                    passed, Map.of())));
        }
        return items;
    }

    // ------------------------------------------------------------------
    // helpers
    // ------------------------------------------------------------------

    private void applyRecord(InferenceRequest request, Map<String, Object> record,
                             StorageService.StoredFile imageFile, StorageService.StoredFile modelFile,
                             StorageService.StoredFile outputFile) {
        request.setImageRef(imageFile.absolutePath());
        request.setImageSha256(imageFile.sha256());
        request.setModelRef(modelFile.absolutePath());
        request.setModelSha256(modelFile.sha256());
        if (outputFile != null) {
            request.setOutputRef(outputFile.absolutePath());
            request.setOutputSha256(outputFile.sha256());
        }
        if (record.get("nonce") != null) {
            request.setNonce(record.get("nonce").toString());
        }
        if (record.get("record_id") != null) {
            request.setRecordId(record.get("record_id").toString());
        }
        if (record.get("artifacts") instanceof Map<?, ?> artifacts
                && artifacts.get("config") instanceof Map<?, ?> configArtifact
                && configArtifact.get("sha256") != null) {
            request.setConfigSha256(configArtifact.get("sha256").toString());
        }
    }

    private InferenceVerification persistVerification(InferenceRequest request,
                                                      Map<String, Object> verification, User actor) {
        InferenceVerification row = new InferenceVerification();
        row.setRequest(request);
        row.setRecordId(request.getRecordId());
        row.setValid(Boolean.TRUE.equals(verification.get("valid")));
        row.setChecks(toJson(verification.getOrDefault("checks", Map.of())));
        row.setDetails(toJson(verification.getOrDefault("details", Map.of())));
        row.setVerifiedBy(actor);
        return verificationRepository.save(row);
    }

    private void validate(MultipartFile image, MultipartFile model) {
        if (image == null || image.isEmpty()) {
            throw new InvalidInferenceException("image artifact is required");
        }
        if (model == null || model.isEmpty()) {
            throw new InvalidInferenceException("model artifact is required");
        }
    }

    private User systemUser() {
        return userRepository.findByUsername(properties.ownerUsername())
                .orElseThrow(() -> new IllegalStateException("seeded system user missing"));
    }

    private Map<String, Object> parseConfig(String configJson) {
        if (configJson == null || configJson.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(configJson, new TypeReference<Map<String, Object>>() {
            });
        } catch (IOException e) {
            throw new InvalidInferenceException("invalid config JSON: " + e.getMessage());
        }
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (IOException e) {
            throw new IllegalStateException("JSON serialization failed", e);
        }
    }

    private <T> T fromJson(String json, Class<T> type) {
        if (json == null || json.isBlank()) {
            return null;
        }
        try {
            return objectMapper.readValue(json, type);
        } catch (IOException e) {
            throw new IllegalStateException("JSON deserialization failed", e);
        }
    }

    private <T> T fromJson(String json, TypeReference<T> type) {
        if (json == null || json.isBlank()) {
            return null;
        }
        try {
            return objectMapper.readValue(json, type);
        } catch (IOException e) {
            throw new IllegalStateException("JSON deserialization failed", e);
        }
    }

    private String str(Map<String, Object> values, String key) {
        if (values == null || key == null) {
            return null;
        }
        Object value = values.get(key);
        return value == null ? null : String.valueOf(value);
    }

    @SuppressWarnings("unchecked")
    private ProvenanceRecordDto toRecordDto(ProvenanceRecord entity) {
        return new ProvenanceRecordDto(
                entity.getRecordId(),
                entity.getRecordType(),
                entity.getRecordTimestamp(),
                fromJson(entity.getArtifacts(), Map.class),
                entity.getNonce(),
                entity.getPrevHash(),
                entity.getVerificationHash(),
                fromJson(entity.getSignature(), Map.class)
        );
    }

    @SuppressWarnings("unchecked")
    private ProvenanceRecordDto toRecordDto(Map<String, Object> record) {
        String timestamp = str(record, "timestamp");
        return new ProvenanceRecordDto(
                str(record, "record_id"),
                str(record, "record_type"),
                timestamp != null ? Instant.parse(timestamp) : null,
                (Map<String, Object>) record.get("artifacts"),
                str(record, "nonce"),
                str(record, "prev_hash"),
                str(record, "verification_hash"),
                (Map<String, Object>) record.get("signature")
        );
    }

    @SuppressWarnings("unchecked")
    private VerificationResultDto toVerificationDto(InferenceVerification entity) {
        return new VerificationResultDto(
                entity.getRecordId(),
                entity.isValid(),
                fromJson(entity.getChecks(), new TypeReference<Map<String, Boolean>>() {
                }),
                fromJson(entity.getDetails(), new TypeReference<Map<String, Object>>() {
                }),
                entity.getVerifiedAt().toString()
        );
    }

    @SuppressWarnings("unchecked")
    private VerificationResultDto toVerificationDto(Map<String, Object> verification) {
        return new VerificationResultDto(
                str(verification, "record_id"),
                (Boolean) verification.get("valid"),
                (Map<String, Boolean>) verification.getOrDefault("checks", Map.of()),
                (Map<String, Object>) verification.getOrDefault("details", Map.of()),
                str(verification, "verified_at")
        );
    }
}

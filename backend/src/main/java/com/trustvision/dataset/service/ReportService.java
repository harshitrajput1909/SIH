package com.trustvision.dataset.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.trustvision.dataset.config.AppProperties;
import com.trustvision.dataset.domain.AssuranceReport;
import com.trustvision.dataset.domain.Dataset;
import com.trustvision.dataset.domain.DatasetAnalysis;
import com.trustvision.dataset.domain.JobStatus;
import com.trustvision.dataset.domain.ProvenanceSubject;
import com.trustvision.dataset.domain.ReportType;
import com.trustvision.dataset.domain.User;
import com.trustvision.dataset.dto.response.ReportResponse;
import com.trustvision.dataset.exception.InvalidDatasetException;
import com.trustvision.dataset.exception.ResourceNotFoundException;
import com.trustvision.dataset.repository.AssuranceReportRepository;
import com.trustvision.dataset.repository.ContributorRiskRepository;
import com.trustvision.dataset.repository.DatasetAnalysisRepository;
import com.trustvision.dataset.repository.DatasetEvidenceRepository;
import com.trustvision.dataset.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.DigestUtils;

import java.nio.file.Files;
import java.nio.file.Path;
import java.io.IOException;
import java.time.Instant;
import java.util.UUID;

/**
 * Builds (once) and serves the assurance report of a completed analysis.
 * The report payload is stored as a JSON artefact with its SHA-256 recorded
 * for cryptographic provenance; PDF rendering arrives with the reports module.
 */
@Service
public class ReportService {

    private static final Logger log = LoggerFactory.getLogger(ReportService.class);

    private final DatasetAnalysisRepository analysisRepository;
    private final AssuranceReportRepository reportRepository;
    private final ContributorRiskRepository contributorRiskRepository;
    private final DatasetEvidenceRepository evidenceRepository;
    private final UserRepository userRepository;
    private final StorageService storageService;
    private final ObjectMapper objectMapper;
    private final AppProperties properties;

    public ReportService(
            DatasetAnalysisRepository analysisRepository,
            AssuranceReportRepository reportRepository,
            ContributorRiskRepository contributorRiskRepository,
            DatasetEvidenceRepository evidenceRepository,
            UserRepository userRepository,
            StorageService storageService,
            ObjectMapper objectMapper,
            AppProperties properties
    ) {
        this.analysisRepository = analysisRepository;
        this.reportRepository = reportRepository;
        this.contributorRiskRepository = contributorRiskRepository;
        this.evidenceRepository = evidenceRepository;
        this.userRepository = userRepository;
        this.storageService = storageService;
        this.objectMapper = objectMapper;
        this.properties = properties;
    }

    public ReportResponse getOrGenerate(UUID analysisId) {
        DatasetAnalysis analysis = analysisRepository.findById(analysisId)
                .orElseThrow(() -> new ResourceNotFoundException("analysis", analysisId));
        if (analysis.getStatus() != JobStatus.COMPLETED) {
            throw new InvalidDatasetException(
                    "analysis " + analysisId + " has not completed (status " + analysis.getStatus() + ")");
        }
        AssuranceReport report = reportRepository
                .findFirstByDatasetAnalysisIdOrderByGeneratedAtDesc(analysisId)
                .orElseGet(() -> generate(analysis));
        return toResponse(report);
    }

    private AssuranceReport generate(DatasetAnalysis analysis) {
        User actor = userRepository.findByUsername(properties.ownerUsername())
                .orElseThrow(() -> new IllegalStateException("seeded system user missing"));
        Dataset dataset = analysis.getDataset();

        ObjectNode payload = objectMapper.createObjectNode();
        payload.put("report_type", ReportType.ASSESSMENT.name());
        payload.put("generated_at", Instant.now().toString());
        payload.put("dataset_id", dataset.getId().toString());
        payload.put("dataset_name", dataset.getName());
        payload.put("dataset_version", dataset.getVersion());
        payload.put("analysis_id", analysis.getId().toString());
        payload.put("trust_score", analysis.getTrustScore());
        payload.put("risk_level", analysis.getRiskLevel() != null ? analysis.getRiskLevel().name() : null);
        payload.set("analysis_result", parseJson(analysis.getResultJson()));

        ArrayNode risks = payload.putArray("contributor_risks");
        contributorRiskRepository.findByAnalysis_IdOrderByRiskScoreDesc(analysis.getId())
                .forEach(risk -> {
                    ObjectNode node = risks.addObject();
                    node.put("contributor", risk.getContributor().getName());
                    node.put("samples", risk.getSamplesContributed());
                    node.put("risk_score", risk.getRiskScore());
                    node.put("risk_level", risk.getRiskLevel().name());
                    node.put("flagged", risk.isFlagged());
                });

        ArrayNode evidence = payload.putArray("evidence");
        evidenceRepository.findByAnalysis_IdOrderByCreatedAtAsc(analysis.getId())
                .forEach(row -> {
                    ObjectNode node = evidence.addObject();
                    node.put("finding_id", row.getFindingId());
                    node.put("detector", row.getDetector());
                    node.put("title", row.getTitle());
                    node.put("severity", row.getSeverity().name());
                    node.put("confidence", row.getConfidence());
                    node.put("sample_count", row.getSampleCount());
                    ArrayNode paths = node.putArray("image_paths");
                    row.getImagePaths().forEach(paths::add);
                });

        byte[] bytes = serialize(payload);
        String sha256 = Sha256.hex(bytes);
        Path artefactRef;
        try {
            artefactRef = storageService.storeReport(analysis.getId(), bytes);
        } catch (IOException e) {
            throw new IllegalStateException("could not store report artefact", e);
        }

        AssuranceReport report = new AssuranceReport();
        report.setTitle("Dataset Assurance Report — " + dataset.getName() + " (" + analysis.getId() + ")");
        report.setDatasetAnalysisId(analysis.getId());
        report.setSubjectType(ProvenanceSubject.DATASET);
        report.setSubjectId(dataset.getId());
        report.setTrustScore(analysis.getTrustScore());
        report.setRiskLevel(analysis.getRiskLevel());
        report.setArtefactRef(artefactRef.toString());
        report.setSha256(sha256);
        report.setGeneratedBy(actor);
        AssuranceReport saved = reportRepository.save(report);
        log.info("generated assurance report {} for analysis {}", saved.getId(), analysis.getId());
        return saved;
    }

    private ReportResponse toResponse(AssuranceReport report) {
        JsonNode payload = null;
        try {
            payload = objectMapper.readTree(Files.readString(Path.of(report.getArtefactRef())));
        } catch (Exception e) {
            log.warn("report artefact unreadable: {}", report.getArtefactRef());
        }
        return new ReportResponse(
                report.getId(),
                report.getReportType().name(),
                report.getFormat().name(),
                report.getTitle(),
                report.getSubjectType().name(),
                report.getSubjectId(),
                report.getDatasetAnalysisId(),
                report.getTrustScore(),
                report.getRiskLevel() != null ? report.getRiskLevel().name() : null,
                report.getSha256(),
                report.getArtefactRef(),
                report.getGeneratedAt(),
                payload
        );
    }

    private JsonNode parseJson(String json) {
        if (json == null || json.isBlank()) {
            return objectMapper.nullNode();
        }
        try {
            return objectMapper.readTree(json);
        } catch (Exception e) {
            log.warn("stored JSON could not be parsed: {}", e.getMessage());
            return objectMapper.nullNode();
        }
    }

    private byte[] serialize(ObjectNode payload) {
        try {
            return objectMapper.writeValueAsBytes(payload);
        } catch (Exception e) {
            throw new IllegalStateException("report serialisation failed", e);
        }
    }
}

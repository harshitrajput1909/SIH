package com.trustvision.dataset.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trustvision.dataset.config.AppProperties;
import com.trustvision.dataset.domain.ClassificationLevel;
import com.trustvision.dataset.domain.Contributor;
import com.trustvision.dataset.domain.ContributorRisk;
import com.trustvision.dataset.domain.Dataset;
import com.trustvision.dataset.domain.DatasetAnalysis;
import com.trustvision.dataset.domain.DatasetEvidence;
import com.trustvision.dataset.domain.DatasetFormat;
import com.trustvision.dataset.domain.DatasetState;
import com.trustvision.dataset.domain.JobStatus;
import com.trustvision.dataset.domain.RiskLevel;
import com.trustvision.dataset.domain.User;
import com.trustvision.dataset.dto.ai.AiEngineDtos.AiAssuranceResult;
import com.trustvision.dataset.dto.ai.AiEngineDtos.AiCapability;
import com.trustvision.dataset.dto.ai.AiEngineDtos.AiContributorRisk;
import com.trustvision.dataset.dto.ai.AiEngineDtos.AiFinding;
import com.trustvision.dataset.dto.request.AnalyzeRequest;
import com.trustvision.dataset.dto.response.ComponentScoreDto;
import com.trustvision.dataset.dto.response.ContributorRiskResponse;
import com.trustvision.dataset.dto.response.DatasetAnalysisResponse;
import com.trustvision.dataset.dto.response.DatasetDetailResponse;
import com.trustvision.dataset.dto.response.DatasetResponse;
import com.trustvision.dataset.dto.response.EvidenceResponse;
import com.trustvision.dataset.exception.AiEngineException;
import com.trustvision.dataset.exception.InvalidDatasetException;
import com.trustvision.dataset.exception.ResourceNotFoundException;
import com.trustvision.dataset.repository.ContributorRepository;
import com.trustvision.dataset.repository.ContributorRiskRepository;
import com.trustvision.dataset.repository.DatasetAnalysisRepository;
import com.trustvision.dataset.repository.DatasetEvidenceRepository;
import com.trustvision.dataset.repository.DatasetRepository;
import com.trustvision.dataset.repository.UserRepository;
import com.trustvision.dataset.service.StorageService.StoredFile;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.util.DigestUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

@Service
public class DatasetService {

    private static final String CAP_DUPLICATES = "duplicate_detection";
    private static final String CAP_FLOODING = "near_duplicate_flooding";
    private static final String CAP_LABEL_FLIP = "label_flip_detection";
    private static final String CAP_MISLABEL = "systematic_mislabelling";
    private static final String CAP_TRIGGER = "trigger_injection";
    private static final String CAP_OOD = "ood_detection";

    private final DatasetRepository datasetRepository;
    private final DatasetAnalysisRepository analysisRepository;
    private final ContributorRepository contributorRepository;
    private final ContributorRiskRepository contributorRiskRepository;
    private final DatasetEvidenceRepository evidenceRepository;
    private final UserRepository userRepository;
    private final StorageService storageService;
    private final AiEngineClient aiEngineClient;
    private final ObjectMapper objectMapper;
    private final TransactionTemplate tx;
    private final AppProperties properties;

    public DatasetService(
            DatasetRepository datasetRepository,
            DatasetAnalysisRepository analysisRepository,
            ContributorRepository contributorRepository,
            ContributorRiskRepository contributorRiskRepository,
            DatasetEvidenceRepository evidenceRepository,
            UserRepository userRepository,
            StorageService storageService,
            AiEngineClient aiEngineClient,
            ObjectMapper objectMapper,
            PlatformTransactionManager transactionManager,
            AppProperties properties
    ) {
        this.datasetRepository = datasetRepository;
        this.analysisRepository = analysisRepository;
        this.contributorRepository = contributorRepository;
        this.contributorRiskRepository = contributorRiskRepository;
        this.evidenceRepository = evidenceRepository;
        this.userRepository = userRepository;
        this.storageService = storageService;
        this.aiEngineClient = aiEngineClient;
        this.objectMapper = objectMapper;
        this.tx = new TransactionTemplate(transactionManager);
        this.properties = properties;
    }

    // ------------------------------------------------------------------
    // POST /dataset/upload
    // ------------------------------------------------------------------

    public DatasetResponse upload(MultipartFile file, String name, String codename,
                                  String format, String classification, String notes) {
        if (file == null || file.isEmpty()) {
            throw new InvalidDatasetException("uploaded file is empty");
        }
        String original = file.getOriginalFilename();
        if (original == null || !original.toLowerCase().endsWith(".zip")) {
            throw new InvalidDatasetException("dataset upload must be a .zip archive (COCO or YOLO layout)");
        }
        User owner = systemUser();
        Dataset dataset = new Dataset();
        dataset.setName(name);
        dataset.setCodename(codename);
        dataset.setFormat(DatasetFormat.valueOf(format.trim().toUpperCase()));
        if (classification != null && !classification.isBlank()) {
            dataset.setClassification(parseClassification(classification));
        }
        dataset.setOwner(owner);
        dataset.setNotes(notes);
        dataset = datasetRepository.save(dataset);

        StoredFile stored;
        try {
            stored = storageService.storeDatasetArtefact(dataset.getId(), file);
        } catch (IOException e) {
            datasetRepository.delete(dataset);
            throw new InvalidDatasetException("could not store uploaded dataset: " + e.getMessage());
        }
        dataset.setArtefactRef(stored.absolutePath());
        dataset.setSha256(stored.sha256());
        dataset.setSizeBytes(stored.sizeBytes());
        return DatasetResponse.from(datasetRepository.save(dataset));
    }

    // ------------------------------------------------------------------
    // POST /dataset/analyze
    // ------------------------------------------------------------------

    public DatasetAnalysisResponse analyze(AnalyzeRequest request) {
        Dataset dataset = datasetRepository.findById(request.datasetId())
                .orElseThrow(() -> new ResourceNotFoundException("dataset", request.datasetId()));
        if (dataset.getState() == DatasetState.ANALYSING) {
            throw new InvalidDatasetException("an analysis is already running for this dataset");
        }
        User actor = systemUser();

        DatasetAnalysis analysis = new DatasetAnalysis();
        analysis.setDataset(dataset);
        analysis.setStatus(JobStatus.QUEUED);
        analysis.setRequestedBy(actor);
        analysis.setStartedAt(Instant.now());
        DatasetAnalysis saved = analysisRepository.save(analysis);

        dataset.setState(DatasetState.ANALYSING);
        datasetRepository.save(dataset);

        try {
            String jobId = aiEngineClient.submitJob(
                    Path.of(dataset.getArtefactRef()),
                    dataset.getFormat().name(),
                    request.options());
            saved.setEngineJobId(jobId);
            saved.setStatus(JobStatus.RUNNING);
            analysisRepository.save(saved);

            AiAssuranceResult result = aiEngineClient.awaitResult(jobId);

            DatasetAnalysis completed = tx.execute(s -> {
                persistResult(saved, dataset, result);
                return analysisRepository.findById(saved.getId()).orElse(saved);
            });
            return toResponse(Objects.requireNonNull(completed), true);
        } catch (AiEngineException | IllegalStateException e) {
            tx.executeWithoutResult(s -> {
                saved.setStatus(JobStatus.FAILED);
                saved.setError(e.getMessage());
                analysisRepository.save(saved);
                dataset.setState(DatasetState.UPLOADED);
                datasetRepository.save(dataset);
            });
            if (e instanceof AiEngineException engineError) {
                throw engineError;
            }
            throw new AiEngineException("analysis failed while persisting results: " + e.getMessage(), e);
        }
    }

    // ------------------------------------------------------------------
    // GET /dataset/{id}
    // ------------------------------------------------------------------

    public DatasetDetailResponse get(UUID id) {
        Dataset dataset = datasetRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("dataset", id));
        DatasetAnalysisResponse latest = analysisRepository
                .findTopByDatasetIdOrderByCreatedAtDesc(id)
                .map(analysis -> toResponse(analysis, true))
                .orElse(null);
        return new DatasetDetailResponse(DatasetResponse.from(dataset), latest);
    }

    // ------------------------------------------------------------------
    // GET /dataset/evidence/{analysisId}
    // ------------------------------------------------------------------

    public List<EvidenceResponse> evidence(UUID analysisId) {
        if (!analysisRepository.existsById(analysisId)) {
            throw new ResourceNotFoundException("analysis", analysisId);
        }
        return evidenceRepository.findByAnalysis_IdOrderByCreatedAtAsc(analysisId).stream()
                .map(this::toEvidenceResponse)
                .toList();
    }

    // ------------------------------------------------------------------
    // helpers
    // ------------------------------------------------------------------

    private void persistResult(DatasetAnalysis analysis, Dataset dataset, AiAssuranceResult result) {
        analysis.setStatus(JobStatus.COMPLETED);
        analysis.setCompletedAt(Instant.now());
        analysis.setDuplicatesCount(countByCapability(result, CAP_DUPLICATES));
        analysis.setFloodCount(countByCapability(result, CAP_FLOODING));
        analysis.setLabelFlipCount(countByCapability(result, CAP_LABEL_FLIP));
        analysis.setSystematicMislabelCount(countByCapability(result, CAP_MISLABEL));
        analysis.setTriggerCount(countByCapability(result, CAP_TRIGGER));
        analysis.setOodCount(countByCapability(result, CAP_OOD));
        if (result.trustScore() != null) {
            analysis.setTrustScore(BigDecimal.valueOf(result.trustScore()));
        }
        if (result.riskLevel() != null) {
            analysis.setRiskLevel(RiskLevel.valueOf(result.riskLevel()));
        }
        analysis.setComponentScores(toJson(result.componentScores()));
        analysis.setLimitations(toJson(result.limitations()));
        String resultJson = toJson(result);
        analysis.setResultJson(resultJson);
        analysis.setResultSha256(Sha256.hex(resultJson));
        if (result.dataset() != null) {
            dataset.setImageCount(result.dataset().imagesTotal());
            dataset.setClassCount(result.dataset().classCount());
        }
        analysisRepository.save(analysis);
        datasetRepository.save(dataset);

        if (result.contributorRiskScores() != null) {
            for (AiContributorRisk risk : result.contributorRiskScores()) {
                Contributor contributor = contributorRepository.findByNameIgnoreCase(risk.contributor())
                        .orElseGet(() -> {
                            Contributor created = new Contributor();
                            created.setName(risk.contributor());
                            return contributorRepository.save(created);
                        });
                ContributorRisk row = new ContributorRisk();
                row.setAnalysis(analysis);
                row.setContributor(contributor);
                row.setSamplesContributed(risk.samples() != null ? risk.samples() : 0);
                row.setRiskScore(BigDecimal.valueOf(risk.riskScore()));
                row.setRiskLevel(RiskLevel.valueOf(risk.riskLevel()));
                row.setFactors(toJson(risk.rates()));
                row.setFlagged(Boolean.TRUE.equals(risk.flagged()));
                contributorRiskRepository.save(row);
            }
        }

        if (result.capabilities() != null) {
            for (AiCapability capability : result.capabilities()) {
                if (capability.findings() == null) {
                    continue;
                }
                for (AiFinding finding : capability.findings()) {
                    DatasetEvidence evidence = new DatasetEvidence();
                    evidence.setAnalysis(analysis);
                    evidence.setFindingId(finding.findingId());
                    evidence.setDetector(finding.detector());
                    evidence.setTitle(finding.title());
                    evidence.setDescription(finding.description());
                    evidence.setSeverity(RiskLevel.valueOf(finding.severity()));
                    evidence.setConfidence(finding.confidence() != null
                            ? BigDecimal.valueOf(finding.confidence()) : null);
                    evidence.setSampleCount(finding.sampleCount() != null ? finding.sampleCount() : 0);
                    evidence.setContributors(toJson(finding.contributors()));
                    List<String> imagePaths = new ArrayList<>();
                    if (finding.evidence() != null) {
                        finding.evidence().forEach(e -> {
                            if (e.imagePaths() != null) {
                                imagePaths.addAll(e.imagePaths());
                            }
                        });
                    }
                    evidence.setImagePaths(imagePaths);
                    evidence.setDetail(toJson(finding.detail()));
                    evidenceRepository.save(evidence);
                }
            }
        }
    }

    private int countByCapability(AiAssuranceResult result, String capability) {
        if (result.capabilities() == null) {
            return 0;
        }
        return result.capabilities().stream()
                .filter(cap -> capability.equals(cap.capability()) && Boolean.TRUE.equals(cap.ran()))
                .flatMap(cap -> cap.findings() == null
                        ? java.util.stream.Stream.<AiFinding>empty()
                        : cap.findings().stream())
                .mapToInt(f -> f.sampleCount() == null ? 0 : f.sampleCount())
                .sum();
    }

    private DatasetAnalysisResponse toResponse(DatasetAnalysis analysis, boolean includeDetails) {
        UUID analysisId = analysis.getId();
        List<ContributorRiskResponse> risks = includeDetails
                ? contributorRiskRepository.findByAnalysis_IdOrderByRiskScoreDesc(analysisId).stream()
                        .map(ContributorRiskResponse::from)
                        .toList()
                : List.of();
        List<EvidenceResponse> evidence = includeDetails
                ? evidenceRepository.findByAnalysis_IdOrderByCreatedAtAsc(analysisId).stream()
                        .map(this::toEvidenceResponse)
                        .toList()
                : List.of();
        return new DatasetAnalysisResponse(
                analysisId,
                analysis.getDataset().getId(),
                analysis.getStatus().name(),
                analysis.getEngineJobId(),
                analysis.getDuplicatesCount(),
                analysis.getFloodCount(),
                analysis.getLabelFlipCount(),
                analysis.getSystematicMislabelCount(),
                analysis.getTriggerCount(),
                analysis.getOodCount(),
                analysis.getTrustScore(),
                analysis.getRiskLevel() != null ? analysis.getRiskLevel().name() : null,
                fromJson(analysis.getComponentScores(), new TypeReference<List<ComponentScoreDto>>() {
                }),
                fromJson(analysis.getLimitations(), new TypeReference<List<String>>() {
                }),
                analysis.getResultSha256(),
                analysis.getError(),
                analysis.getStartedAt(),
                analysis.getCompletedAt(),
                risks,
                evidence
        );
    }

    private EvidenceResponse toEvidenceResponse(DatasetEvidence evidence) {
        return new EvidenceResponse(
                evidence.getId(),
                evidence.getAnalysis() != null ? evidence.getAnalysis().getId() : null,
                evidence.getFindingId(),
                evidence.getDetector(),
                evidence.getTitle(),
                evidence.getDescription(),
                evidence.getSeverity().name(),
                evidence.getConfidence(),
                evidence.getSampleCount(),
                fromJson(evidence.getContributors(), new TypeReference<List<String>>() {
                }),
                evidence.getImagePaths(),
                fromJson(evidence.getDetail(), new TypeReference<Map<String, Object>>() {
                }),
                evidence.getCreatedAt()
        );
    }

    private User systemUser() {
        return userRepository.findByUsername(properties.ownerUsername())
                .orElseThrow(() -> new IllegalStateException(
                        "seeded system user missing — check Flyway migration V1__dataset_assurance.sql"));
    }

    private ClassificationLevel parseClassification(String value) {
        try {
            return ClassificationLevel.valueOf(value.trim().toUpperCase().replace('-', '_'));
        } catch (IllegalArgumentException e) {
            throw new InvalidDatasetException(
                    "classification must be one of: UNCLASSIFIED, OFFICIAL, OFFICIAL_SENSITIVE, SECRET");
        }
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (IOException e) {
            throw new IllegalStateException("JSON serialisation failed", e);
        }
    }

    private <T> T fromJson(String json, TypeReference<T> type) {
        if (json == null || json.isBlank()) {
            return null;
        }
        try {
            return objectMapper.readValue(json, type);
        } catch (IOException e) {
            throw new IllegalStateException("JSON deserialisation failed", e);
        }
    }
}

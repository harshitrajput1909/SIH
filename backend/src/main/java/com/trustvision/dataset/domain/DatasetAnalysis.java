package com.trustvision.dataset.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UuidGenerator;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/** One stored analysis run over a dataset, with aggregates and the full engine result. */
@Entity
@Table(name = "dataset_analysis")
public class DatasetAnalysis {

    @Id
    @UuidGenerator
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "dataset_id", nullable = false)
    private Dataset dataset;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private JobStatus status = JobStatus.QUEUED;

    @Column(name = "engine_job_id")
    private String engineJobId;

    @Column(name = "duplicates_count")
    private Integer duplicatesCount;

    @Column(name = "flood_count")
    private Integer floodCount;

    @Column(name = "label_flip_count")
    private Integer labelFlipCount;

    @Column(name = "systematic_mislabel_count")
    private Integer systematicMislabelCount;

    @Column(name = "trigger_count")
    private Integer triggerCount;

    @Column(name = "ood_count")
    private Integer oodCount;

    @Column(name = "trust_score", precision = 5, scale = 2)
    private BigDecimal trustScore;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Enumerated(EnumType.STRING)
    private RiskLevel riskLevel;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "component_scores", columnDefinition = "jsonb")
    private String componentScores;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private String limitations;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "result_json", columnDefinition = "jsonb")
    private String resultJson;

    @Column(name = "result_sha256", columnDefinition = "char(64)")
    private String resultSha256;

    private String error;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "requested_by")
    private User requestedBy;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    public UUID getId() { return id; }
    public Dataset getDataset() { return dataset; }
    public void setDataset(Dataset dataset) { this.dataset = dataset; }
    public JobStatus getStatus() { return status; }
    public void setStatus(JobStatus status) { this.status = status; }
    public String getEngineJobId() { return engineJobId; }
    public void setEngineJobId(String engineJobId) { this.engineJobId = engineJobId; }
    public Integer getDuplicatesCount() { return duplicatesCount; }
    public void setDuplicatesCount(Integer duplicatesCount) { this.duplicatesCount = duplicatesCount; }
    public Integer getFloodCount() { return floodCount; }
    public void setFloodCount(Integer floodCount) { this.floodCount = floodCount; }
    public Integer getLabelFlipCount() { return labelFlipCount; }
    public void setLabelFlipCount(Integer labelFlipCount) { this.labelFlipCount = labelFlipCount; }
    public Integer getSystematicMislabelCount() { return systematicMislabelCount; }
    public void setSystematicMislabelCount(Integer systematicMislabelCount) { this.systematicMislabelCount = systematicMislabelCount; }
    public Integer getTriggerCount() { return triggerCount; }
    public void setTriggerCount(Integer triggerCount) { this.triggerCount = triggerCount; }
    public Integer getOodCount() { return oodCount; }
    public void setOodCount(Integer oodCount) { this.oodCount = oodCount; }
    public BigDecimal getTrustScore() { return trustScore; }
    public void setTrustScore(BigDecimal trustScore) { this.trustScore = trustScore; }
    public RiskLevel getRiskLevel() { return riskLevel; }
    public void setRiskLevel(RiskLevel riskLevel) { this.riskLevel = riskLevel; }
    public String getComponentScores() { return componentScores; }
    public void setComponentScores(String componentScores) { this.componentScores = componentScores; }
    public String getLimitations() { return limitations; }
    public void setLimitations(String limitations) { this.limitations = limitations; }
    public String getResultJson() { return resultJson; }
    public void setResultJson(String resultJson) { this.resultJson = resultJson; }
    public String getResultSha256() { return resultSha256; }
    public void setResultSha256(String resultSha256) { this.resultSha256 = resultSha256; }
    public String getError() { return error; }
    public void setError(String error) { this.error = error; }
    public Instant getStartedAt() { return startedAt; }
    public void setStartedAt(Instant startedAt) { this.startedAt = startedAt; }
    public Instant getCompletedAt() { return completedAt; }
    public void setCompletedAt(Instant completedAt) { this.completedAt = completedAt; }
    public User getRequestedBy() { return requestedBy; }
    public void setRequestedBy(User requestedBy) { this.requestedBy = requestedBy; }
    public Instant getCreatedAt() { return createdAt; }
}

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
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UuidGenerator;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "assurance_reports")
public class AssuranceReport {

    @Id
    @UuidGenerator
    private UUID id;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Enumerated(EnumType.STRING)
    @Column(name = "report_type", nullable = false)
    private ReportType reportType = ReportType.ASSESSMENT;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ReportFormat format = ReportFormat.JSON;

    @Column(nullable = false, length = 300)
    private String title;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Enumerated(EnumType.STRING)
    @Column(name = "subject_type", nullable = false)
    private ProvenanceSubject subjectType = ProvenanceSubject.DATASET;

    @Column(name = "subject_id", nullable = false)
    private UUID subjectId;

    @Column(name = "dataset_analysis_id")
    private UUID datasetAnalysisId;

    @Column(name = "trust_score", precision = 5, scale = 2)
    private BigDecimal trustScore;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Enumerated(EnumType.STRING)
    private RiskLevel riskLevel;

    @Column(name = "artefact_ref", nullable = false, length = 500)
    private String artefactRef;

    @Column(nullable = false, columnDefinition = "char(64)")
    private String sha256;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "generated_by", nullable = false)
    private User generatedBy;

    @Column(name = "generated_at", nullable = false)
    private Instant generatedAt = Instant.now();

    public UUID getId() { return id; }
    public ReportType getReportType() { return reportType; }
    public ReportFormat getFormat() { return format; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public ProvenanceSubject getSubjectType() { return subjectType; }
    public void setSubjectType(ProvenanceSubject subjectType) { this.subjectType = subjectType; }
    public UUID getSubjectId() { return subjectId; }
    public void setSubjectId(UUID subjectId) { this.subjectId = subjectId; }
    public UUID getDatasetAnalysisId() { return datasetAnalysisId; }
    public void setDatasetAnalysisId(UUID datasetAnalysisId) { this.datasetAnalysisId = datasetAnalysisId; }
    public BigDecimal getTrustScore() { return trustScore; }
    public void setTrustScore(BigDecimal trustScore) { this.trustScore = trustScore; }
    public RiskLevel getRiskLevel() { return riskLevel; }
    public void setRiskLevel(RiskLevel riskLevel) { this.riskLevel = riskLevel; }
    public String getArtefactRef() { return artefactRef; }
    public void setArtefactRef(String artefactRef) { this.artefactRef = artefactRef; }
    public String getSha256() { return sha256; }
    public void setSha256(String sha256) { this.sha256 = sha256; }
    public User getGeneratedBy() { return generatedBy; }
    public void setGeneratedBy(User generatedBy) { this.generatedBy = generatedBy; }
    public Instant getGeneratedAt() { return generatedAt; }
}

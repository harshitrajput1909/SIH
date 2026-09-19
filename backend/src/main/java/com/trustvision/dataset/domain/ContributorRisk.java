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

/** Contributor risk score snapshot, one row per (analysis run, contributor). */
@Entity
@Table(name = "contributor_risk")
public class ContributorRisk {

    @Id
    @UuidGenerator
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "dataset_analysis_id", nullable = false)
    private DatasetAnalysis analysis;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "contributor_id", nullable = false)
    private Contributor contributor;

    @Column(name = "samples_contributed", nullable = false)
    private int samplesContributed;

    @Column(name = "risk_score", nullable = false, precision = 5, scale = 2)
    private BigDecimal riskScore;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private RiskLevel riskLevel;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private String factors;

    @Column(nullable = false)
    private boolean flagged = false;

    @Column(name = "assessed_at", nullable = false)
    private Instant assessedAt = Instant.now();

    public UUID getId() { return id; }
    public DatasetAnalysis getAnalysis() { return analysis; }
    public void setAnalysis(DatasetAnalysis analysis) { this.analysis = analysis; }
    public Contributor getContributor() { return contributor; }
    public void setContributor(Contributor contributor) { this.contributor = contributor; }
    public int getSamplesContributed() { return samplesContributed; }
    public void setSamplesContributed(int samplesContributed) { this.samplesContributed = samplesContributed; }
    public BigDecimal getRiskScore() { return riskScore; }
    public void setRiskScore(BigDecimal riskScore) { this.riskScore = riskScore; }
    public RiskLevel getRiskLevel() { return riskLevel; }
    public void setRiskLevel(RiskLevel riskLevel) { this.riskLevel = riskLevel; }
    public String getFactors() { return factors; }
    public void setFactors(String factors) { this.factors = factors; }
    public boolean isFlagged() { return flagged; }
    public void setFlagged(boolean flagged) { this.flagged = flagged; }
    public Instant getAssessedAt() { return assessedAt; }
}

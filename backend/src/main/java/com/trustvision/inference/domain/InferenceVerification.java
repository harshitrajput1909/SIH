package com.trustvision.inference.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UuidGenerator;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

/** Stored verification result: replay / tamper / signature / artifact checks. */
@Entity
@Table(name = "inference_verifications")
public class InferenceVerification {

    @Id
    @UuidGenerator
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "request_id", nullable = false)
    private InferenceRequest request;

    @Column(name = "record_id", nullable = false, length = 64)
    private String recordId;

    @Column(nullable = false)
    private boolean valid;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private String checks;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private String details;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "verified_by", nullable = false)
    private com.trustvision.dataset.domain.User verifiedBy;

    @Column(name = "verified_at", nullable = false)
    private Instant verifiedAt = Instant.now();

    public UUID getId() { return id; }
    public InferenceRequest getRequest() { return request; }
    public void setRequest(InferenceRequest request) { this.request = request; }
    public String getRecordId() { return recordId; }
    public void setRecordId(String recordId) { this.recordId = recordId; }
    public boolean isValid() { return valid; }
    public void setValid(boolean valid) { this.valid = valid; }
    public String getChecks() { return checks; }
    public void setChecks(String checks) { this.checks = checks; }
    public String getDetails() { return details; }
    public void setDetails(String details) { this.details = details; }
    public com.trustvision.dataset.domain.User getVerifiedBy() { return verifiedBy; }
    public void setVerifiedBy(com.trustvision.dataset.domain.User verifiedBy) { this.verifiedBy = verifiedBy; }
    public Instant getVerifiedAt() { return verifiedAt; }
}

package com.trustvision.inference.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UuidGenerator;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

/**
 * Platform copy of the provenance engine's hash-chained record. Append-only:
 * UPDATE/DELETE are refused by a database trigger (V2 migration).
 */
@Entity
@Table(name = "provenance_records")
public class ProvenanceRecord {

    @Id
    @UuidGenerator
    private UUID id;

    @Column(name = "request_id")
    private UUID requestId;

    @Column(name = "record_id", nullable = false, unique = true, length = 64)
    private String recordId;

    @Column(name = "record_type", nullable = false, length = 40)
    private String recordType;

    @Column(name = "record_timestamp", nullable = false)
    private Instant recordTimestamp;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private String artifacts;

    @Column(nullable = false)
    private String nonce;

    @Column(name = "prev_hash", columnDefinition = "char(64)")
    private String prevHash;

    @Column(name = "verification_hash", nullable = false, columnDefinition = "char(64)")
    private String verificationHash;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private String signature;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    public UUID getId() { return id; }
    public UUID getRequestId() { return requestId; }
    public void setRequestId(UUID requestId) { this.requestId = requestId; }
    public String getRecordId() { return recordId; }
    public void setRecordId(String recordId) { this.recordId = recordId; }
    public String getRecordType() { return recordType; }
    public void setRecordType(String recordType) { this.recordType = recordType; }
    public Instant getRecordTimestamp() { return recordTimestamp; }
    public void setRecordTimestamp(Instant recordTimestamp) { this.recordTimestamp = recordTimestamp; }
    public String getArtifacts() { return artifacts; }
    public void setArtifacts(String artifacts) { this.artifacts = artifacts; }
    public String getNonce() { return nonce; }
    public void setNonce(String nonce) { this.nonce = nonce; }
    public String getPrevHash() { return prevHash; }
    public void setPrevHash(String prevHash) { this.prevHash = prevHash; }
    public String getVerificationHash() { return verificationHash; }
    public void setVerificationHash(String verificationHash) { this.verificationHash = verificationHash; }
    public String getSignature() { return signature; }
    public void setSignature(String signature) { this.signature = signature; }
    public Instant getCreatedAt() { return createdAt; }
}

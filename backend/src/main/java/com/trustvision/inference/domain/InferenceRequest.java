package com.trustvision.inference.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UuidGenerator;

import java.time.Instant;
import java.util.UUID;

/** One inference verification call: the hashes, nonce and engine record link. */
@Entity
@Table(name = "inference_requests")
public class InferenceRequest {

    @Id
    @UuidGenerator
    private UUID id;

    @Column(name = "image_ref", nullable = false, length = 500)
    private String imageRef;

    @Column(name = "image_sha256", nullable = false, columnDefinition = "char(64)")
    private String imageSha256;

    @Column(name = "model_ref", nullable = false, length = 500)
    private String modelRef;

    @Column(name = "model_sha256", nullable = false, columnDefinition = "char(64)")
    private String modelSha256;

    @Column(name = "config_ref", length = 500)
    private String configRef;

    @Column(name = "config_sha256", columnDefinition = "char(64)")
    private String configSha256;

    @Column(name = "output_ref", length = 500)
    private String outputRef;

    @Column(name = "output_sha256", columnDefinition = "char(64)")
    private String outputSha256;

    @Column(nullable = false)
    private String nonce;

    @Column(name = "record_id", length = 64)
    private String recordId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "requested_by", nullable = false)
    private com.trustvision.dataset.domain.User requestedBy;

    @Column(name = "requested_at", nullable = false)
    private Instant requestedAt = Instant.now();

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    public UUID getId() { return id; }
    public String getImageRef() { return imageRef; }
    public void setImageRef(String imageRef) { this.imageRef = imageRef; }
    public String getImageSha256() { return imageSha256; }
    public void setImageSha256(String imageSha256) { this.imageSha256 = imageSha256; }
    public String getModelRef() { return modelRef; }
    public void setModelRef(String modelRef) { this.modelRef = modelRef; }
    public String getModelSha256() { return modelSha256; }
    public void setModelSha256(String modelSha256) { this.modelSha256 = modelSha256; }
    public String getConfigRef() { return configRef; }
    public void setConfigRef(String configRef) { this.configRef = configRef; }
    public String getConfigSha256() { return configSha256; }
    public void setConfigSha256(String configSha256) { this.configSha256 = configSha256; }
    public String getOutputRef() { return outputRef; }
    public void setOutputRef(String outputRef) { this.outputRef = outputRef; }
    public String getOutputSha256() { return outputSha256; }
    public void setOutputSha256(String outputSha256) { this.outputSha256 = outputSha256; }
    public String getNonce() { return nonce; }
    public void setNonce(String nonce) { this.nonce = nonce; }
    public String getRecordId() { return recordId; }
    public void setRecordId(String recordId) { this.recordId = recordId; }
    public com.trustvision.dataset.domain.User getRequestedBy() { return requestedBy; }
    public void setRequestedBy(com.trustvision.dataset.domain.User requestedBy) { this.requestedBy = requestedBy; }
    public Instant getRequestedAt() { return requestedAt; }
    public Instant getCreatedAt() { return createdAt; }
}

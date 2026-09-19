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
import org.hibernate.annotations.UpdateTimestamp;
import org.hibernate.annotations.UuidGenerator;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "datasets")
public class Dataset {

    @Id
    @UuidGenerator
    private UUID id;

    @Column(nullable = false, length = 120)
    private String name;

    @Column(length = 60)
    private String codename;

    @Column(nullable = false)
    private int version = 1;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private DatasetFormat format;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ClassificationLevel classification = ClassificationLevel.OFFICIAL;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "owner_id", nullable = false)
    private User owner;

    @Column(name = "supersedes_id")
    private UUID supersedesId;

    @Column(name = "artefact_ref", nullable = false, length = 500)
    private String artefactRef;

    @Column(nullable = false, columnDefinition = "char(64)")
    private String sha256;

    @Column(name = "size_bytes", nullable = false)
    private long sizeBytes;

    @Column(name = "image_count")
    private Integer imageCount;

    @Column(name = "class_count")
    private Integer classCount;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private DatasetState state = DatasetState.UPLOADED;

    @Column(name = "quarantined_at")
    private Instant quarantinedAt;

    @Column(length = 2000)
    private String notes;

    @Column(name = "uploaded_at", nullable = false)
    private Instant uploadedAt = Instant.now();

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(nullable = false)
    private Instant updatedAt;

    public UUID getId() { return id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getCodename() { return codename; }
    public void setCodename(String codename) { this.codename = codename; }
    public int getVersion() { return version; }
    public void setVersion(int version) { this.version = version; }
    public DatasetFormat getFormat() { return format; }
    public void setFormat(DatasetFormat format) { this.format = format; }
    public ClassificationLevel getClassification() { return classification; }
    public void setClassification(ClassificationLevel classification) { this.classification = classification; }
    public User getOwner() { return owner; }
    public void setOwner(User owner) { this.owner = owner; }
    public UUID getSupersedesId() { return supersedesId; }
    public void setSupersedesId(UUID supersedesId) { this.supersedesId = supersedesId; }
    public String getArtefactRef() { return artefactRef; }
    public void setArtefactRef(String artefactRef) { this.artefactRef = artefactRef; }
    public String getSha256() { return sha256; }
    public void setSha256(String sha256) { this.sha256 = sha256; }
    public long getSizeBytes() { return sizeBytes; }
    public void setSizeBytes(long sizeBytes) { this.sizeBytes = sizeBytes; }
    public Integer getImageCount() { return imageCount; }
    public void setImageCount(Integer imageCount) { this.imageCount = imageCount; }
    public Integer getClassCount() { return classCount; }
    public void setClassCount(Integer classCount) { this.classCount = classCount; }
    public DatasetState getState() { return state; }
    public void setState(DatasetState state) { this.state = state; }
    public Instant getQuarantinedAt() { return quarantinedAt; }
    public void setQuarantinedAt(Instant quarantinedAt) { this.quarantinedAt = quarantinedAt; }
    public String getNotes() { return notes; }
    public void setNotes(String notes) { this.notes = notes; }
    public Instant getUploadedAt() { return uploadedAt; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
}

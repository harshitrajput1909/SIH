package com.trustvision.dataset.repository;

import com.trustvision.dataset.domain.DatasetAnalysis;
import com.trustvision.dataset.domain.JobStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface DatasetAnalysisRepository extends JpaRepository<DatasetAnalysis, UUID> {

    Optional<DatasetAnalysis> findTopByDatasetIdOrderByCreatedAtDesc(UUID datasetId);

    boolean existsByDatasetIdAndStatus(UUID datasetId, JobStatus status);
}

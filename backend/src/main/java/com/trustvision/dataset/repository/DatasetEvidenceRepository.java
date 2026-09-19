package com.trustvision.dataset.repository;

import com.trustvision.dataset.domain.DatasetEvidence;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface DatasetEvidenceRepository extends JpaRepository<DatasetEvidence, UUID> {

    List<DatasetEvidence> findByAnalysis_IdOrderByCreatedAtAsc(UUID analysisId);
}

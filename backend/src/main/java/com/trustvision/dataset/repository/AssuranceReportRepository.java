package com.trustvision.dataset.repository;

import com.trustvision.dataset.domain.AssuranceReport;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface AssuranceReportRepository extends JpaRepository<AssuranceReport, UUID> {

    Optional<AssuranceReport> findFirstByDatasetAnalysisIdOrderByGeneratedAtDesc(UUID analysisId);
}

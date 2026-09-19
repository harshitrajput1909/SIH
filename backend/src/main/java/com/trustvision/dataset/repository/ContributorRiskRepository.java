package com.trustvision.dataset.repository;

import com.trustvision.dataset.domain.ContributorRisk;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface ContributorRiskRepository extends JpaRepository<ContributorRisk, UUID> {

    List<ContributorRisk> findByAnalysis_IdOrderByRiskScoreDesc(UUID analysisId);
}

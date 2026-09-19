package com.trustvision.inference.repository;

import com.trustvision.inference.domain.ProvenanceRecord;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface ProvenanceRecordRepository extends JpaRepository<ProvenanceRecord, UUID> {

    Optional<ProvenanceRecord> findByRecordId(String recordId);

    Optional<ProvenanceRecord> findTopByRequestIdOrderByCreatedAtDesc(UUID requestId);
}

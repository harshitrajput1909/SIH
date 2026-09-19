package com.trustvision.inference.repository;

import com.trustvision.inference.domain.InferenceRequest;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface InferenceRequestRepository extends JpaRepository<InferenceRequest, UUID> {

    Optional<InferenceRequest> findByNonce(String nonce);
}

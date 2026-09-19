package com.trustvision.inference.repository;

import com.trustvision.inference.domain.InferenceVerification;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface InferenceVerificationRepository extends JpaRepository<InferenceVerification, UUID> {

    List<InferenceVerification> findByRequestIdOrderByVerifiedAtDesc(UUID requestId);
}

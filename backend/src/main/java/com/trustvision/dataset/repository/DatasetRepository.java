package com.trustvision.dataset.repository;

import com.trustvision.dataset.domain.Dataset;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface DatasetRepository extends JpaRepository<Dataset, UUID> {

    Optional<Dataset> findTopByNameOrderByVersionDesc(String name);

    boolean existsByNameAndVersion(String name, int version);
}

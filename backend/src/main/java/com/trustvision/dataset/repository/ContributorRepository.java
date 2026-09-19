package com.trustvision.dataset.repository;

import com.trustvision.dataset.domain.Contributor;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface ContributorRepository extends JpaRepository<Contributor, UUID> {

    Optional<Contributor> findByNameIgnoreCase(String name);
}
